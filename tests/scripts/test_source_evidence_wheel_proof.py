from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/source_evidence_wheel_proof.py"


def proof() -> Any:
    assert SCRIPT.is_file(), "single-Source wheel controller is missing"
    return importlib.import_module("scripts.source_evidence_wheel_proof")


def git(repository: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=repository, stderr=subprocess.DEVNULL)


def repository(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repository"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname="test"\nversion="0.1.0"\n')
    (root / "uv.lock").write_text("version=1\n")
    git(root, "init", "--quiet", "--initial-branch=main")
    git(root, "add", "pyproject.toml", "uv.lock")
    git(
        root,
        "-c",
        "user.name=Proof Test",
        "-c",
        "user.email=proof@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "declared",
    )
    return root, git(root, "rev-parse", "HEAD").decode().strip()


def args(root: Path, commit: str, target: Path) -> argparse.Namespace:
    return argparse.Namespace(
        repository=root,
        source_commit=commit,
        work_dir=target,
        python=[Path(sys.executable), Path(sys.executable)],
    )


@pytest.mark.parametrize("change", ["invalid", "different", "dirty", "untracked"])
def test_declared_commit_must_be_the_clean_stable_head_before_side_effects(
    tmp_path: Path, change: str
) -> None:
    module = proof()
    root, commit = repository(tmp_path)
    target = tmp_path / "external"
    if change == "invalid":
        commit = "main"
    elif change == "different":
        commit = "0" * 40
    elif change == "dirty":
        (root / "uv.lock").write_text("changed")
    else:
        (root / "unexpected").write_text("untracked")
    with pytest.raises(module.ProofFailure, match="source_commit_invalid"):
        module.run(args(root, commit, target))
    assert not target.exists()


def test_end_binding_detects_a_changed_commit(tmp_path: Path) -> None:
    module = proof()
    root, commit = repository(tmp_path)
    git(
        root,
        "-c",
        "user.name=Proof Test",
        "-c",
        "user.email=proof@example.invalid",
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "later",
    )
    with pytest.raises(module.ProofFailure, match="source_commit_changed"):
        module.check_source(root, commit, "source_commit_changed")


def test_existing_work_directory_is_preserved(tmp_path: Path) -> None:
    module = proof()
    root, commit = repository(tmp_path)
    target = tmp_path / "external"
    target.mkdir()
    retained = target / "receipt.json"
    retained.write_bytes(b"retained")
    with pytest.raises(module.ProofFailure, match="work_directory_exists"):
        module.run(args(root, commit, target))
    assert retained.read_bytes() == b"retained"


@pytest.mark.parametrize("alias", [False, True])
def test_repository_work_directory_and_identity_alias_are_rejected(
    tmp_path: Path, alias: bool
) -> None:
    module = proof()
    root, commit = repository(tmp_path)
    parent = root
    if alias:
        parent = tmp_path / "repository-alias"
        parent.symlink_to(root, target_is_directory=True)
    target = parent / "proof"
    with pytest.raises(module.ProofFailure, match="external_work_directory_required"):
        module.run(args(root, commit, target))
    assert not target.exists()


@pytest.mark.parametrize("missing", [False, True])
def test_wrong_or_missing_existing_interpreters_cannot_create_environments(
    tmp_path: Path, missing: bool
) -> None:
    module = proof()
    root, commit = repository(tmp_path)
    target = tmp_path / "external"
    values = args(root, commit, target)
    if missing:
        values.python[1] = tmp_path / "missing-python"
    with pytest.raises(module.ProofFailure, match="python_interpreter_unavailable"):
        module.run(values)
    assert not target.exists()


def flow_receipt() -> tuple[dict[str, Any], dict[str, str]]:
    assets = {"selected": "a" * 64, "other": "b" * 64}
    scope: dict[str, Any] = {
        "schema_version": "mke.source_search_scope.v1",
        "source_id": "src_selected",
        "publication_id": "pub_selected",
        "publication_revision": 1,
        "run_id": "run_selected",
        "content_fingerprint": "sha256:" + assets["selected"],
    }
    references: list[dict[str, Any]] = []
    for page in range(1, 4):
        text = f"needle café selected page {page}".encode()
        evidence = {key: value for key, value in scope.items() if key != "schema_version"}
        evidence.update(
            evidence_id=f"ev_{page}",
            locator={"kind": "page", "start": page, "end": page},
            evidence_text_sha256="sha256:" + hashlib.sha256(text).hexdigest(),
            original_utf8_bytes=len(text),
        )
        references.append(
            {
                "evidence": evidence,
                "read": {"tool": "read_evidence_v1", "evidence_id": f"ev_{page}"},
                "verified_utf8_bytes": len(text),
                "exact_text_sha256_verified": True,
                "excerpt_window_verified": True,
            }
        )
    return {
        "schema_version": "mke.source_evidence_installed_consumer.v1",
        "status": "passed",
        "tool_count": 15,
        "source_count": 2,
        "scope": scope,
        "authority_snapshot": {
            "schema_version": "mke.active_authority_snapshot.v1",
            "active_set_fingerprint": "sha256:" + "c" * 64,
            "observation": {
                "schema_version": "mke.active_publication_observation.v1",
                "library_id": "local",
                "state": "active",
                "source_count": 2,
                "active_publication_count": 2,
                "active_evidence_count": 8,
            },
        },
        "references": references,
        "asset_sha256": assets,
        "cases": {
            "first_page": "more_available",
            "complete": "complete",
            "selected_empty": "insufficient_evidence",
            "unrelated_match": True,
            "cli_sdk_equal": True,
            "utf8_digest_and_excerpt_verified": True,
        },
    }, assets


def test_consumer_flow_receipt_is_strict_and_binds_all_lineage_and_exact_fixture_text() -> None:
    module = proof()
    payload, assets = flow_receipt()
    result = module.processes.CommandResult(0, module.encoded(payload), b"")
    assert module.validate_consumer(result, "flow", assets) == payload


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "tool_count",
        "scope",
        "lineage",
        "digest",
        "read",
        "bytes",
        "prefix",
        "duplicate",
        "bool",
    ],
)
def test_invalid_success_claim_is_never_accepted(mutation: str) -> None:
    module = proof()
    payload, assets = flow_receipt()
    if mutation == "extra":
        payload["partial"] = True
    elif mutation == "tool_count":
        payload["tool_count"] = 14
    elif mutation == "scope":
        payload["scope"]["content_fingerprint"] = "sha256:" + assets["other"]
    elif mutation == "lineage":
        payload["references"][1]["evidence"]["run_id"] = "run_other"
    elif mutation == "digest":
        payload["references"][1]["evidence"]["evidence_text_sha256"] = "sha256:" + "0" * 64
    elif mutation == "read":
        payload["references"][1]["read"]["evidence_id"] = "ev_other"
    elif mutation == "bytes":
        payload["references"][1]["verified_utf8_bytes"] -= 1
    elif mutation == "prefix":
        payload["references"] = payload["references"][:1]
    elif mutation == "duplicate":
        payload["references"][1] = copy.deepcopy(payload["references"][0])
    else:
        payload["cases"]["cli_sdk_equal"] = 1
    with pytest.raises(module.ProofFailure, match="consumer_payload_invalid"):
        module.validate_consumer(
            module.processes.CommandResult(0, module.encoded(payload), b""), "flow", assets
        )


@pytest.mark.parametrize("case", ["mismatch", "stale", "read_failure", "citation_failure"])
def test_expected_failure_boundary_requires_exact_redacted_shape_and_nonzero_exit(
    case: str,
) -> None:
    module = proof()
    payload = {
        "schema_version": "mke.source_evidence_installed_consumer.v1",
        "status": "failed",
        "code": module.CASE_CODES[case],
    }
    assert (
        module.validate_consumer(
            module.processes.CommandResult(1, module.encoded(payload), b""), case, {}
        )
        == payload
    )
    changes: list[tuple[dict[str, Any], int]] = [
        (payload, 0),
        ({**payload, "references": []}, 1),
        ({**payload, "code": "consumer_failed"}, 1),
    ]
    for changed, status in changes:
        with pytest.raises(module.ProofFailure, match="negative_boundary_failed"):
            module.validate_consumer(
                module.processes.CommandResult(status, module.encoded(changed), b""), case, {}
            )


def test_copy_assets_uses_git_bytes_and_detects_post_copy_changes(tmp_path: Path) -> None:
    module = proof()
    root, _ = repository(tmp_path)
    for relative in module.ASSET_PATHS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    git(root, "add", *module.ASSET_PATHS)
    git(
        root,
        "-c",
        "user.name=Proof Test",
        "-c",
        "user.email=proof@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "assets",
    )
    commit = git(root, "rev-parse", "HEAD").decode().strip()
    destination = tmp_path / "copied"
    expected = module.copy_assets(root, commit, destination)
    assert expected == {
        relative: hashlib.sha256((root / relative).read_bytes()).hexdigest()
        for relative in module.ASSET_PATHS
    }
    module.verify_assets(destination, expected)
    (destination / "assets/selected.pdf").write_bytes(b"changed")
    with pytest.raises(module.ProofFailure, match="asset_identity_invalid"):
        module.verify_assets(destination, expected)


def test_failed_command_keeps_bounded_private_diagnostics_and_safe_code(tmp_path: Path) -> None:
    module = proof()
    log = tmp_path / "commands.jsonl"
    runner = module.Runner(tmp_path, log)
    with pytest.raises(module.ProofFailure, match="wheel_build_failed"):
        runner.checked(
            [sys.executable, "-c", "print('private diagnostic');raise SystemExit(7)"],
            "wheel_build_failed",
        )
    record = json.loads(log.read_text())
    assert record["returncode"] == 7 and record["stdout"] == "private diagnostic\n"
    assert record["code"] == "wheel_build_failed"


def test_oversized_subprocess_output_is_stopped_with_a_retained_terminal_diagnostic(
    tmp_path: Path,
) -> None:
    module = proof()
    log = tmp_path / "commands.jsonl"
    runner = module.Runner(tmp_path, log)
    with pytest.raises(module.ProofFailure, match="command_output_exceeded"):
        runner.call([sys.executable, "-c", "import os;os.write(1,b'x'*(2*1024*1024+1))"])
    diagnostic = json.loads(log.read_text())
    assert diagnostic["code"] == "command_output_exceeded"
    assert len(diagnostic["stdout"].encode()) == 2 * 1024 * 1024


def test_bounded_timeout_error_keeps_captured_prefix_for_m3_diagnostics(tmp_path: Path) -> None:
    module = proof()
    with pytest.raises(module.processes.ControllerError, match="command_timed_out") as failure:
        module.processes.run_bounded(
            [
                sys.executable,
                "-c",
                "import sys,time;print('startup cause',flush=True);"
                "print('stderr cause',file=sys.stderr,flush=True);time.sleep(3)",
            ],
            cwd=tmp_path,
            env=module.Runner(tmp_path).environment,
            timeout_seconds=0.2,
            max_stdout_bytes=32,
            max_stderr_bytes=32,
        )
    assert failure.value.stdout == b"startup cause\n" and failure.value.stderr == b"stderr cause\n"


def test_cleanup_failure_does_not_remove_or_accept_a_retained_non_directory(tmp_path: Path) -> None:
    module = proof()
    temporary = tmp_path / "temporary"
    temporary.write_bytes(b"retained")
    with pytest.raises(module.ProofFailure, match="cleanup_failed"):
        module.cleanup_temporary(temporary)
    assert temporary.read_bytes() == b"retained"


def test_main_failure_is_one_bounded_redacted_object(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = proof()
    assert (
        module.main(
            [
                "--repository",
                str(tmp_path),
                "--source-commit",
                "main",
                "--python",
                sys.executable,
                "--python",
                sys.executable,
                "--work-dir",
                str(tmp_path / "external"),
            ]
        )
        == 1
    )
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out) == {
        "schema_version": "mke.source_evidence_wheel_proof.v1",
        "status": "failed",
        "code": "source_commit_invalid",
    }
    assert len(output.out.encode()) < 32768 and str(tmp_path) not in output.out
