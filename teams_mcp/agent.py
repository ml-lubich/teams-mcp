"""Machine-readable CLI schema for agent integrations."""

from __future__ import annotations

import click

from teams_mcp import __version__


def build_schema(root: click.Group) -> dict[str, object]:
    """Describe runnable Click commands and their parameters."""
    commands: list[dict[str, object]] = []

    def visit(command: click.Command, prefix: str) -> None:
        subcommands = command.commands if isinstance(command, click.Group) else None
        if subcommands:
            for name, child in subcommands.items():
                if child.hidden:
                    continue
                visit(child, f"{prefix} {name}".strip())
            return

        params = [
            {
                "name": param.name,
                "type": param.type.name,
                "required": bool(param.required),
                "flags": list(param.opts),
            }
            for param in command.params
            if param.name != "help"
        ]
        commands.append(
            {
                "name": prefix,
                "help": (command.help or "").strip(),
                "params": params,
            }
        )

    global_params = [
        {
            "name": param.name,
            "type": param.type.name,
            "required": bool(param.required),
            "flags": list(param.opts),
        }
        for param in root.params
        if param.name != "help"
    ]
    visit(root, "")
    return {
        "version": __version__,
        "tool": "teams",
        "mcp": "teams-mcp",
        "help": "teams --help | teams <command> --help",
        "global_params": global_params,
        "commands": commands,
    }
