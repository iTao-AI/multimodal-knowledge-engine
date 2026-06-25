import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any, cast

import pytest

from mke.evaluation.chinese_protocol import (
    ChineseProtocolValidationError,
    load_chinese_retrieval_protocol,
    snapshot_chinese_retrieval_fixtures,
)

PROTOCOL = Path("tests/fixtures/retrieval-chinese-v1/protocol.json")


def _copy_protocol(tmp_path: Path) -> Path:
    root = tmp_path / "retrieval-chinese-v1"
    shutil.copytree(PROTOCOL.parent, root)
    return root / "protocol.json"


def _payload(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _adjudication(path: Path) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((path.parent / "qrel-adjudication.json").read_text(encoding="utf-8")),
    )


def _write_adjudication(path: Path, payload: dict[str, object]) -> None:
    adjudication_path = path.parent / "qrel-adjudication.json"
    _write(adjudication_path, payload)
    protocol = _payload(path)
    record = cast(dict[str, object], protocol["qrel_adjudication"])
    record["sha256"] = hashlib.sha256(adjudication_path.read_bytes()).hexdigest()
    _write(path, protocol)


def _queries(payload: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], payload["queries"])


def _documents(payload: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], payload["documents"])


def _qrels(query: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], query["qrels"])


def _reviewed_queries(payload: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], payload["queries"])


def _judgments(query: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], query["judgments"])


def test_load_checked_in_chinese_protocol_has_frozen_shape() -> None:
    protocol = load_chinese_retrieval_protocol(PROTOCOL)

    assert protocol.schema_version == "mke.retrieval_chinese_protocol.v1"
    assert protocol.protocol_id == "retrieval-chinese-v1"
    assert protocol.rank_probe_query_id == "zh-dev-exact-02"
    assert len(protocol.documents) == 5
    assert len(protocol.queries) == 48
    assert protocol.qrel_adjudication.review_status == "complete"
    assert protocol.qrel_adjudication.reviewed_query_count == 48
    assert protocol.qrel_adjudication.query_page_judgment_count == 1680


PROTOCOL_MUTATIONS: list[
    tuple[Callable[[dict[str, object]], object], str]
] = [
    (lambda payload: payload.update({"unexpected": True}), "unknown fields"),
    (lambda payload: payload.pop("queries"), "missing required fields"),
    (
        lambda payload: payload.update(
            {"schema_version": "mke.retrieval_chinese_protocol.v2"}
        ),
        "schema version is unsupported",
    ),
    (
        lambda payload: payload.update({"protocol_id": "UPPER"}),
        "protocol identifier is invalid",
    ),
    (
        lambda payload: _documents(payload)[0].update({"document_id": "UPPER"}),
        "document identifier is invalid",
    ),
    (
        lambda payload: _queries(payload)[0].update({"query_id": "UPPER"}),
        "query identifier is invalid",
    ),
    (
        lambda payload: _queries(payload)[0].update({"split": "other"}),
        "query split is invalid",
    ),
    (
        lambda payload: _queries(payload)[0].update({"category": "other"}),
        "query category is invalid",
    ),
    (
        lambda payload: _queries(payload)[0].update({"text": ""}),
        "query text is invalid",
    ),
    (
        lambda payload: _queries(payload)[0].update({"text": "?"}),
        "query text is invalid",
    ),
    (
        lambda payload: _queries(payload)[0].update({"text": "中" * 1001}),
        "query text is invalid",
    ),
    (
        lambda payload: _qrels(_queries(payload)[0])[0].update({"grade": True}),
        "qrel grade is invalid",
    ),
    (
        lambda payload: _qrels(_queries(payload)[0])[0].update({"grade": -1}),
        "qrel grade is invalid",
    ),
    (
        lambda payload: _qrels(_queries(payload)[0])[0].update({"grade": 3}),
        "qrel grade is invalid",
    ),
    (
        lambda payload: _qrels(_queries(payload)[0]).append(
            dict(_qrels(_queries(payload)[0])[0])
        ),
        "query qrel locators must be unique",
    ),
    (
        lambda payload: [
            item.update({"grade": 1})
            for item in _qrels(_queries(payload)[0])
            if item["grade"] == 2
        ],
        "answerable query requires grade 2",
    ),
    (
        lambda payload: _qrels(_queries(payload)[22]).append(
            {
                "document_id": "ub-service-core",
                "locator_kind": "page",
                "locator_start": 1,
                "locator_end": 1,
                "grade": 2,
            }
        ),
        "unanswerable query must not have qrels",
    ),
    (
        lambda payload: [
            item.update({"grade": 1})
            for item in _qrels(_queries(payload)[20])
            if item["grade"] == 0
        ],
        "hard-negative query requires grade 0",
    ),
    (
        lambda payload: _qrels(_queries(payload)[0])[0].update(
            {"document_id": "copyright-law"}
        ),
        "qrel split does not match query",
    ),
    (
        lambda payload: _queries(payload)[24].update(
            {"text": _queries(payload)[0]["text"]}
        ),
        "query text must be unique",
    ),
    (lambda payload: _queries(payload).pop(), "query count is invalid"),
    (lambda payload: _documents(payload).pop(), "document count is invalid"),
]


@pytest.mark.parametrize(
    ("mutation", "cause"),
    PROTOCOL_MUTATIONS,
)
def test_protocol_rejects_invalid_schema_and_semantics(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], object],
    cause: str,
) -> None:
    path = _copy_protocol(tmp_path)
    payload = _payload(path)
    mutation(payload)
    _write(path, payload)

    with pytest.raises(ChineseProtocolValidationError, match=cause):
        load_chinese_retrieval_protocol(path)


@pytest.mark.parametrize(
    "unsafe_path",
    (
        "/absolute.pdf",
        "../outside.pdf",
        "development/../outside.pdf",
        r"development\outside.pdf",
    ),
)
def test_protocol_rejects_unsafe_fixture_paths(
    tmp_path: Path, unsafe_path: str
) -> None:
    path = _copy_protocol(tmp_path)
    payload = _payload(path)
    primary = cast(dict[str, object], _documents(payload)[0]["primary_file"])
    primary["path"] = unsafe_path
    _write(path, payload)

    with pytest.raises(ChineseProtocolValidationError, match="fixture path is invalid"):
        load_chinese_retrieval_protocol(path)


def test_protocol_rejects_symlink_fixture(tmp_path: Path) -> None:
    path = _copy_protocol(tmp_path)
    fixture = path.parent / "development/ub-service-core-2.0-zh.pdf"
    outside = tmp_path / "outside.pdf"
    fixture.replace(outside)
    fixture.symlink_to(outside)

    with pytest.raises(ChineseProtocolValidationError, match="fixture path is invalid"):
        load_chinese_retrieval_protocol(path)


ADJUDICATION_MUTATIONS: list[
    tuple[Callable[[dict[str, object]], object], str]
] = [
    (
        lambda payload: payload.update({"review_date": True}),
        "qrel review date is invalid",
    ),
    (
        lambda payload: payload.update({"review_date": "2026-6-25"}),
        "qrel review date is invalid",
    ),
    (
        lambda payload: payload.update({"review_date": "2026-02-30"}),
        "qrel review date is invalid",
    ),
    (
        lambda payload: payload.update({"review_date": "2026-06-24"}),
        "qrel review date is invalid",
    ),
    (
        lambda payload: payload.update({"review_status": "draft"}),
        "qrel review status is invalid",
    ),
    (
        lambda payload: _reviewed_queries(payload).pop(),
        "qrel review query coverage is invalid",
    ),
    (
        lambda payload: _judgments(_reviewed_queries(payload)[0]).pop(),
        "qrel review page coverage is invalid",
    ),
    (
        lambda payload: _judgments(_reviewed_queries(payload)[0]).append(
            dict(_judgments(_reviewed_queries(payload)[0])[0])
        ),
        "qrel review page coverage is invalid",
    ),
    (
        lambda payload: _judgments(_reviewed_queries(payload)[0]).reverse(),
        "qrel review page order is invalid",
    ),
    (
        lambda payload: _judgments(_reviewed_queries(payload)[0])[0].update(
            {"grade": 3}
        ),
        "qrel review grade is invalid",
    ),
    (
        lambda payload: _judgments(_reviewed_queries(payload)[0])[12].update(
            {"grade": "non_relevant"}
        ),
        "qrel review does not match protocol qrels",
    ),
    (
        lambda payload: _reviewed_queries(payload)[0].update({"decision_basis": ""}),
        "decision basis is invalid",
    ),
    (
        lambda payload: _reviewed_queries(payload)[0].update(
            {"decision_basis": "x" * 501}
        ),
        "decision basis is invalid",
    ),
    (
        lambda payload: _reviewed_queries(payload)[0].update(
            {"decision_basis": "/Users/example/private"}
        ),
        "decision basis is not public-safe",
    ),
    (
        lambda payload: _reviewed_queries(payload)[0].update(
            {"decision_basis": "API_KEY=secret"}
        ),
        "decision basis is not public-safe",
    ),
    (
        lambda payload: _reviewed_queries(payload)[0].update(
            {"decision_basis": "Traceback (most recent call last)"}
        ),
        "decision basis is not public-safe",
    ),
]


@pytest.mark.parametrize(
    ("mutation", "cause"),
    ADJUDICATION_MUTATIONS,
)
def test_protocol_rejects_invalid_qrel_adjudication(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], object],
    cause: str,
) -> None:
    path = _copy_protocol(tmp_path)
    payload = _adjudication(path)
    mutation(payload)
    _write_adjudication(path, payload)

    with pytest.raises(ChineseProtocolValidationError, match=cause):
        load_chinese_retrieval_protocol(path)


def test_protocol_rejects_adjudication_checksum_mismatch(tmp_path: Path) -> None:
    path = _copy_protocol(tmp_path)
    adjudication_path = path.parent / "qrel-adjudication.json"
    adjudication_path.write_bytes(adjudication_path.read_bytes() + b"\n")

    with pytest.raises(
        ChineseProtocolValidationError, match="qrel adjudication checksum does not match"
    ):
        load_chinese_retrieval_protocol(path)


def test_protocol_rejects_missing_changed_and_duplicate_fixture_bytes(
    tmp_path: Path,
) -> None:
    missing_path = _copy_protocol(tmp_path / "missing")
    (missing_path.parent / "development/adversarial.pdf").unlink()
    with pytest.raises(ChineseProtocolValidationError, match="fixture file is missing"):
        load_chinese_retrieval_protocol(missing_path)

    changed_path = _copy_protocol(tmp_path / "changed")
    changed = changed_path.parent / "development/adversarial.pdf"
    changed.write_bytes(changed.read_bytes() + b"x")
    with pytest.raises(
        ChineseProtocolValidationError, match="fixture byte size does not match"
    ):
        load_chinese_retrieval_protocol(changed_path)

    duplicate_path = _copy_protocol(tmp_path / "duplicate")
    payload = _payload(duplicate_path)
    first = cast(dict[str, object], _documents(payload)[0]["primary_file"])
    second = cast(dict[str, object], _documents(payload)[1]["primary_file"])
    duplicate = duplicate_path.parent / str(second["path"])
    source = duplicate_path.parent / str(first["path"])
    duplicate.write_bytes(source.read_bytes())
    second["bytes"] = first["bytes"]
    second["sha256"] = first["sha256"]
    _write(duplicate_path, payload)
    with pytest.raises(
        ChineseProtocolValidationError, match="fixture checksums must be unique"
    ):
        load_chinese_retrieval_protocol(duplicate_path)


def test_snapshot_preserves_verified_bytes_and_rejects_existing_target(
    tmp_path: Path,
) -> None:
    protocol = load_chinese_retrieval_protocol(PROTOCOL)
    snapshot = snapshot_chinese_retrieval_fixtures(protocol, tmp_path / "snapshot")

    assert snapshot.root == (tmp_path / "snapshot").resolve()
    for document in snapshot.documents:
        path = snapshot.resolve(document.primary_file)
        assert path.stat().st_size == document.primary_file.bytes
        assert hashlib.sha256(path.read_bytes()).hexdigest() == document.primary_file.sha256

    with pytest.raises(ChineseProtocolValidationError, match="snapshot target exists"):
        snapshot_chinese_retrieval_fixtures(protocol, tmp_path / "snapshot")


def test_snapshot_rejects_fixture_mutation_during_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _copy_protocol(tmp_path)
    protocol = load_chinese_retrieval_protocol(path)
    source = protocol.resolve(protocol.documents[0].primary_file)
    original_open = Path.open
    mutation_count = 0

    def mutating_open(
        target: Path,
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> IO[Any]:
        nonlocal mutation_count
        if target == source and mode == "rb":
            mutation_count += 1
            with original_open(target, "ab") as stream:
                stream.write(b"x")
        return original_open(
            target,
            mode,
            buffering=buffering,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )

    monkeypatch.setattr(Path, "open", mutating_open)

    with pytest.raises(
        ChineseProtocolValidationError, match="fixture changed during snapshot"
    ):
        snapshot_chinese_retrieval_fixtures(protocol, tmp_path / "snapshot")
    assert mutation_count == 1
    assert not (tmp_path / "snapshot").exists()
