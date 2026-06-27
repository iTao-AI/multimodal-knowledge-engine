from pathlib import Path

import pytest
from pytest import MonkeyPatch

import mke.cli
from mke.cli import main
from mke.interfaces.mcp_contract import McpRuntimeConfig


def test_cli_mcp_passes_db_and_allowed_root(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    calls: list[tuple[Path, Path, str, str]] = []
    db_path = tmp_path / "mke.sqlite"
    allowed_root = tmp_path / "materials"
    allowed_root.mkdir()

    def fake_run_mcp_server(config: McpRuntimeConfig) -> int:
        assert config.runtime.retrieval_strategy is not None
        assert config.runtime.retrieval_query_policy is not None
        calls.append(
            (
                config.db_path,
                config.allowed_root,
                config.runtime.retrieval_strategy,
                config.runtime.retrieval_query_policy,
            )
        )
        return 0

    monkeypatch.setattr(mke.cli, "run_mcp_server", fake_run_mcp_server)

    assert main(["--db", str(db_path), "mcp", "--allowed-root", str(allowed_root)]) == 0

    assert calls == [
        (
            db_path,
            allowed_root,
            "cjk-active-scan-overlap-v1",
            "numeric-grouping-v1",
        )
    ]


def test_cli_mcp_allowed_root_defaults_to_current_directory(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    calls: list[tuple[Path, Path]] = []
    db_path = tmp_path / "mke.sqlite"

    def fake_run_mcp_server(config: McpRuntimeConfig) -> int:
        calls.append((config.db_path, config.allowed_root))
        return 0

    monkeypatch.setattr(mke.cli, "run_mcp_server", fake_run_mcp_server)
    monkeypatch.chdir(tmp_path)

    assert main(["--db", str(db_path), "mcp"]) == 0

    assert calls == [(db_path, Path.cwd())]


def test_cli_mcp_passes_current_retrieval_policy_for_rollback(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    policies: list[str] = []

    def fake_run_mcp_server(config: McpRuntimeConfig) -> int:
        assert config.runtime.retrieval_query_policy is not None
        policies.append(config.runtime.retrieval_query_policy)
        return 0

    monkeypatch.setattr(mke.cli, "run_mcp_server", fake_run_mcp_server)

    assert (
        main(
            [
                "--db",
                str(tmp_path / "mke.sqlite"),
                "--retrieval-query-policy",
                "current",
                "mcp",
            ]
        )
        == 0
    )

    assert policies == ["current"]


def test_cli_mcp_passes_explicit_retrieval_strategy(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    strategies: list[str] = []

    def fake_run_mcp_server(config: McpRuntimeConfig) -> int:
        assert config.runtime.retrieval_strategy is not None
        strategies.append(config.runtime.retrieval_strategy)
        return 0

    monkeypatch.setattr(mke.cli, "run_mcp_server", fake_run_mcp_server)

    assert (
        main(
            [
                "--db",
                str(tmp_path / "mke.sqlite"),
                "--retrieval-strategy",
                "cjk-active-scan-overlap-v1",
                "mcp",
            ]
        )
        == 0
    )

    assert strategies == ["cjk-active-scan-overlap-v1"]


def test_cli_mcp_rejects_conflicting_strategy_and_query_policy(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--db",
                str(tmp_path / "mke.sqlite"),
                "--retrieval-strategy",
                "cjk-active-scan-overlap-v1",
                "--retrieval-query-policy",
                "current",
                "mcp",
            ]
        )

    assert error.value.code == 2


def test_cli_legacy_numeric_policy_remains_explicit_rollback_after_default_flip(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    strategies: list[str] = []

    def fake_run_mcp_server(config: McpRuntimeConfig) -> int:
        assert config.runtime.retrieval_strategy is not None
        strategies.append(config.runtime.retrieval_strategy)
        return 0

    monkeypatch.setattr(
        "mke.runtime.DEFAULT_RETRIEVAL_STRATEGY",
        "cjk-active-scan-overlap-v1",
    )
    monkeypatch.setattr(mke.cli, "run_mcp_server", fake_run_mcp_server)

    assert main(["--db", str(tmp_path / "default.sqlite"), "mcp"]) == 0
    assert (
        main(
            [
                "--db",
                str(tmp_path / "rollback.sqlite"),
                "--retrieval-query-policy",
                "numeric-grouping-v1",
                "mcp",
            ]
        )
        == 0
    )

    assert strategies == [
        "cjk-active-scan-overlap-v1",
        "numeric-grouping-v1",
    ]
