import hashlib
import json
from pathlib import Path

import fitz

FIXTURES = Path(__file__).parents[1] / "fixtures"
MANIFEST = FIXTURES / "retrieval-eval-v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_retrieval_eval_corpus_matches_approved_bytes_and_text_layers() -> None:
    expected = {
        "eval/retrieval/usgs-volcano-hazards.pdf": (
            563382,
            "bdb8a5b6c648194e0fcc6f932b70976350bdc864c8187632c47f0cb64a21da4e",
            (5842, 8626),
        ),
        "eval/retrieval/usgs-water-use-2005.pdf": (
            400168,
            "ef27346a9f2eab19d438a0740d43c606a9b739147e09d89d1121df294ed3c585",
            (6755, 9716),
        ),
    }

    for relative_path, (expected_bytes, expected_sha256, expected_chars) in expected.items():
        path = FIXTURES / relative_path
        assert path.stat().st_size == expected_bytes
        assert _sha256(path) == expected_sha256
        with fitz.open(path) as document:
            assert len(document) == 2
            assert tuple(len(page.get_text("text", sort=True)) for page in document) == (
                expected_chars
            )


def test_retrieval_eval_reuses_exact_video_fixture_bytes() -> None:
    expected = {
        "video/short-audio.mp4": (
            13025,
            "4e3c9feffa503e193165ddf27c40c0e0edf9f256c2e8e1e2d863bd7ba3e1fe49",
        ),
        "video/short-audio.mp4.mke-transcript.json": (
            506,
            "5688603821b9262f85592912ef957d852ea34448e7292c927ea5071a0668e995",
        ),
    }

    for relative_path, (expected_bytes, expected_sha256) in expected.items():
        path = FIXTURES / relative_path
        assert path.stat().st_size == expected_bytes
        assert _sha256(path) == expected_sha256


def test_retrieval_eval_manifest_freezes_approved_inventory() -> None:
    payload = json.loads(MANIFEST.read_text())

    assert payload["schema_version"] == "mke.retrieval_eval.v1"
    assert payload["manifest_id"] == "retrieval-eval-v1"
    assert len(payload["documents"]) == 3
    assert len(payload["queries"]) == 24
    assert sum(query["category"] == "answerable" for query in payload["queries"]) == 16
    assert sum(query["category"] == "lexical_confuser" for query in payload["queries"]) == 4
    assert sum(query["category"] == "out_of_corpus" for query in payload["queries"]) == 4
