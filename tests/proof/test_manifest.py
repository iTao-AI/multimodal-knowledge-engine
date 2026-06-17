from mke.proof.manifest import PRODUCT_PROOF_MANIFEST


def test_product_manifest_has_ordered_cases_and_name() -> None:
    assert PRODUCT_PROOF_MANIFEST.name == "product"
    assert PRODUCT_PROOF_MANIFEST.cases == (
        "cli_pdf_ingest",
        "cli_pdf_search",
        "cli_failed_reprocess",
        "cli_video_ingest_search",
        "cli_ask",
        "mcp_ingest_file",
        "mcp_get_run",
        "mcp_search_and_ask",
    )


def test_product_manifest_uses_repository_relative_fixtures() -> None:
    fixtures = PRODUCT_PROOF_MANIFEST.fixtures

    assert str(fixtures.text_layer_pdf) == "tests/fixtures/pdf/text-layer.pdf"
    assert str(fixtures.revised_pdf) == "tests/fixtures/pdf/text-layer-revised.pdf"
    assert str(fixtures.video) == "tests/fixtures/video/short-audio.mp4"
    assert (
        str(fixtures.video_transcript)
        == "tests/fixtures/video/short-audio.mp4.mke-transcript.json"
    )
