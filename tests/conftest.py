from pathlib import Path

import pytest

PDF_FIXTURES = Path(__file__).parent / "fixtures" / "pdf"


@pytest.fixture
def pdf_fixtures() -> Path:
    return PDF_FIXTURES
