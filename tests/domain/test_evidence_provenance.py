import pytest

from mke.domain import (
    ActivePublicationObservation,
    AskResult,
    AskSnapshot,
    SearchResult,
    SearchResultProvenance,
    SearchSnapshot,
)


def _result(kind: str = "page") -> SearchResult:
    return SearchResult("ev_1", "pub_1", "src_1", kind, 1 if kind == "page" else 0, 1 if kind == "page" else 10, "text")


def test_provenance_accepts_source_fingerprint_and_locator() -> None:
    value = SearchResultProvenance(_result(), "sha256:" + "a" * 64, 2, "run_1")
    assert value.publication_revision == 2


@pytest.mark.parametrize("fingerprint", ["md5:" + "a" * 64, "sha256:" + "A" * 64, "sha256:abc", "sha256:" + "g" * 64])
def test_provenance_rejects_invalid_fingerprint(fingerprint: str) -> None:
    with pytest.raises(ValueError):
        SearchResultProvenance(_result(), fingerprint, 1, "run_1")


@pytest.mark.parametrize("result", [_result("other"), SearchResult("ev_1", "pub_1", "src_1", "page", 1, 2, "x"), SearchResult("ev_1", "pub_1", "src_1", "timestamp_ms", 1, 1, "x")])
def test_provenance_rejects_invalid_locator(result: SearchResult) -> None:
    with pytest.raises(ValueError):
        SearchResultProvenance(result, "sha256:" + "a" * 64, 1, "run_1")


@pytest.mark.parametrize(
    ("state", "sources", "publications", "evidence"),
    [("empty", 1, 0, 0), ("no_active_publication", 0, 0, 0), ("active", 1, 1, 0), ("active", 1, 0, 1)],
)
def test_observation_rejects_inconsistent_counts(state: str, sources: int, publications: int, evidence: int) -> None:
    with pytest.raises(ValueError):
        ActivePublicationObservation("local", state, sources, publications, evidence)


def test_snapshots_are_immutable_compositions() -> None:
    observation = ActivePublicationObservation("local", "active", 1, 1, 1)
    item = SearchResultProvenance(_result(), "sha256:" + "a" * 64, 1, "run_1")
    search = SearchSnapshot(observation, (item,))
    ask = AskSnapshot(observation, AskResult("ask_1", "q", "evidence_found", "s", (_result(),), ()), (item,))
    assert search.results == ask.evidence
