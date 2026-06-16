from pathlib import Path

import mke.cli
from mke.cli import main


def test_cli_mcp_passes_db_and_allowed_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[tuple[Path, Path]] = []
    db_path = tmp_path / "mke.sqlite"
    allowed_root = tmp_path / "materials"
    allowed_root.mkdir()

    def fake_run_mcp_server(*, db_path: Path, allowed_root: Path) -> int:
        calls.append((db_path, allowed_root))
        return 0

    monkeypatch.setattr(mke.cli, "run_mcp_server", fake_run_mcp_server)

    assert main(["--db", str(db_path), "mcp", "--allowed-root", str(allowed_root)]) == 0

    assert calls == [(db_path, allowed_root)]


def test_cli_mcp_allowed_root_defaults_to_current_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[tuple[Path, Path]] = []
    db_path = tmp_path / "mke.sqlite"

    def fake_run_mcp_server(*, db_path: Path, allowed_root: Path) -> int:
        calls.append((db_path, allowed_root))
        return 0

    monkeypatch.setattr(mke.cli, "run_mcp_server", fake_run_mcp_server)
    monkeypatch.chdir(tmp_path)

    assert main(["--db", str(db_path), "mcp"]) == 0

    assert calls == [(db_path, Path.cwd())]
