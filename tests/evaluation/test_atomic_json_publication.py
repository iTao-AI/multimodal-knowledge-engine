from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest


def _module() -> Any:
    return importlib.import_module(
        "mke.evaluation._atomic_json_publication"
    )


def _content(value: str = "candidate") -> bytes:
    return (
        json.dumps(
            {
                "schema_version": "mke.test_atomic.v1",
                "value": value,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _validate(value: object) -> None:
    payload = cast(dict[str, object], value)
    if (
        not isinstance(value, dict)
        or payload.get("schema_version") != "mke.test_atomic.v1"
        or set(payload) != {"schema_version", "value"}
    ):
        raise ValueError


def _invalid_readback(path: Path) -> bytes:
    del path
    return b"{}"


def _raise_private(*args: object, **kwargs: object) -> NoReturn:
    del args, kwargs
    raise OSError("private")


def _raise_private_path(path: Path) -> NoReturn:
    del path
    raise OSError("private")


def _terminal_next_step(result: object) -> str:
    return cast(Any, result).next_step


def test_atomic_publication_exclusive_creates_complete_bytes(
    tmp_path: Path,
) -> None:
    module = _module()
    destination = tmp_path / "artifact.json"
    content = _content()

    result = module.publish_json_no_replace(
        destination,
        content,
        validate=_validate,
    )

    assert destination.read_bytes() == content
    assert result.output_state == "complete_visible"
    assert result.publication_outcome == "published"
    assert result.sha256 == module.sha256_bytes(content)
    assert result.problem is None
    assert list(tmp_path.iterdir()) == [destination]


def test_preexisting_complete_destination_is_never_replaced(
    tmp_path: Path,
) -> None:
    module = _module()
    destination = tmp_path / "artifact.json"
    existing = _content("existing")
    destination.write_bytes(existing)

    result = module.publish_json_no_replace(
        destination,
        _content("candidate"),
        validate=_validate,
    )

    assert destination.read_bytes() == existing
    assert result.output_state == "complete_preexisting"
    assert result.publication_outcome == "not_attempted"
    assert result.sha256 == module.sha256_bytes(existing)
    assert result.problem == "retrieval_order_output_exists"
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize(
    "helper",
    [
        "_write_bytes",
        "_fsync_file",
        "_readback_bytes",
    ],
)
def test_failure_before_visibility_leaves_destination_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    helper: str,
) -> None:
    module = _module()
    destination = tmp_path / "artifact.json"
    if helper == "_readback_bytes":
        monkeypatch.setattr(module, helper, _invalid_readback)
    else:
        monkeypatch.setattr(module, helper, _raise_private)

    result = module.publish_json_no_replace(
        destination,
        _content(),
        validate=_validate,
    )

    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []
    assert result.output_state == "absent"
    assert result.publication_outcome == "failed_before_visibility"
    assert result.problem == "retrieval_order_publication_failed"
    assert "private" not in repr(result)
    assert str(tmp_path) not in repr(result)


def test_no_replace_race_retains_complete_winner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    destination = tmp_path / "artifact.json"
    winner = _content("winner")

    def race(temporary: Path, target: Path) -> None:
        del temporary
        target.write_bytes(winner)
        raise FileExistsError

    monkeypatch.setattr(module, "_publish_no_replace", race)

    result = module.publish_json_no_replace(
        destination,
        _content("candidate"),
        validate=_validate,
    )

    assert destination.read_bytes() == winner
    assert result.output_state == "complete_preexisting"
    assert result.publication_outcome == "not_attempted"
    assert result.sha256 == module.sha256_bytes(winner)
    assert list(tmp_path.iterdir()) == [destination]


def test_directory_fsync_failure_retains_complete_visible_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    destination = tmp_path / "artifact.json"
    content = _content()
    monkeypatch.setattr(module, "_fsync_directory", _raise_private_path)

    result = module.publish_json_no_replace(
        destination,
        content,
        validate=_validate,
    )

    assert destination.read_bytes() == content
    assert result.output_state == "complete_visible"
    assert result.publication_outcome == "durability_unconfirmed"
    assert result.problem == "retrieval_order_publication_durability_unconfirmed"
    assert _terminal_next_step(result) == "do_not_retry_visible_output"
    assert "private" not in repr(result)
    assert str(tmp_path) not in repr(result)
    assert list(tmp_path.iterdir()) == [destination]


def test_invalid_json_is_rejected_before_temporary_creation(
    tmp_path: Path,
) -> None:
    module = _module()
    destination = tmp_path / "artifact.json"

    result = module.publish_json_no_replace(
        destination,
        b"{}",
        validate=_validate,
    )

    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []
    assert result.output_state == "not_applicable"
    assert result.publication_outcome == "not_attempted"
    assert result.problem == "retrieval_order_output_invalid"


def test_publish_then_oserror_is_classified_as_visible_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    destination = tmp_path / "artifact.json"
    content = _content()

    def publish_then_fail(temporary: Path, target: Path) -> None:
        module.os.link(temporary, target)
        raise OSError("private")

    monkeypatch.setattr(module, "_publish_no_replace", publish_then_fail)

    result = module.publish_json_no_replace(
        destination,
        content,
        validate=_validate,
    )

    assert destination.read_bytes() == content
    assert result.output_state == "complete_visible"
    assert result.publication_outcome == "durability_unconfirmed"
    assert result.problem == "retrieval_order_publication_durability_unconfirmed"
    assert result.next_step == "do_not_retry_visible_output"
    assert "private" not in repr(result)


def test_publish_exception_with_different_valid_winner_is_preexisting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    destination = tmp_path / "artifact.json"
    winner = _content("winner")

    def publish_winner_then_fail(temporary: Path, target: Path) -> None:
        del temporary
        target.write_bytes(winner)
        raise OSError("private")

    monkeypatch.setattr(
        module,
        "_publish_no_replace",
        publish_winner_then_fail,
    )

    result = module.publish_json_no_replace(
        destination,
        _content("candidate"),
        validate=_validate,
    )

    assert destination.read_bytes() == winner
    assert result.output_state == "complete_preexisting"
    assert result.publication_outcome == "not_attempted"
    assert result.problem == "retrieval_order_output_exists"


def test_publish_exception_with_invalid_visible_output_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    destination = tmp_path / "artifact.json"

    def publish_invalid_then_fail(temporary: Path, target: Path) -> None:
        del temporary
        target.write_bytes(b"{}")
        raise OSError("private")

    monkeypatch.setattr(
        module,
        "_publish_no_replace",
        publish_invalid_then_fail,
    )

    result = module.publish_json_no_replace(
        destination,
        _content(),
        validate=_validate,
    )

    assert destination.read_bytes() == b"{}"
    assert result.output_state == "not_applicable"
    assert result.publication_outcome == "durability_unconfirmed"
    assert result.problem == "retrieval_order_publication_failed"
    assert result.next_step == "do_not_retry_visible_output"
    assert "private" not in repr(result)
