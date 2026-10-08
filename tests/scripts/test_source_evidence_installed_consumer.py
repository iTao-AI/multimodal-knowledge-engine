from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/source_evidence_installed_consumer.py"


def consumer() -> Any:
    assert SCRIPT.is_file(), "installed Source consumer entry is missing"
    return importlib.import_module("scripts.source_evidence_installed_consumer")


def assets(root: Path) -> Path:
    root.mkdir()
    entries: list[dict[str, Any]] = []
    for role, count, text in [
        ("selected", 3, "needle café selected"),
        ("other", 5, "needle outsideonly"),
    ]:
        path = root / f"{role}.pdf"
        document = pymupdf.open()
        for number in range(count):
            page = document.new_page()
            page.insert_text((72, 72), f"{text} page {number + 1}")  # pyright: ignore[reportUnknownMemberType]
        document.save(path, no_new_id=True)  # pyright: ignore[reportUnknownMemberType]
        document.close()
        entries.append(
            {
                "role": role,
                "filename": path.name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "pages": count,
            }
        )
    (root / "manifest.json").write_text(
        json.dumps(
            {"schema_version": "mke.source_evidence_installed_manifest.v1", "sources": entries}
        )
    )
    return root


def config(module: Any, root: Path, asset_root: Path) -> Any:
    return module.Config(
        root,
        asset_root,
        ROOT / "tests/fixtures/source-search-v1/mcp-tool-schemas.json",
        Path(sys.executable).with_name("mke"),
        {**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )


@pytest.mark.parametrize("mutation", ["digest", "bytes", "extra", "filename"])
def test_asset_identity_is_checked_before_creating_a_library(tmp_path: Path, mutation: str) -> None:
    module = consumer()
    source_root = assets(tmp_path / "assets")
    manifest = json.loads((source_root / "manifest.json").read_text())
    if mutation == "digest":
        manifest["sources"][0]["sha256"] = "0" * 64
    elif mutation == "bytes":
        manifest["sources"][0]["bytes"] += 1
    elif mutation == "extra":
        manifest["sources"][0]["unbound"] = True
    else:
        manifest["sources"][0]["filename"] = "../selected.pdf"
    (source_root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(module.CaseFailure, match="asset_identity_invalid"):
        asyncio.run(module.run_flow(config(module, tmp_path / "data", source_root)))
    assert not (tmp_path / "data").exists()


def test_real_flow_binds_cli_ask_to_sdk_reads_and_never_fills_from_other_source(
    tmp_path: Path,
) -> None:
    module = consumer()
    source_root = assets(tmp_path / "assets")
    result = asyncio.run(module.run_flow(config(module, tmp_path / "data", source_root)))
    assert result["schema_version"] == "mke.source_evidence_installed_consumer.v1"
    assert result["status"] == "passed" and result["tool_count"] == 15
    assert result["cases"] == {
        "first_page": "more_available",
        "complete": "complete",
        "selected_empty": "insufficient_evidence",
        "unrelated_match": True,
        "cli_sdk_equal": True,
        "utf8_digest_and_excerpt_verified": True,
    }
    assert (
        result["scope"]["content_fingerprint"]
        == "sha256:" + hashlib.sha256((source_root / "selected.pdf").read_bytes()).hexdigest()
    )
    assert result["scope"]["publication_revision"] == 1
    assert len(result["references"]) == 3
    for reference in result["references"]:
        assert reference["evidence"]["source_id"] == result["scope"]["source_id"]
        assert reference["evidence"]["publication_id"] == result["scope"]["publication_id"]
        assert reference["evidence"]["run_id"] == result["scope"]["run_id"]
        assert reference["verified_utf8_bytes"] == reference["evidence"]["original_utf8_bytes"]
        assert reference["exact_text_sha256_verified"] is True
        assert reference["excerpt_window_verified"] is True
    assert len(json.dumps(result).encode()) < 32768
    assert "next_cursor" not in json.dumps(result)
    assert result["references"][0]["verified_utf8_bytes"] == 28


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("mismatch", "identity_mismatch_detected"),
        ("stale", "stale_publication_detected"),
        ("read_failure", "read_replacement_detected"),
        ("citation_failure", "citation_corruption_detected"),
    ],
)
def test_real_negative_boundary_discards_the_entire_result(
    tmp_path: Path, case: str, code: str
) -> None:
    module = consumer()
    source_root = assets(tmp_path / "assets")
    cfg = config(module, tmp_path / "data", source_root)
    asyncio.run(module.run_flow(cfg))
    with pytest.raises(module.CaseFailure) as failure:
        asyncio.run(module.run_negative(cfg, case))
    assert failure.value.code == code
    if case in {"read_failure", "citation_failure"}:
        evidence = json.loads((cfg.work_dir / f"{case}-boundary.json").read_text())
        assert evidence["first_reference_complete"] is True
        assert evidence["native_boundary_exercised"] is True
        assert evidence["successful_receipt_emitted"] is False


def test_reused_library_is_refused_without_overwrite(tmp_path: Path) -> None:
    module = consumer()
    source_root = assets(tmp_path / "assets")
    data = tmp_path / "data"
    data.mkdir()
    retained = data / "existing.sqlite"
    retained.write_bytes(b"retained")
    with pytest.raises(module.CaseFailure, match="work_directory_exists"):
        asyncio.run(module.run_flow(config(module, data, source_root)))
    assert retained.read_bytes() == b"retained"


def test_cli_command_does_not_block_the_consumer_workflow_deadline(tmp_path: Path) -> None:
    module = consumer()
    source_root = assets(tmp_path / "assets")
    slow_cli = tmp_path / "slow-mke"
    slow_cli.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(0.2)\nraise SystemExit(1)\n")
    slow_cli.chmod(0o700)
    cfg = replace(config(module, tmp_path / "data", source_root), mke=slow_cli)

    async def execute() -> None:
        async with asyncio.timeout(0.02):
            await module.run_flow(cfg)

    with pytest.raises(TimeoutError):
        asyncio.run(execute())


def test_cli_ask_packet_validation_rejects_changed_lineage(tmp_path: Path) -> None:
    module = consumer()
    source_root = assets(tmp_path / "assets")
    cfg = config(module, tmp_path / "data", source_root)
    asyncio.run(module.run_flow(cfg))
    stored = json.loads((cfg.work_dir / "cli-complete.json").read_text())
    corrupted = copy.deepcopy(stored)
    corrupted["evidence"][0]["evidence"]["run_id"] = "run_" + "0" * 32
    with pytest.raises(module.CaseFailure, match="cli_packet_invalid"):
        module.validate_ask(corrupted, stored["scope"], "needle")


def test_equal_length_wrong_cli_excerpt_discards_the_entire_native_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = consumer()
    cfg = config(module, tmp_path / "data", assets(tmp_path / "assets"))
    original = module.cli

    def corrupt_cli(cfg: Any, *args: str) -> Any:
        result = original(cfg, *args)
        if args[0] == "ask" and args[1] == "needle" and "--json" in args and result.returncode == 0:
            payload = json.loads(result.stdout)
            text = payload["evidence"][0]["excerpt"]["text"]
            payload["evidence"][0]["excerpt"]["text"] = "X" + text[1:]
            return module.processes.CommandResult(
                result.returncode, module.encoded(payload), result.stderr
            )
        return result

    monkeypatch.setattr(module, "cli", corrupt_cli)
    with pytest.raises(module.CaseFailure, match="cli_sdk_mismatch"):
        asyncio.run(module.run_flow(cfg))
    assert not (cfg.work_dir / "selected-pairs.json").exists()


def test_nonzero_internal_cli_retains_private_stdout_stderr(tmp_path: Path) -> None:
    module = consumer()
    root = tmp_path / "data"
    root.mkdir()
    failing = tmp_path / "failing-cli"
    failing.write_text(
        f"#!{sys.executable}\nimport sys\nprint('cli diagnostic')\n"
        "print('private cause',file=sys.stderr)\nraise SystemExit(7)\n"
    )
    failing.chmod(0o700)
    cfg = replace(config(module, root, tmp_path), mke=failing)
    result = module.cli(cfg, "ingest", "selected.pdf", "--json")
    assert result.returncode == 7
    diagnostic = json.loads((root / "diagnostics/cli.jsonl").read_text())
    assert diagnostic["stdout"] == "cli diagnostic\n" and diagnostic["stderr"] == "private cause\n"


@pytest.mark.parametrize("overflow", [False, True])
def test_sdk_stderr_prefix_is_retained_after_startup_timeout_or_overflow(
    tmp_path: Path, overflow: bool
) -> None:
    module = consumer()
    destination = tmp_path / "sdk-stderr.log"

    async def execute() -> None:
        async with module.DiagnosticStderrCapture(destination, 16) as capture:
            capture.write_end.write("startup cause" + ("x" * 30 if overflow else ""))
            capture.write_end.flush()
            with pytest.raises(
                module.pack.ProofError,
                match="command_output_exceeded" if overflow else "mcp_startup_timeout",
            ):
                await module.pack._deadline(asyncio.sleep(1), 0.05, "mcp_startup_timeout", capture)

    asyncio.run(execute())
    assert destination.read_bytes().startswith(b"startup cause")
    assert len(destination.read_bytes()) <= 16


def test_failed_consumer_keeps_phase_and_exception_without_partial_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = consumer()
    cfg = config(module, tmp_path / "data", assets(tmp_path / "assets"))
    cfg.work_dir.mkdir()
    error = RuntimeError("private transport diagnostic")
    module.record_exception(cfg, "sdk_startup", error)
    diagnostic = json.loads((cfg.work_dir / "diagnostics/failure.json").read_text())
    assert (
        diagnostic["phase"] == "sdk_startup"
        and "private transport diagnostic" in diagnostic["traceback"]
    )
    assert not capsys.readouterr().out


def test_real_sdk_startup_failure_retains_stderr_and_phase_without_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = consumer()
    stub = tmp_path / "startup-failure-mke"
    stub.write_text(
        f"#!{sys.executable}\nimport sys\n"
        "if 'mcp' in sys.argv:\n print('SDK startup cause',file=sys.stderr)\n raise SystemExit(1)\n"
    )
    stub.chmod(0o700)
    cfg = replace(config(module, tmp_path / "data", assets(tmp_path / "assets")), mke=stub)
    with pytest.raises(ExceptionGroup, match="unhandled errors"):
        asyncio.run(module.run_case(cfg, "flow"))
    logs = list((cfg.work_dir / "diagnostics").glob("sdk-*.stderr.log"))
    assert logs and any(b"SDK startup cause" in log.read_bytes() for log in logs)
    diagnostic = json.loads((cfg.work_dir / "diagnostics/failure.json").read_text())
    assert diagnostic["phase"] == "flow" and diagnostic["traceback"]
    assert not (cfg.work_dir / "selected-pairs.json").exists() and not capsys.readouterr().out


def test_declared_generator_is_deterministic_and_keeps_multibyte_pdf_text(tmp_path: Path) -> None:
    script = ROOT / "scripts/generate_source_evidence_installed_fixtures.py"
    assert script.is_file(), "independently named fixture generator is missing"
    generator = importlib.import_module("scripts.generate_source_evidence_installed_fixtures")
    generator.build_assets(tmp_path / "first")
    generator.build_assets(tmp_path / "second")
    for name in ("selected.pdf", "other.pdf", "manifest.json"):
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
    with pymupdf.open(tmp_path / "first/selected.pdf") as document:
        assert len(document) == 3
        text = cast(str, document[0].get_text())  # pyright: ignore[reportUnknownMemberType]
        assert isinstance(text, str) and text.strip() == "needle café selected page 1"
    manifest = json.loads((tmp_path / "first/manifest.json").read_text())
    assert {row["filename"] for row in manifest["sources"]} == {"selected.pdf", "other.pdf"}
