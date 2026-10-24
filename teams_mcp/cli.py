"""Microsoft Teams CLI entry point."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol, cast

import click
from rich.console import Console
from rich.table import Table

from teams_mcp import __version__
from teams_mcp.client import TeamsClient

console = Console()


class TeamsClientPort(Protocol):
    """Operations the CLI uses, injectable for isolated command checks."""

    def send_message(
        self,
        message: str,
        chat_id: str | None = None,
        recipient: str | None = None,
    ) -> dict[str, Any]: ...

    def read_recent_messages(self, limit: int = 10) -> list[dict[str, Any]]: ...


ClientFactory = Callable[[], TeamsClientPort]


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)
@click.version_option(
    __version__,
    "--version",
    "-V",
    prog_name="teams",
)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Microsoft Teams command line tools."""
    ctx.ensure_object(dict)
    ctx.obj.setdefault("client_factory", TeamsClient)


def _client(ctx: click.Context) -> TeamsClientPort:
    factory = cast(ClientFactory, ctx.obj["client_factory"])
    return factory()


@cli.command("send")
@click.argument("message", type=click.STRING)
@click.option(
    "--chat-id",
    "-c",
    type=click.STRING,
    default=None,
    help="Microsoft Graph chat ID (when using the Graph API).",
)
@click.option(
    "--recipient",
    "-r",
    type=click.STRING,
    default=None,
    help="Recipient or Teams window title filter.",
)
@click.option("-j", "--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
def send_cmd(
    ctx: click.Context,
    message: str,
    chat_id: str | None,
    recipient: str | None,
    as_json: bool,
) -> None:
    """Send a message to Microsoft Teams."""
    response = _client(ctx).send_message(
        message=message,
        chat_id=chat_id,
        recipient=recipient,
    )
    if as_json:
        click.echo(json.dumps(response, ensure_ascii=False))
    elif response.get("status") == "sent":
        console.print(
            f"[bold green]✓ Message sent to Teams via {response.get('channel')}[/bold green]"
        )
    else:
        console.print(
            f"[bold red]✗ Failed to send message:[/bold red] {response.get('error')}"
        )


@cli.command("read")
@click.option(
    "--limit",
    "-l",
    type=click.IntRange(min=1, max=100),
    default=10,
    show_default=True,
    help="Maximum number of chats or messages to retrieve (1–100).",
)
@click.option("-j", "--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
def read_cmd(ctx: click.Context, limit: int, as_json: bool) -> None:
    """Read recent Teams messages or chats."""
    response = _client(ctx).read_recent_messages(limit=limit)
    if as_json:
        click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        return

    table = Table(title="Microsoft Teams Recent Messages / Status")
    table.add_column("Property", style="cyan")
    table.add_column("Details", style="green")

    for item in response:
        if "error" in item:
            table.add_row("Error", str(item["error"]))
        elif "status" in item:
            table.add_row(str(item.get("status", "info")), str(item.get("message", "")))
        else:
            table.add_row(
                str(item.get("id", "Chat")),
                str(item.get("topic", item.get("chatType", "Direct"))),
            )

    console.print(table)


def main() -> None:
    """Run the Teams CLI."""
    cli()


if __name__ == "__main__":
    main()
