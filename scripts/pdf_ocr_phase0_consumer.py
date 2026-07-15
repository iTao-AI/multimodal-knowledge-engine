#!/usr/bin/env python3
"""Prove the Phase 0 scorecard and portable EvidenceRef through one installed wheel."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
from consumer_source_pack_proof import (  # noqa: E402
    CommandResult,
    ControllerError,
    isolated_environment,
    run_bounded,
)

_SCHEMA = "mke.pdf_ocr_phase0_consumer_proof.v1"
_PROTOCOL = "pdf-ocr-phase0-v1"
_DISTRIBUTION = "multimodal-knowledge-engine"
_WHEEL_RE = re.compile(
    r"multimodal_knowledge_engine-(?P<version>[0-9]+(?:\.[0-9]+){2})-py3-none-any\.whl\Z"
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_COMMAND_TIMEOUT_SECONDS = 900.0
_MAX_STDOUT_BYTES = 2 * 1024 * 1024
_MAX_STDERR_BYTES = 512 * 1024
_CLIENT_CODES = frozenset(
    {
        "ingest_failed",
        "server_failed",
        "discovery_failed",
        "search_failed",
        "ask_failed",
        "locator_failed",
        "schema_failed",
    }
)
_RECEIPTS = {
    "package_sha256": Path("benchmarks/ocr/candidate-environments.json"),
    "model_sha256": Path("benchmarks/ocr/model-artifacts.json"),
    "provider_startup_sha256": Path("benchmarks/ocr/provider-startup.json"),
}
_PROTOCOL_PATH = Path("tests/fixtures/pdf-ocr-phase0-v1/protocol.json")


class ConsumerProofError(RuntimeError):
    """Closed controller failure that never serializes private detail."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ConsumerProofConfig:
    repository: Path
    wheel: Path
    scorecard: Path
    python: str = sys.executable


@dataclass(frozen=True)
class _WheelAuthority:
    path: Path
    version: str
    bytes: int
    sha256: str


CommandRunner = Callable[..., CommandResult]
Cleanup = Callable[[Path], None]


def run_consumer_proof(config: ConsumerProofConfig) -> dict[str, object]:
    return _run_consumer_proof(
        config,
        command_runner=run_bounded,
        cleanup=_remove_runtime_root,
        validate_scorecard=True,
    )


def _run_consumer_proof_for_test(  # pyright: ignore[reportUnusedFunction]
    config: ConsumerProofConfig,
    *,
    command_runner: CommandRunner,
    cleanup: Cleanup = shutil.rmtree,
    validate_scorecard: bool = True,
) -> dict[str, object]:
    return _run_consumer_proof(
        config,
        command_runner=command_runner,
        cleanup=cleanup,
        validate_scorecard=validate_scorecard,
    )


def _run_consumer_proof(
    config: ConsumerProofConfig,
    *,
    command_runner: CommandRunner,
    cleanup: Cleanup,
    validate_scorecard: bool,
) -> dict[str, object]:
    repository = _directory(config.repository, "build_failed")
    wheel = _wheel_authority(config.wheel)
    scorecard = _scorecard_authority(config.scorecard, validate=validate_scorecard)
    _validate_repository_inputs(repository, scorecard)
    runtime_root = Path(tempfile.mkdtemp(prefix="mke-pdf-ocr-consumer-")).resolve()
    result: dict[str, object] | None = None
    pending: ConsumerProofError | None = None
    try:
        if _within(runtime_root, repository):
            raise ConsumerProofError("venv_failed")
        _prepare_runtime_inputs(repository, config.scorecard, runtime_root)
        environment = runtime_root / "venv"
        bin_dir = environment / ("Scripts" if os.name == "nt" else "bin")
        installed_python = bin_dir / "python"
        installed_mke = bin_dir / "mke"
        child_environment = _child_environment(runtime_root)

        _step(
            command_runner,
            "venv_failed",
            ["uv", "venv", str(environment), "--python", config.python, "--no-python-downloads"],
            cwd=runtime_root,
            env=child_environment,
        )
        _step(
            command_runner,
            "install_failed",
            [
                "uv",
                "pip",
                "install",
                "--offline",
                "--python",
                str(installed_python),
                str(wheel.path),
            ],
            cwd=runtime_root,
            env=child_environment,
        )

        identity = _json_step(
            command_runner,
            "schema_failed",
            [
                str(installed_python),
                "-I",
                str(runtime_root / "pdf_ocr_phase0_consumer.py"),
                "--internal-identity",
            ],
            cwd=runtime_root,
            env=child_environment,
        )
        python_version = _validate_installed_identity(
            identity,
            environment=environment,
            repository=repository,
            wheel=wheel,
        )

        candidate = _json_step(
            command_runner,
            "candidate_failed",
            _sandboxed(
                runtime_root,
                [
                    str(installed_python),
                    "-I",
                    str(runtime_root / "pdf_ocr_phase0_consumer.py"),
                    "--internal-candidate",
                    "--scorecard",
                    str(runtime_root / "phase0-scorecard.json"),
                    "--protocol",
                    str(runtime_root / _PROTOCOL_PATH),
                    "--package-receipt",
                    str(runtime_root / _RECEIPTS["package_sha256"]),
                    "--model-receipt",
                    str(runtime_root / _RECEIPTS["model_sha256"]),
                    "--startup-receipt",
                    str(runtime_root / _RECEIPTS["provider_startup_sha256"]),
                    "--database",
                    str(runtime_root / "phase0.sqlite"),
                ],
            ),
            cwd=runtime_root,
            env=child_environment,
        )
        if candidate.get("status") == "no_go":
            result = _no_go_result(wheel, python_version)
        else:
            provider, profile = _validate_candidate_result(candidate, scorecard)
            client = _client_step(
                command_runner,
                _sandboxed(
                    runtime_root,
                    [
                        str(installed_python),
                        "-I",
                        str(runtime_root / "pdf_ocr_phase0_consumer.py"),
                        "--internal-client",
                        "--database",
                        str(runtime_root / "phase0.sqlite"),
                        "--protocol",
                        str(runtime_root / _PROTOCOL_PATH),
                        "--mke",
                        str(installed_mke),
                    ],
                ),
                cwd=runtime_root,
                env=child_environment,
            )
            _validate_client_result(client)
            result = {
                "schema": _SCHEMA,
                "status": "passed",
                "protocol": _PROTOCOL,
                "provider": provider,
                "profile": profile,
                "package_version": wheel.version,
                "python_version": python_version,
                "wheel_sha256": wheel.sha256,
                "wheel_reused": True,
                "publication_verified": True,
                "search_verified": True,
                "ask_verified": True,
                "evidence_ref_verified": True,
                "network_blocked": True,
                "cleanup": True,
            }
    except ConsumerProofError as error:
        pending = error
    finally:
        try:
            cleanup(runtime_root)
        except OSError:
            pending = ConsumerProofError("cleanup_failed")
        if runtime_root.exists() and pending is None:
            pending = ConsumerProofError("cleanup_failed")
    if pending is not None:
        raise pending
    if result is None:
        raise ConsumerProofError("schema_failed")
    _validate_public_result(result)
    return result


def _step(
    runner: CommandRunner,
    code: str,
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> CommandResult:
    print(f"stage={code.removesuffix('_failed')}", file=sys.stderr)
    try:
        result = runner(
            command,
            cwd=cwd,
            env=env,
            timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
            max_stdout_bytes=_MAX_STDOUT_BYTES,
            max_stderr_bytes=_MAX_STDERR_BYTES,
        )
    except (ControllerError, OSError) as error:
        raise ConsumerProofError(code) from error
    if result.returncode != 0:
        raise ConsumerProofError(code)
    return result


def _json_step(
    runner: CommandRunner,
    code: str,
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> dict[str, object]:
    result = _step(runner, code, command, cwd=cwd, env=env)
    try:
        value: object = json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConsumerProofError(code) from error
    if not isinstance(value, dict):
        raise ConsumerProofError(code)
    return cast(dict[str, object], value)


def _client_step(
    runner: CommandRunner,
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> dict[str, object]:
    try:
        result = runner(
            command,
            cwd=cwd,
            env=env,
            timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
            max_stdout_bytes=_MAX_STDOUT_BYTES,
            max_stderr_bytes=_MAX_STDERR_BYTES,
        )
    except (ControllerError, OSError) as error:
        raise ConsumerProofError("server_failed") from error
    try:
        value: object = json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConsumerProofError("server_failed") from error
    if not isinstance(value, dict):
        raise ConsumerProofError("server_failed")
    payload = cast(dict[str, object], value)
    if result.returncode != 0:
        code = payload.get("code")
        if payload.get("status") == "failed" and isinstance(code, str) and code in _CLIENT_CODES:
            raise ConsumerProofError(code)
        raise ConsumerProofError("server_failed")
    return payload


def _validate_client_result(value: Mapping[str, object]) -> None:
    expected = {
        "status": "passed",
        "discovery_verified": True,
        "search_verified": True,
        "ask_verified": True,
        "evidence_ref_verified": True,
        "network_blocked": True,
    }
    if dict(value) != expected:
        code = value.get("code")
        if value.get("status") == "failed" and isinstance(code, str) and code in _CLIENT_CODES:
            raise ConsumerProofError(code)
        raise ConsumerProofError("schema_failed")


def _wheel_authority(path: Path) -> _WheelAuthority:
    try:
        wheel = path.resolve(strict=True)
        if wheel.is_symlink() or not wheel.is_file():
            raise ValueError
        matched = _WHEEL_RE.fullmatch(wheel.name)
        if matched is None:
            raise ValueError
        data = wheel.read_bytes()
        with zipfile.ZipFile(wheel) as archive:
            metadata_names = [
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_names) != 1:
                raise ValueError
            metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        version = matched.group("version")
        if metadata.get("Name") != _DISTRIBUTION or metadata.get("Version") != version:
            raise ValueError
    except (OSError, ValueError, zipfile.BadZipFile, KeyError) as error:
        raise ConsumerProofError("build_failed") from error
    return _WheelAuthority(wheel, version, len(data), hashlib.sha256(data).hexdigest())


def _scorecard_authority(path: Path, *, validate: bool) -> dict[str, object]:
    try:
        from mke.evaluation.pdf_ocr_runner import canonical_scorecard_bytes

        raw = path.read_bytes()
        value: object = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError
        scorecard = cast(dict[str, object], value)
        if validate and canonical_scorecard_bytes(scorecard) != raw:
            raise ValueError
        decision_value = scorecard.get("decision")
        if not isinstance(decision_value, dict):
            raise ValueError
        decision = cast(dict[str, object], decision_value)
        if decision.get("status") not in {"go", "no_go"}:
            raise ValueError
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ConsumerProofError("schema_failed") from error
    return scorecard


def _validate_repository_inputs(repository: Path, scorecard: Mapping[str, object]) -> None:
    receipts_value = scorecard.get("receipts")
    if not isinstance(receipts_value, dict):
        raise ConsumerProofError("schema_failed")
    receipts = cast(dict[str, object], receipts_value)
    if set(receipts) != set(_RECEIPTS):
        raise ConsumerProofError("schema_failed")
    for key, relative in _RECEIPTS.items():
        path = repository / relative
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise ConsumerProofError("schema_failed") from error
        if receipts.get(key) != digest:
            raise ConsumerProofError("schema_failed")
    if not (repository / _PROTOCOL_PATH).is_file():
        raise ConsumerProofError("schema_failed")


def _prepare_runtime_inputs(repository: Path, scorecard: Path, runtime_root: Path) -> None:
    try:
        shutil.copy2(Path(__file__).resolve(), runtime_root / "pdf_ocr_phase0_consumer.py")
        shutil.copy2(
            Path(__file__).resolve().with_name("consumer_source_pack_proof.py"),
            runtime_root / "consumer_source_pack_proof.py",
        )
        shutil.copy2(scorecard, runtime_root / "phase0-scorecard.json")
        protocol_source = repository / _PROTOCOL_PATH.parent
        protocol_target = runtime_root / _PROTOCOL_PATH.parent
        protocol_target.parent.mkdir(parents=True)
        shutil.copytree(protocol_source, protocol_target)
        for relative in _RECEIPTS.values():
            target = runtime_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repository / relative, target)
        (runtime_root / "home").mkdir(mode=0o700)
        (runtime_root / "tmp").mkdir(mode=0o700)
        (runtime_root / "deny-network.sb").write_text(
            "(version 1)\n(allow default)\n(deny network*)\n", encoding="utf-8"
        )
    except OSError as error:
        raise ConsumerProofError("venv_failed") from error


def _validate_installed_identity(
    value: Mapping[str, object],
    *,
    environment: Path,
    repository: Path,
    wheel: _WheelAuthority,
) -> str:
    if set(value) != {
        "mke_file",
        "mke_version",
        "metadata_version",
        "python_version",
        "sys_executable",
    }:
        raise ConsumerProofError("schema_failed")
    strings = {key: value[key] for key in value}
    if any(not isinstance(item, str) for item in strings.values()):
        raise ConsumerProofError("schema_failed")
    module = Path(cast(str, value["mke_file"])).resolve()
    executable = Path(os.path.abspath(cast(str, value["sys_executable"])))
    if (
        value["mke_version"] != wheel.version
        or value["metadata_version"] != wheel.version
        or not _within(module, environment.resolve())
        or not _within(executable, environment.resolve())
        or _within(module, repository.resolve())
        or _within(executable, repository.resolve())
        or "site-packages" not in module.parts
    ):
        raise ConsumerProofError("schema_failed")
    version = cast(str, value["python_version"])
    if re.fullmatch(r"3\.(?:12|13)\.\d+", version) is None:
        raise ConsumerProofError("schema_failed")
    return version


def _validate_candidate_result(
    value: Mapping[str, object], scorecard: Mapping[str, object]
) -> tuple[str, str]:
    if set(value) != {"status", "protocol", "provider", "profile", "publication_verified"}:
        raise ConsumerProofError("schema_failed")
    decision = cast(dict[str, object], scorecard["decision"])
    if (
        value["status"] != "passed"
        or value["protocol"] != _PROTOCOL
        or value["provider"] != decision["selected_provider"]
        or value["profile"] != decision["selected_profile"]
        or value["publication_verified"] is not True
        or not isinstance(value["provider"], str)
        or not isinstance(value["profile"], str)
    ):
        raise ConsumerProofError("ingest_failed")
    return value["provider"], value["profile"]


def _no_go_result(wheel: _WheelAuthority, python_version: str) -> dict[str, object]:
    return {
        "schema": _SCHEMA,
        "status": "no_go",
        "protocol": _PROTOCOL,
        "package_version": wheel.version,
        "python_version": python_version,
        "wheel_sha256": wheel.sha256,
        "wheel_reused": True,
        "publication_verified": False,
        "search_verified": False,
        "ask_verified": False,
        "evidence_ref_verified": False,
        "network_blocked": True,
        "cleanup": True,
    }


def _validate_public_result(value: Mapping[str, object]) -> None:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if any(marker in encoded for marker in ("/Users/", "/private/", "Traceback", "TOKEN=")):
        raise ConsumerProofError("schema_failed")
    if value.get("schema") != _SCHEMA or value.get("protocol") != _PROTOCOL:
        raise ConsumerProofError("schema_failed")
    digest = value.get("wheel_sha256")
    if digest is not None and (not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None):
        raise ConsumerProofError("schema_failed")


def _child_environment(runtime_root: Path) -> dict[str, str]:
    environment = isolated_environment(os.environ)
    operator_home = environment.get("HOME")
    cache = environment.get("UV_CACHE_DIR")
    if cache is None and operator_home is not None:
        cache = str(Path(operator_home) / ".cache/uv")
    if cache is None or not Path(cache).is_dir():
        raise ConsumerProofError("install_failed")
    for key in tuple(environment):
        if key.lower().endswith("proxy"):
            environment.pop(key, None)
    environment.update(
        {
            "HOME": str(runtime_root / "home"),
            "TMPDIR": str(runtime_root / "tmp"),
            "UV_CACHE_DIR": cache,
            "UV_OFFLINE": "1",
            "NO_PROXY": "*",
        }
    )
    return environment


def _sandboxed(runtime_root: Path, command: list[str]) -> list[str]:
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise ConsumerProofError("candidate_failed")
    return ["/usr/bin/sandbox-exec", "-f", str(runtime_root / "deny-network.sb"), *command]


def _directory(path: Path, code: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ConsumerProofError(code) from error
    if resolved.is_symlink() or not resolved.is_dir():
        raise ConsumerProofError(code)
    return resolved


def _remove_runtime_root(path: Path) -> None:
    shutil.rmtree(path)


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _internal_identity() -> int:
    import importlib.metadata as metadata

    import mke

    print(
        json.dumps(
            {
                "mke_file": mke.__file__,
                "mke_version": mke.__version__,
                "metadata_version": metadata.version(_DISTRIBUTION),
                "python_version": ".".join(map(str, sys.version_info[:3])),
                "sys_executable": sys.executable,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


def _internal_candidate(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--internal-candidate", action="store_true")
    parser.add_argument("--scorecard", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--package-receipt", type=Path, required=True)
    parser.add_argument("--model-receipt", type=Path, required=True)
    parser.add_argument("--startup-receipt", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from mke.evaluation.pdf_ocr_protocol import load_pdf_ocr_evaluation_protocol
        from mke.evaluation.pdf_ocr_provider import normalize_ocr_text
        from mke.evaluation.pdf_ocr_runner import (
            canonical_scorecard_bytes,
            publish_and_verify,
        )

        raw = args.scorecard.read_bytes()
        scorecard = cast(dict[str, object], json.loads(raw))
        if canonical_scorecard_bytes(scorecard) != raw:
            raise ValueError
        receipts = cast(dict[str, object], scorecard["receipts"])
        paths = {
            "package_sha256": args.package_receipt,
            "model_sha256": args.model_receipt,
            "provider_startup_sha256": args.startup_receipt,
        }
        if any(
            hashlib.sha256(path.read_bytes()).hexdigest() != receipts[key]
            for key, path in paths.items()
        ):
            raise ValueError
        decision = cast(dict[str, object], scorecard["decision"])
        if decision["status"] == "no_go":
            print('{"status":"no_go"}')
            return 0
        provider = cast(str, decision["selected_provider"])
        profile = cast(str, decision["selected_profile"])
        bindings = cast(list[dict[str, object]], scorecard["extractor_identities"])
        identity = next(item["payload"] for item in bindings if item["provider"] == provider)
        protocol = load_pdf_ocr_evaluation_protocol(args.protocol)
        recognized = {
            (document.document_id, page.page_number): normalize_ocr_text(page.expected_ocr_text)
            for document in protocol.documents
            for page in document.pages
            if page.expected_ocr_text is not None
        }
        proof = publish_and_verify(
            protocol=protocol,
            recognized_text=recognized,
            extractor_identity=cast(dict[str, object], identity),
            database=args.database,
        )
        if (
            proof.failure_codes
            or proof.route_accuracy.numerator != proof.route_accuracy.denominator
            or proof.query_accuracy.numerator != proof.query_accuracy.denominator
            or proof.evidence_ref_accuracy.numerator != proof.evidence_ref_accuracy.denominator
        ):
            raise RuntimeError("product proof failed")
        result = {
            "status": "passed",
            "protocol": protocol.protocol_id,
            "provider": provider,
            "profile": profile,
            "publication_verified": True,
        }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception:
        print('{"code":"ingest_failed","status":"failed"}')
        return 1


async def _run_mcp_client(
    database: Path, protocol_path: Path, executable: Path
) -> dict[str, object]:
    from datetime import timedelta

    from mcp import ClientSession, StdioServerParameters, types
    from mcp.client.stdio import stdio_client

    from mke.evaluation.pdf_ocr_protocol import (
        documents_by_id,
        load_pdf_ocr_evaluation_protocol,
    )
    from mke.evaluation.pdf_ocr_provider import normalize_ocr_text
    from mke.interfaces.mcp_schemas import (
        AskLibraryResponseV1,
        AskLibrarySuccessV1,
        EvidenceRefV1,
        SearchLibraryResponseV1,
        SearchLibrarySuccessV1,
    )

    sock = socket.socket()
    sock.settimeout(0.2)
    try:
        sock.connect(("1.1.1.1", 53))
    except OSError:
        network_blocked = True
    else:
        network_blocked = False
    finally:
        sock.close()
    if not network_blocked:
        raise ConsumerProofError("server_failed")

    protocol = load_pdf_ocr_evaluation_protocol(protocol_path)
    server = StdioServerParameters(
        command=str(executable),
        args=["--db", str(database), "mcp", "--allowed-root", str(protocol.root)],
        cwd=str(protocol.root),
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
    )

    def payload(result: object) -> dict[str, object]:
        if getattr(result, "isError", False):
            raise ConsumerProofError("schema_failed")
        structured = getattr(result, "structuredContent", None)
        if isinstance(structured, dict):
            return cast(dict[str, object], structured)
        for item in cast(list[object], getattr(result, "content", [])):
            if isinstance(item, types.TextContent):
                value = json.loads(item.text)
                if isinstance(value, dict):
                    return cast(dict[str, object], value)
        raise ConsumerProofError("schema_failed")

    try:
        async with stdio_client(server, errlog=sys.stderr) as (read, write):
            async with ClientSession(
                read,
                write,
                read_timeout_seconds=timedelta(seconds=60),
            ) as session:
                await asyncio.wait_for(session.initialize(), timeout=60)
                tools = await asyncio.wait_for(session.list_tools(), timeout=60)
                names = {item.name for item in tools.tools}
                if not {"search_library_v1", "ask_library_v1"}.issubset(names):
                    raise ConsumerProofError("discovery_failed")
                documents = documents_by_id(protocol)
                for query in protocol.queries:
                    try:
                        searched_raw = await asyncio.wait_for(
                            session.call_tool(
                                "search_library_v1", {"query": query.text, "limit": 5}
                            ),
                            timeout=60,
                        )
                    except Exception as error:
                        raise ConsumerProofError("search_failed") from error
                    try:
                        asked_raw = await asyncio.wait_for(
                            session.call_tool(
                                "ask_library_v1", {"question": query.text, "limit": 5}
                            ),
                            timeout=60,
                        )
                    except Exception as error:
                        raise ConsumerProofError("ask_failed") from error
                    try:
                        searched = SearchLibraryResponseV1.model_validate(
                            payload(searched_raw)
                        ).root
                        asked = AskLibraryResponseV1.model_validate(payload(asked_raw)).root
                    except Exception as error:
                        raise ConsumerProofError("schema_failed") from error
                    if not isinstance(searched, SearchLibrarySuccessV1) or not isinstance(
                        asked, AskLibrarySuccessV1
                    ):
                        raise ConsumerProofError("schema_failed")
                    expected_page = documents[query.expected_document_id].pages[
                        query.expected_page - 1
                    ]
                    expected_text = normalize_ocr_text(
                        expected_page.expected_ocr_text
                        or expected_page.expected_text_layer_text
                        or ""
                    )

                    def key(item: EvidenceRefV1) -> tuple[object, ...]:
                        return (
                            item.schema_version,
                            item.evidence_id,
                            item.source_id,
                            item.content_fingerprint,
                            item.publication_id,
                            item.publication_revision,
                            item.run_id,
                            item.locator.kind,
                            item.locator.start,
                            item.locator.end,
                            item.text,
                        )

                    expected_digest = (
                        "sha256:" + documents[query.expected_document_id].fixture.sha256
                    )
                    search_items = [
                        item
                        for item in searched.results
                        if item.locator.kind == "page"
                        and item.locator.start == query.expected_page
                        and item.locator.end == query.expected_page
                        and item.content_fingerprint == expected_digest
                        and item.text == expected_text
                    ]
                    ask_items = [
                        item
                        for item in asked.evidence
                        if item.locator.kind == "page"
                        and item.locator.start == query.expected_page
                        and item.locator.end == query.expected_page
                        and item.content_fingerprint == expected_digest
                        and item.text == expected_text
                    ]
                    if len(search_items) != 1 or len(ask_items) != 1:
                        raise ConsumerProofError("locator_failed")
                    if key(search_items[0]) != key(ask_items[0]):
                        raise ConsumerProofError("locator_failed")
    except ConsumerProofError:
        raise
    except Exception as error:
        raise ConsumerProofError("server_failed") from error
    return {
        "status": "passed",
        "discovery_verified": True,
        "search_verified": True,
        "ask_verified": True,
        "evidence_ref_verified": True,
        "network_blocked": True,
    }


def _internal_client(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--internal-client", action="store_true")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--mke", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(_run_mcp_client(args.database, args.protocol, args.mke))
    except ConsumerProofError as error:
        print(json.dumps({"status": "failed", "code": error.code}, separators=(",", ":")))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf_ocr_phase0_consumer.py")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--scorecard", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_consumer_proof(
            ConsumerProofConfig(
                repository=args.repository,
                wheel=args.wheel,
                scorecard=args.scorecard,
                python=args.python,
            )
        )
    except ConsumerProofError as error:
        result = {"status": "failed", "code": error.code}
        print(
            json.dumps(result, sort_keys=True, separators=(",", ":"))
            if args.json_output
            else f"status=failed code={error.code}"
        )
        return 1
    print(
        json.dumps(result, sort_keys=True, separators=(",", ":"))
        if args.json_output
        else " ".join(f"{key}={value}" for key, value in result.items())
    )
    return 0


if __name__ == "__main__":
    if "--internal-identity" in sys.argv[1:]:
        raise SystemExit(_internal_identity())
    if "--internal-candidate" in sys.argv[1:]:
        raise SystemExit(_internal_candidate(sys.argv[1:]))
    if "--internal-client" in sys.argv[1:]:
        raise SystemExit(_internal_client(sys.argv[1:]))
    raise SystemExit(main())
