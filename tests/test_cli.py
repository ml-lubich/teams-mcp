"""Offline contract tests for the Teams command line interface."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from click.testing import CliRunner

from teams_mcp.cli import cli


class FakeTeamsClient:
    def __init__(self) -> None:
        self.read_limits: list[int] = []
        self.send_calls: list[dict[str, Any]] = []

    def read_recent_messages(self, limit: int = 10) -> list[dict[str, str]]:
        self.read_limits.append(limit)
        return [{"id": "chat-1", "topic": "Example chat"}]

    def send_message(self, **kwargs: Any) -> dict[str, str]:
        self.send_calls.append(kwargs)
        return {"status": "sent"}


def _factory_for(client: FakeTeamsClient) -> Callable[[], FakeTeamsClient]:
    return lambda: client


def test_root_help_aliases_list_commands_without_creating_a_client() -> None:
    client = FakeTeamsClient()
    runner = CliRunner()

    for option in ("-h", "--help"):
        result = runner.invoke(cli, [option], obj={"client_factory": _factory_for(client)})

        assert result.exit_code == 0
        assert "read" in result.output
        assert "send" in result.output

    assert client.read_limits == []
    assert client.send_calls == []


def test_root_without_command_prints_help() -> None:
    client = FakeTeamsClient()
    result = CliRunner().invoke(cli, [], obj={"client_factory": _factory_for(client)})

    assert "read" in result.output
    assert "send" in result.output
    assert client.read_limits == []
    assert client.send_calls == []


def test_nested_command_help_is_read_only() -> None:
    client = FakeTeamsClient()
    runner = CliRunner()

    for command in (["read"], ["send"], ["agent"], ["agent", "schema"]):
        result = runner.invoke(
            cli, [*command, "-h"], obj={"client_factory": _factory_for(client)}
        )
        assert result.exit_code == 0

    assert client.read_limits == []
    assert client.send_calls == []


def test_version_option_is_read_only() -> None:
    client = FakeTeamsClient()
    runner = CliRunner()

    for option in ("-V", "--version"):
        result = runner.invoke(cli, [option], obj={"client_factory": _factory_for(client)})
        assert result.exit_code == 0
        assert "teams" in result.output.lower()

    assert client.read_limits == []
    assert client.send_calls == []


def test_read_json_uses_injected_client_and_never_sends(monkeypatch: Any) -> None:
    monkeypatch.delenv("TEAMS_ACCESS_TOKEN", raising=False)
    client = FakeTeamsClient()

    result = CliRunner().invoke(
        cli,
        ["read", "--limit", "4", "-j"],
        obj={"client_factory": _factory_for(client)},
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == [{"id": "chat-1", "topic": "Example chat"}]
    assert client.read_limits == [4]
    assert client.send_calls == []


def test_read_table_formats_chat_status_and_error_rows() -> None:
    class RowsClient(FakeTeamsClient):
        def read_recent_messages(self, limit: int = 10) -> list[dict[str, str]]:
            return [
                {"id": "chat-1", "topic": "Topic"},
                {"chatType": "group"},
                {"status": "info", "message": "hint"},
                {"error": "offline"},
            ]

    result = CliRunner().invoke(
        cli,
        ["read"],
        obj={"client_factory": _factory_for(RowsClient())},
    )
    assert result.exit_code == 0
    assert "chat-1" in result.output
    assert "group" in result.output
    assert "offline" in result.output


def test_send_json_and_failure_outputs() -> None:
    client = FakeTeamsClient()
    result = CliRunner().invoke(
        cli,
        ["send", "hello", "-j"],
        obj={"client_factory": _factory_for(client)},
    )
    assert result.exit_code == 0
    assert json.loads(result.output) == {"status": "sent"}
    assert client.send_calls == [{"message": "hello", "chat_id": None, "recipient": None}]

    class FailedClient(FakeTeamsClient):
        def send_message(self, **kwargs: Any) -> dict[str, str]:
            return {"status": "error", "error": "offline"}

    failure = CliRunner().invoke(
        cli,
        ["send", "hello"],
        obj={"client_factory": _factory_for(FailedClient())},
    )
    assert failure.exit_code == 0
    assert "offline" in failure.output


def test_main_calls_click_group(monkeypatch: Any) -> None:
    from teams_mcp import cli as cli_module

    called: list[bool] = []
    monkeypatch.setattr(cli_module, "cli", lambda: called.append(True))
    cli_module.main()
    assert called == [True]


def test_invalid_read_limit_is_rejected_before_client_creation() -> None:
    client = FakeTeamsClient()

    result = CliRunner().invoke(
        cli,
        ["read", "--limit", "0"],
        obj={"client_factory": _factory_for(client)},
    )

    assert result.exit_code != 0
    assert client.read_limits == []
    assert client.send_calls == []


def test_agent_schema_is_json_and_describes_cli_contract() -> None:
    result = CliRunner().invoke(cli, ["agent", "schema"])

    assert result.exit_code == 0
    schema = json.loads(result.output)
    assert schema["tool"] == "teams"
    assert {command["name"] for command in schema["commands"]} == {
        "send",
        "read",
        "agent schema",
    }
    send = next(command for command in schema["commands"] if command["name"] == "send")
    params = {param["name"]: param for param in send["params"]}
    assert params["message"]["required"] is True
    assert "--chat-id" in params["chat_id"]["flags"]
    assert {param["name"] for param in schema["global_params"]} == {"version"}
