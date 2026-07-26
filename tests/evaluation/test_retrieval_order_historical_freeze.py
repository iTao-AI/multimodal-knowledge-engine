from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

FROZEN_SHA256 = {
    "benchmarks/retrieval/retrieval-eval-v1-baseline.json": (
        "c2518b2f95a91eb91f2f83953965e186711e2b3d93725e9d83617d0fde530a88"
    ),
    "benchmarks/retrieval/numeric-grouping-v1-comparison.json": (
        "98fb1f61d824d7b307d3a2745b49ed972fc6d4af292833098a15b13b860ddae9"
    ),
    "benchmarks/retrieval/retrieval-chinese-v1-baseline.json": (
        "7187d999fc98f2ed0f405756f0a4b02ab4dcbb14fdb8d49d8bfd1ad205295828"
    ),
    "benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json": (
        "5cb54cc7baea939b439c617ee917badff64bface2f2fe5a85b128185fdf3ed3c"
    ),
    "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json": (
        "a992059a24b5afbd26c22f71916d7266ada9c3e9ed1fe1354447c7f5f2c40d26"
    ),
    "benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json": (
        "6b77d29fa3b8badd7400e53fa96cd544ecf84d51563170bfc44d56975ff470c3"
    ),
    "benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json": (
        "e22e561618726c339bd955d1c7cfcf573080c251549e6a89c8187251d6011e36"
    ),
    "tests/fixtures/retrieval-eval-v1.json": (
        "a65b33e011c7a39245a2202fa741e57a268b42da9f68d8da0725955834dd4761"
    ),
    "tests/fixtures/retrieval-numeric-v1/protocol-lock.json": (
        "17c424e49237deba600fef70d47da803fb73f72d2ee65995fc155dc96e22da60"
    ),
    "tests/fixtures/retrieval-chinese-v1/protocol.json": (
        "00f72934018a52b5b5f5591fba119050882aee9b782e5dac199702b0cf995944"
    ),
    "tests/fixtures/retrieval-dense-v1/protocol-lock.json": (
        "afca992a7115fdb06e620168d14f8d09055f231c061b59f82c69f0be2a6e4251"
    ),
    "tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json": (
        "2407fb3d9abfe1a1127c5d9a600dea529c32c308a42cbd3622c52211d314a716"
    ),
    "tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json": (
        "6983eb5243493176d6cf97a5e7b5ae888aac9885c25e945583bc291aacf253b1"
    ),
    "benchmarks/retrieval/retrieval-order-v1-current-runtime-observation.json": (
        "1a98e4e6c4eabc01663991646aac46e4a73033eef8a7e17a27db2e0fdce71691"
    ),
}


def _source_identity_module() -> Any:
    return importlib.import_module("mke.evaluation.source_identity")


def _identity(files: list[dict[str, object]]) -> dict[str, object]:
    encoded = json.dumps(
        files, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "files": files}


def test_historical_artifact_and_protocol_bytes_are_frozen() -> None:
    assert {
        path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for path in FROZEN_SHA256
    } == FROZEN_SHA256
    canonical = json.dumps(
        FROZEN_SHA256,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == (
        "4462b830a1340e6f8c08ae01082ba82212d95976057767f60ee29671cc965922"
    )


def test_current_source_builder_includes_only_explicit_paths(
    tmp_path: Path,
) -> None:
    module = _source_identity_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "recorded.py").write_text("recorded = True\n")
    (tmp_path / "src" / "unrelated.py").write_text("unrelated = True\n")

    identity = module.build_source_identity(
        tmp_path, ("src/recorded.py",)
    )

    assert [item["path"] for item in identity["files"]] == ["src/recorded.py"]


@pytest.mark.parametrize(
    "case",
    [
        "absolute_path",
        "parent_path",
        "duplicate_path",
        "negative_bytes",
        "bool_bytes",
        "uppercase_sha256",
        "wrong_source_digest",
        "extra_file_field",
        "extra_source_field",
    ],
)
def test_recorded_source_identity_rejects_noncanonical_values(
    case: str,
) -> None:
    module = _source_identity_module()
    value = _identity(
        [{"path": "src/recorded.py", "bytes": 0, "sha256": "0" * 64}]
    )
    files = cast(list[dict[str, object]], value["files"])
    if case == "absolute_path":
        files[0]["path"] = "/absolute.py"
    elif case == "parent_path":
        files[0]["path"] = "../escape.py"
    elif case == "duplicate_path":
        files.append(dict(files[0]))
    elif case == "negative_bytes":
        files[0]["bytes"] = -1
    elif case == "bool_bytes":
        files[0]["bytes"] = True
    elif case == "uppercase_sha256":
        files[0]["sha256"] = "A" * 64
    elif case == "wrong_source_digest":
        value["sha256"] = "0" * 64
    elif case == "extra_file_field":
        files[0]["unexpected"] = True
    else:
        value["unexpected"] = True

    with pytest.raises(ValueError):
        module.validate_recorded_source_identity(value)


def test_recorded_file_identity_requires_expected_path() -> None:
    module = _source_identity_module()
    value = {"path": "src/recorded.py", "bytes": 0, "sha256": "0" * 64}

    with pytest.raises(ValueError):
        module.validate_recorded_file_identity(
            value, expected_path="src/other.py"
        )
