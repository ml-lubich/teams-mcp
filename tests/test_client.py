"""Offline tests for Teams client behavior and OS/network boundaries."""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from typing import Any

from teams_mcp.client import TeamsClient


def test_token_defaults_from_environment(monkeypatch: Any) -> None:
    monkeypatch.setenv("TEAMS_ACCESS_TOKEN", "test-token")
    assert TeamsClient().token == "test-token"
    assert TeamsClient(token="explicit").token == "explicit"


def test_applescript_sends_only_through_mocked_runner(monkeypatch: Any) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], **_: Any) -> SimpleNamespace:
        calls.append(args)
        return SimpleNamespace(stdout="SUCCESS\n")

    monkeypatch.setattr("teams_mcp.client.subprocess.run", fake_run)
    result = TeamsClient().send_via_applescript('hello "there"', "Example")

    assert result == {"status": "sent", "channel": "applescript", "chat": "Example"}
    assert calls and calls[0][0:2] == ["osascript", "-e"]
    assert 'hello \\\"there\\\"' in calls[0][2]


def test_applescript_error_and_runner_exceptions_are_reported(monkeypatch: Any) -> None:
    def failed_run(*_: Any, **__: Any) -> Any:
        raise subprocess.CalledProcessError(1, "osascript", stderr="denied")

    monkeypatch.setattr("teams_mcp.client.subprocess.run", failed_run)
    result = TeamsClient().send_via_applescript("unused")
    assert result == {"status": "error", "error": "ERROR: denied"}

    monkeypatch.setattr(
        "teams_mcp.client.subprocess.run",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("unavailable")),
    )
    assert TeamsClient()._run_osascript("script") == "ERROR: unavailable"


def test_read_recent_messages_uses_graph_response(monkeypatch: Any) -> None:
    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"value": [{"id": "chat-1"}]}).encode()

    seen: list[Any] = []
    monkeypatch.setattr("urllib.request.urlopen", lambda req: (seen.append(req), Response())[1])
    assert TeamsClient("token").read_recent_messages(3) == [{"id": "chat-1"}]
    assert "Bearer token" == seen[0].get_header("Authorization")
    assert "$top=3" in seen[0].full_url


def test_read_recent_messages_error_and_desktop_hint(monkeypatch: Any) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda *_: (_ for _ in ()).throw(OSError("offline")))
    assert TeamsClient("token").read_recent_messages() == [{"error": "offline"}]
    assert TeamsClient().read_recent_messages()[0]["status"] == "info"


def test_graph_send_payload_success_and_error(monkeypatch: Any) -> None:
    seen: list[Any] = []

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def read(self) -> bytes:
            return b'{"id":"sent-1"}'

    monkeypatch.setattr("urllib.request.urlopen", lambda req: (seen.append(req), Response())[1])
    result = TeamsClient("token").send_message("hello", chat_id="chat/1")
    assert result == {"status": "sent", "channel": "graph_api", "response": {"id": "sent-1"}}
    assert json.loads(seen[0].data) == {"body": {"content": "hello"}}
    assert seen[0].get_method() == "POST"

    monkeypatch.setattr("urllib.request.urlopen", lambda *_: (_ for _ in ()).throw(OSError("offline")))
    assert TeamsClient("token").send_message("hello", chat_id="chat") == {
        "status": "error", "error": "offline"
    }


def test_send_without_graph_chat_uses_applescript_fallback(monkeypatch: Any) -> None:
    called: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        TeamsClient,
        "send_via_applescript",
        lambda self, message, chat_title=None: (called.append((message, chat_title)) or {"status": "sent"}),
    )
    assert TeamsClient("token").send_message("hello", recipient="Person") == {"status": "sent"}
    assert called == [("hello", "Person")]
