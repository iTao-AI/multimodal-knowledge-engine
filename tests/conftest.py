from pathlib import Path

import pytest

PDF_FIXTURES = Path(__file__).parent / "fixtures" / "pdf"
VIDEO_FIXTURES = Path(__file__).parent / "fixtures" / "video"


@pytest.fixture
def pdf_fixtures() -> Path:
    return PDF_FIXTURES


@pytest.fixture
def video_fixtures() -> Path:
    return VIDEO_FIXTURES
