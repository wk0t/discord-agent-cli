# discord-agent-cli

A Discord command-line client designed to be driven by an **AI agent**: every command prints a **single, uniform JSON object to stdout**, never free-form text.

The agent can therefore chain commands naturally:
`guilds` → `channels <guild_id>` → `messages <channel_id>` → `send` / `react` / `search` / `watch`...

## Output contract

Success (exit code 0):

```json
{"ok": true, "command": "messages", "data": [ ... ]}
```

Error (exit code 1):

```json
{"ok": false, "command": "send", "error": {"type": "Forbidden", "message": "Missing Permissions"}}
```

- `watch` emits **JSON lines** (one object per line): `{"ok": true, "event": "message", "data": {...}}`
- `--pretty` indents the JSON for humans; without the flag it is compact (ideal for parsing).
- Internal logs go to **stderr**, never to stdout.

## Installation

```bash
pip install -r requirements.txt
```

## Create the Discord bot

1. Go to <https://discord.com/developers/applications> → **New Application** → **Bot** tab → **Add Bot**.
2. Copy the **token** (*Reset Token* button).
3. Enable the **privileged intents** in the *Bot* tab: `SERVER MEMBERS INTENT` and `MESSAGE CONTENT INTENT` (required to read messages and the member list).
4. *OAuth2 → URL Generator* tab: scopes `bot` (+ `applications.commands` if needed), useful permissions: `Read Messages/View Channels`, `Send Messages`, `Read Message History`, `Add Reactions`, `Manage Messages`, `Manage Channels`, `View Server Members`... then invite the bot to your server with the generated URL.

## Token configuration

```bash
cp .env.example .env   # then put your token in .env
# or:
export DISCORD_TOKEN="your_token"
# or per call:
python discord_cli.py --token "your_token" whoami
```

`.env` is in `.gitignore`: the token will never be committed.

## Commands

| Command | Description | Example |
|---|---|---|
| `whoami` | bot identity, latency | `python discord_cli.py whoami` |
| `guilds` | servers the bot is in | `python discord_cli.py guilds` |
| `guild <id>` | server details + roles | `python discord_cli.py guild 111...` |
| `channels <guild_id>` | channels (`--type`, `--category`) | `python discord_cli.py channels 111... --type text` |
| `channel <id>` | channel details | `python discord_cli.py channel 222...` |
| `messages <channel_id>` | history (`-n`, `--before`, `--after`) | `python discord_cli.py messages 222... -n 30` |
| `send <channel_id> <text>` | send (`--reply-to`, `--file`, `--embed-*`) | `python discord_cli.py send 222... "Hi!"` |
| `edit <channel_id> <msg_id> <text>` | edit a bot message | `... edit 222... 333... "corrected"` |
| `delete <channel_id> <msg_id>` | delete a message | `... delete 222... 333...` |
| `react` / `unreact` | react to a message | `... react 222... 333... "👍"` |
| `pins <channel_id>` | pinned messages | `... pins 222...` |
| `members <guild_id> [-n]` | server members | `... members 111... -n 200` |
| `member <guild_id> <user_id>` | member details | `... member 111... 999...` |
| `roles <guild_id>` / `emojis <guild_id>` | roles / emojis | `... roles 111...` |
| `search <query> --channel/--guild <id>` | search history | `... search "meeting" --guild 111... --max 5000` |
| `create-channel <guild_id> <name>` | create a channel (`--type`, `--category`, `--topic`) | `... create-channel 111... "announcements" --type text` |
| `delete-channel <id>` | delete a channel | `... delete-channel 222...` |
| `threads <channel_id> [--archived]` | threads of a channel | `... threads 222...` |
| `create-thread <channel_id> <name>` | create a thread (`--message-id`, `--private`) | `... create-thread 222... "thread-1"` |
| `dm <user_id> <text>` | private message | `... dm 999... "hello in DM"` |
| `profile <user_id>` | global profile of a user | `... profile 999...` |
| `watch <channel_id...>` | **real time**: JSON lines of new messages, Ctrl-C to quit (`--timeout N` to stop by itself) | `... watch 222... 444... --timeout 60` |

## `--mock` mode (no token)

To test the JSON contract without a Discord account:

```bash
python discord_cli.py --mock --pretty guilds
python discord_cli.py --mock messages 123 -n 5
python discord_cli.py --mock watch 123
```

## Example chain for an agent

```bash
python discord_cli.py guilds                          # pick a server
python discord_cli.py channels <guild_id>             # find #general
python discord_cli.py messages <channel_id> -n 50      # read recent context
python discord_cli.py send <channel_id> "Summary: ..."  # reply
python discord_cli.py watch <channel_id> --timeout 300 # wait for new messages
```

## Known limitations

- `search --guild` walks the history channel by channel: bound it with `--max` (default 2000 messages scanned).
- `edit` only works on messages written by the bot itself (Discord rule).
- `members` requires the *Server Members* intent enabled in the developer portal.
- The token is never displayed, including in error messages.
