# teams-mcp

Installable Microsoft Teams CLI package. The `teams` command provides help,
version information, recent chat reads, and message sending through the
configured Teams client.

## Install and build

```bash
uv tool install -e .
teams --help
teams --version
```

For a local checkout, install the package with `uv tool install .`.

Build a wheel and source archive with:

```bash
uv build
```

## Commands

```bash
teams read --limit 5
teams read --limit 5 --json
teams send --help
teams agent schema
```

`teams agent schema` prints the command, option, and version contract as JSON.
This package currently exposes a CLI; it does not run an MCP server.

`read` uses the Microsoft Graph API when `TEAMS_ACCESS_TOKEN` is set. Without
that token, it prints local integration guidance and does not open the Teams
app. For offline CLI verification, tests inject a fake client and do not make
Graph requests.

`send` delivers a message through Microsoft Graph when a token and chat ID are
provided, or through the desktop automation fallback. Running `teams send`
can deliver a real message; inspect its help before use.

## Development

```bash
uv sync --locked --extra dev
uv run pytest -q
```

The pytest configuration measures `teams_mcp` and fails below 80% aggregate line
coverage. CLI tests use a fake client. They must not read credentials, contact
Graph, launch Teams, or send messages.
