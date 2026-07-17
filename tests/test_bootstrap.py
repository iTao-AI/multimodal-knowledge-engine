from pytest import CaptureFixture

from mke import __version__
from mke.cli import main


def test_package_exposes_bootstrap_version() -> None:
    assert __version__ == "0.1.3"


def test_cli_reports_bootstrap_status(capsys: CaptureFixture[str]) -> None:
    assert main() == 0
    captured = capsys.readouterr()
    assert captured.out == "multimodal-knowledge-engine: bootstrap stage\n"
