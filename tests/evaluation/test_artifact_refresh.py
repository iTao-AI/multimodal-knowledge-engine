import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from mke.evaluation.artifact_refresh import (
    ArtifactRefreshError,
    recover_artifact_refresh,
    refresh_artifact_set,
)
from mke.evaluation.chinese_report import render_chinese_retrieval_json
from mke.evaluation.chinese_runner import run_chinese_retrieval_evaluation
from mke.evaluation.cjk_lexical_comparison import (
    render_cjk_lexical_comparison_json,
    run_cjk_lexical_comparison,
)
from mke.evaluation.numeric_comparison import (
    refresh_numeric_protocol_scope,
    render_numeric_comparison_json,
    run_numeric_comparison,
)
from mke.evaluation.report import render_retrieval_json_report
from mke.evaluation.runner import run_retrieval_evaluation

TARGETS = (
    "benchmarks/retrieval/retrieval-eval-v1-baseline.json",
    "tests/fixtures/retrieval-numeric-v1/protocol-lock.json",
    "benchmarks/retrieval/numeric-grouping-v1-comparison.json",
    "benchmarks/retrieval/retrieval-chinese-v1-baseline.json",
    "benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json",
)


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for directory in (
        ".github/workflows",
        "src",
        "tests/fixtures",
        "benchmarks",
    ):
        shutil.copytree(Path(directory), root / directory)
    for file_name in ("pyproject.toml", "uv.lock"):
        shutil.copy2(file_name, root / file_name)
    return root


def _observations(root: Path, tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    e1 = tmp_path / "e1.json"
    e1.write_text(
        render_retrieval_json_report(
            run_retrieval_evaluation(
                root / "tests/fixtures/retrieval-eval-v1.json"
            )
        ),
        encoding="utf-8",
    )
    protocol = (
        root
        / "tests/fixtures/retrieval-numeric-v1/.protocol-lock.observation.json"
    )
    protocol.write_bytes(
        (
            root / "tests/fixtures/retrieval-numeric-v1/protocol-lock.json"
        ).read_bytes()
    )
    refresh_numeric_protocol_scope(
        protocol_path=protocol,
        repository_root=root,
    )
    e2 = tmp_path / "e2.json"
    e2.write_text(
        render_numeric_comparison_json(run_numeric_comparison(protocol)),
        encoding="utf-8",
    )
    protocol.unlink()
    e3 = tmp_path / "e3.json"
    e3.write_text(
        render_chinese_retrieval_json(
            run_chinese_retrieval_evaluation(
                root / "tests/fixtures/retrieval-chinese-v1/protocol.json"
            )
        ),
        encoding="utf-8",
    )
    e3b = tmp_path / "e3b.json"
    e3b.write_text(
        render_cjk_lexical_comparison_json(
            run_cjk_lexical_comparison(
                root / "tests/fixtures/retrieval-chinese-v1/protocol.json"
            )
        ),
        encoding="utf-8",
    )
    return e1, e2, e3, e3b


def test_refresh_artifact_set_replaces_and_validates_all_five_targets(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    e1, e2, e3, e3b = _observations(root, tmp_path)

    manifest = refresh_artifact_set(
        repository_root=root,
        e1_observed_path=e1,
        e2_observed_path=e2,
        e3_observed_path=e3,
        e3b_observed_path=e3b,
    )

    assert set(manifest) == set(TARGETS)
    assert all(len(value) == 64 for value in manifest.values())
    assert not (root / ".mke-retrieval-artifact-refresh").exists()


def test_refresh_artifact_set_rolls_back_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repository(tmp_path)
    e1, e2, e3, e3b = _observations(root, tmp_path)
    targets = tuple(root / relative for relative in TARGETS)
    before = {path: path.read_bytes() for path in targets}
    original_replace = os.replace

    def failing_replace(source: Any, target: Any) -> None:
        if Path(os.fsdecode(target)) == root / TARGETS[4]:
            raise OSError("injected replacement failure")
        original_replace(source, target)

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(ArtifactRefreshError):
        refresh_artifact_set(
            repository_root=root,
            e1_observed_path=e1,
            e2_observed_path=e2,
            e3_observed_path=e3,
            e3b_observed_path=e3b,
        )

    assert {path: path.read_bytes() for path in targets} == before


def test_recover_restores_checksum_verified_e3b_backup(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    transaction = root / ".mke-retrieval-artifact-refresh"
    backup = transaction / "backups/4"
    backup.parent.mkdir(parents=True)
    target = root / "benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json"
    original = target.read_bytes()
    backup.write_bytes(original)
    target.write_text("partial", encoding="utf-8")
    journal = {
        "schema_version": "mke.retrieval_artifact_refresh_journal.v1",
        "targets": [
            {
                "path": target.relative_to(root).as_posix(),
                "existed": True,
                "backup": backup.relative_to(transaction).as_posix(),
                "original_sha256": __import__("hashlib").sha256(original).hexdigest(),
                "staged": "staged/4",
                "staged_sha256": "0" * 64,
                "replaced": True,
            }
        ],
    }
    (transaction / "journal.json").write_text(
        json.dumps(journal), encoding="utf-8"
    )

    recover_artifact_refresh(root)

    assert target.read_bytes() == original
    assert not transaction.exists()


def test_refresh_artifact_set_rolls_back_when_e3b_observation_changes_semantics(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    e1, e2, e3, e3b = _observations(root, tmp_path)
    before = {root / relative: (root / relative).read_bytes() for relative in TARGETS}
    observed = json.loads(e3b.read_text(encoding="utf-8"))
    observed["candidate_status"] = "failed"
    e3b.write_text(json.dumps(observed, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ArtifactRefreshError):
        refresh_artifact_set(
            repository_root=root,
            e1_observed_path=e1,
            e2_observed_path=e2,
            e3_observed_path=e3,
            e3b_observed_path=e3b,
        )

    assert {path: path.read_bytes() for path in before} == before
