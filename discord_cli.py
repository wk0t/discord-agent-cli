#!/usr/bin/env python3
"""discord-cli — a Discord command-line client designed for AI agents.

Every command prints a single, uniform JSON object to stdout:
    {"ok": true,  "command": "...", "data": ...}
    {"ok": false, "command": "...", "error": {"type": "...", "message": "..."}}

No logging library pollutes stdout (discord.py logs go to stderr).

Usage:
    python discord_cli.py [--token TOKEN | .env] [--pretty] <command> [args]

Examples:
    python discord_cli.py guilds
    python discord_cli.py channels 111222333
    python discord_cli.py messages 444555666 -n 20
    python discord_cli.py send 444555666 "Hello from an AI agent"
    python discord_cli.py watch 444555666 777888999 --timeout 60
    python discord_cli.py --mock guilds          # demo without a token
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Output / errors
# ---------------------------------------------------------------------------

_PRETTY = False
_TOKEN = ""


def emit(obj: dict) -> None:
    """Print a JSON object to stdout (the agent's single source of truth)."""
    indent = 2 if _PRETTY else None
    print(json.dumps(obj, ensure_ascii=False, indent=indent), flush=True)


def _sanitize(text: str) -> str:
    """Never let the token leak into an error message."""
    if _TOKEN:
        text = text.replace(_TOKEN, "***")
    return text


def fail(command: str, exc: BaseException) -> "NoReturn":  # type: ignore[name-defined]
    emit({
        "ok": False,
        "command": command,
        "error": {"type": type(exc).__name__, "message": _sanitize(str(exc))},
    })
    sys.exit(1)


# ---------------------------------------------------------------------------
# Token / .env
# ---------------------------------------------------------------------------

def load_env_file(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def resolve_token(args: argparse.Namespace) -> str:
    token = args.token or os.environ.get("DISCORD_TOKEN", "")
    if not token:
        load_env_file(args.env)
        token = os.environ.get("DISCORD_TOKEN", "")
    return token.strip()


# ---------------------------------------------------------------------------
# Serialization (discord objects -> clean JSON dicts)
# ---------------------------------------------------------------------------

def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def user_dict(u) -> dict:
    avatar = None
    with contextlib.suppress(Exception):
        avatar = str(u.display_avatar.url)
    return {
        "id": str(u.id),
        "name": u.name,
        "display_name": getattr(u, "display_name", u.name),
        "bot": bool(getattr(u, "bot", False)),
        "avatar_url": avatar,
    }


def member_dict(m) -> dict:
    d = user_dict(m)
    d.update({
        "nick": m.nick,
        "joined_at": _iso(getattr(m, "joined_at", None)),
        "roles": [str(r.id) for r in m.roles if r.name != "@everyone"],
        "premium_since": _iso(getattr(m, "premium_since", None)),
        "guild_id": str(m.guild.id),
    })
    return d


def emoji_dict(e) -> dict:
    return {"id": str(e.id), "name": e.name, "animated": e.animated, "str": str(e)}


def role_dict(r) -> dict:
    return {
        "id": str(r.id),
        "name": r.name,
        "color": str(r.color),
        "position": r.position,
        "mentionable": r.mentionable,
        "hoist": r.hoist,
        "permissions": str(r.permissions.value),
    }


def channel_dict(c) -> dict:
    d = {
        "id": str(c.id),
        "name": getattr(c, "name", None),
        "type": str(getattr(c, "type", "unknown")),
        "guild_id": str(c.guild.id) if getattr(c, "guild", None) else None,
        "position": getattr(c, "position", None),
        "category_id": str(c.category_id) if getattr(c, "category_id", None) else None,
        "topic": getattr(c, "topic", None),
        "nsfw": bool(getattr(c, "nsfw", False)),
        "slowmode_delay": getattr(c, "slowmode_delay", None),
        "last_message_id": str(c.last_message_id) if getattr(c, "last_message_id", None) else None,
    }
    if str(getattr(c, "type", "")).startswith("voice") or str(getattr(c, "type", "")) in ("stage_voice",):
        d["bitrate"] = getattr(c, "bitrate", None)
        d["user_limit"] = getattr(c, "user_limit", None)
    return d


def thread_dict(t) -> dict:
    d = channel_dict(t)
    d.update({
        "parent_id": str(t.parent_id) if getattr(t, "parent_id", None) else None,
        "owner_id": str(t.owner_id) if getattr(t, "owner_id", None) else None,
        "archived": bool(getattr(t, "archived", False)),
        "locked": bool(getattr(t, "locked", False)),
        "message_count": getattr(t, "message_count", None),
    })
    return d


def attachment_dict(a) -> dict:
    return {
        "id": str(a.id),
        "filename": a.filename,
        "size": a.size,
        "url": a.url,
        "content_type": a.content_type,
    }


def embed_dict(e) -> dict:
    return {
        "title": e.title,
        "description": e.description,
        "url": e.url,
        "type": str(e.type),
        "fields": [{"name": f.name, "value": f.value} for f in (e.fields or [])],
    }


def message_dict(m) -> dict:
    ref = None
    if m.reference and m.reference.message_id:
        ref = {"message_id": str(m.reference.message_id), "channel_id": str(m.reference.channel_id)}
    return {
        "id": str(m.id),
        "channel_id": str(m.channel.id),
        "guild_id": str(m.guild.id) if m.guild else None,
        "author": user_dict(m.author),
        "content": m.content,
        "created_at": _iso(m.created_at),
        "edited_at": _iso(m.edited_at),
        "pinned": m.pinned,
        "type": str(m.type),
        "attachments": [attachment_dict(a) for a in m.attachments],
        "embeds": [embed_dict(e) for e in m.embeds],
        "reactions": [
            {"emoji": str(r.emoji), "count": r.count, "me": r.me} for r in m.reactions
        ],
        "mentions": [user_dict(u) for u in m.mentions],
        "mention_everyone": m.mention_everyone,
        "reply_to": ref,
    }


def guild_dict(g) -> dict:
    icon = None
    with contextlib.suppress(Exception):
        icon = str(g.icon.url) if g.icon else None
    return {
        "id": str(g.id),
        "name": g.name,
        "description": g.description,
        "member_count": g.member_count,
        "owner_id": str(g.owner_id),
        "icon_url": icon,
        "created_at": _iso(g.created_at),
        "features": list(g.features or []),
        "emojis": [emoji_dict(e) for e in g.emojis],
    }


# ---------------------------------------------------------------------------
# Commands (each handler: async (client, args) -> data)
# ---------------------------------------------------------------------------

async def cmd_whoami(client, args):
    u = client.user
    return {
        "id": str(u.id),
        "name": u.name,
        "bot": True,
        "guilds": len(client.guilds),
        "latency_ms": round(client.latency * 1000, 1) if client.latency else None,
    }


async def cmd_guilds(client, args):
    return [guild_dict(g) for g in client.guilds]


async def cmd_guild(client, args):
    g = client.get_guild(int(args.guild_id)) or await client.fetch_guild(int(args.guild_id))
    d = guild_dict(g)
    d["roles"] = [role_dict(r) for r in g.roles]
    return d


async def cmd_channels(client, args):
    g = client.get_guild(int(args.guild_id)) or await client.fetch_guild(int(args.guild_id))
    out = [channel_dict(c) for c in g.channels]
    if args.type:
        out = [c for c in out if c["type"].startswith(args.type)]
    if args.category:
        out = [c for c in out if c["category_id"] == str(args.category)]
    return sorted(out, key=lambda c: (c["position"] is None, c["position"] or 0))


async def cmd_channel(client, args):
    c = await client.fetch_channel(int(args.channel_id))
    return channel_dict(c)


async def _get_channel(client, channel_id: str):
    c = client.get_channel(int(channel_id))
    return c or await client.fetch_channel(int(channel_id))


async def cmd_messages(client, args):
    ch = await _get_channel(client, args.channel_id)
    kwargs = {"limit": min(max(args.limit, 1), 1000)}
    if args.before:
        kwargs["before"] = await ch.fetch_message(int(args.before)) if hasattr(ch, "fetch_message") else None
    if args.after:
        kwargs["after"] = await ch.fetch_message(int(args.after)) if hasattr(ch, "fetch_message") else None
    msgs = [message_dict(m) async for m in ch.history(**{k: v for k, v in kwargs.items() if v is not None})]
    return msgs


async def cmd_send(client, args):
    ch = await _get_channel(client, args.channel_id)
    kwargs = {}
    if args.reply_to:
        ref = await ch.fetch_message(int(args.reply_to))
        kwargs["reference"] = ref
    files = None
    if args.file:
        import discord
        files = [discord.File(fp) for fp in args.file]
        kwargs["files"] = files
    embed = None
    if args.embed_title or args.embed_description:
        import discord
        embed = discord.Embed(
            title=args.embed_title or None,
            description=args.embed_description or None,
            color=int(args.embed_color, 16) if args.embed_color else None,
        )
        kwargs["embed"] = embed
    m = await ch.send(args.text, **kwargs)
    return message_dict(m)


async def _get_message(client, channel_id: str, message_id: str):
    ch = await _get_channel(client, channel_id)
    return ch, await ch.fetch_message(int(message_id))


async def cmd_edit(client, args):
    _, m = await _get_message(client, args.channel_id, args.message_id)
    m = await m.edit(content=args.text)
    return message_dict(m)


async def cmd_delete(client, args):
    _, m = await _get_message(client, args.channel_id, args.message_id)
    await m.delete()
    return {"deleted": True, "message_id": str(m.id), "channel_id": str(m.channel.id)}


async def cmd_react(client, args):
    _, m = await _get_message(client, args.channel_id, args.message_id)
    await m.add_reaction(args.emoji)
    return {"reacted": True, "emoji": args.emoji, "message_id": str(m.id)}


async def cmd_unreact(client, args):
    _, m = await _get_message(client, args.channel_id, args.message_id)
    await m.remove_reaction(args.emoji, client.user)
    return {"unreacted": True, "emoji": args.emoji, "message_id": str(m.id)}


async def cmd_pins(client, args):
    ch = await _get_channel(client, args.channel_id)
    pins = await ch.pins()
    return [message_dict(m) for m in pins]


async def cmd_members(client, args):
    g = client.get_guild(int(args.guild_id)) or await client.fetch_guild(int(args.guild_id))
    out = []
    async for m in g.fetch_members(limit=min(max(args.limit, 1), 1000)):
        out.append(member_dict(m))
    return out


async def cmd_member(client, args):
    g = client.get_guild(int(args.guild_id)) or await client.fetch_guild(int(args.guild_id))
    m = g.get_member(int(args.user_id)) or await g.fetch_member(int(args.user_id))
    return member_dict(m)


async def cmd_roles(client, args):
    g = client.get_guild(int(args.guild_id)) or await client.fetch_guild(int(args.guild_id))
    return [role_dict(r) for r in g.roles]


async def cmd_emojis(client, args):
    g = client.get_guild(int(args.guild_id)) or await client.fetch_guild(int(args.guild_id))
    return [emoji_dict(e) for e in g.emojis]


async def cmd_search(client, args):
    """Text search in message history (local, bounded by --max)."""
    query = args.query.lower()
    results = []
    max_scan = min(max(args.max, 1), 20000)

    async def scan_channel(ch):
        nonlocal max_scan
        scanned = 0
        async for m in ch.history(limit=None):
            if scanned >= max_scan:
                break
            scanned += 1
            max_scan -= 1
            if query in (m.content or "").lower():
                results.append(message_dict(m))
                if len(results) >= args.limit:
                    return

    if args.channel:
        ch = await _get_channel(client, args.channel)
        await scan_channel(ch)
    elif args.guild:
        g = client.get_guild(int(args.guild)) or await client.fetch_guild(int(args.guild))
        for c in g.text_channels:
            if len(results) >= args.limit or max_scan <= 0:
                break
            await scan_channel(c)
    else:
        raise ValueError("search requires --channel or --guild")
    return {"query": args.query, "count": len(results), "results": results}


async def cmd_create_channel(client, args):
    import discord
    g = client.get_guild(int(args.guild_id)) or await client.fetch_guild(int(args.guild_id))
    kwargs = {"name": args.name}
    if args.category:
        kwargs["category"] = g.get_channel(int(args.category))
    if args.topic:
        kwargs["topic"] = args.topic
    if args.nsfw:
        kwargs["nsfw"] = True
    t = args.type
    if t == "text":
        c = await g.create_text_channel(**kwargs)
    elif t == "voice":
        c = await g.create_voice_channel(**kwargs)
    elif t == "category":
        c = await g.create_category(**kwargs)
    elif t == "stage":
        c = await g.create_stage_channel(**kwargs)
    elif t == "forum":
        c = await g.create_forum_channel(**kwargs)
    else:
        raise ValueError(f"unknown type: {t} (text|voice|category|stage|forum)")
    return channel_dict(c)


async def cmd_delete_channel(client, args):
    c = await _get_channel(client, args.channel_id)
    await c.delete()
    return {"deleted": True, "channel_id": str(c.id), "name": getattr(c, "name", None)}


async def cmd_threads(client, args):
    ch = await _get_channel(client, args.channel_id)
    out = [thread_dict(t) for t in getattr(ch, "threads", [])]
    if args.archived:
        async for t in ch.archived_threads(limit=args.limit):
            out.append(thread_dict(t))
    return out


async def cmd_create_thread(client, args):
    ch = await _get_channel(client, args.channel_id)
    kwargs = {"name": args.name}
    if args.message_id:
        kwargs["message"] = await ch.fetch_message(int(args.message_id))
    if args.private:
        kwargs["type"] = __import__("discord").ChannelType.private_thread
    t = await ch.create_thread(**kwargs)
    return thread_dict(t)


async def cmd_dm(client, args):
    user = await client.fetch_user(int(args.user_id))
    m = await user.send(args.text)
    return message_dict(m)


async def cmd_profile(client, args):
    u = await client.fetch_user(int(args.user_id))
    d = user_dict(u)
    d["created_at"] = _iso(u.created_at)
    d["banner_url"] = None
    with contextlib.suppress(Exception):
        d["banner_url"] = str(u.banner.url) if u.banner else None
    return d


COMMANDS = {
    "whoami": cmd_whoami,
    "guilds": cmd_guilds,
    "guild": cmd_guild,
    "channels": cmd_channels,
    "channel": cmd_channel,
    "messages": cmd_messages,
    "send": cmd_send,
    "edit": cmd_edit,
    "delete": cmd_delete,
    "react": cmd_react,
    "unreact": cmd_unreact,
    "pins": cmd_pins,
    "members": cmd_members,
    "member": cmd_member,
    "roles": cmd_roles,
    "emojis": cmd_emojis,
    "search": cmd_search,
    "create-channel": cmd_create_channel,
    "delete-channel": cmd_delete_channel,
    "threads": cmd_threads,
    "create-thread": cmd_create_thread,
    "dm": cmd_dm,
    "profile": cmd_profile,
}


# ---------------------------------------------------------------------------
# Mock mode (demo / JSON contract test without a token)
# ---------------------------------------------------------------------------

MOCK_GUILD = {
    "id": "1000000000000000001", "name": "Demo Server", "description": "fake guild (--mock)",
    "member_count": 42, "owner_id": "1000000000000000009", "icon_url": None,
    "created_at": "2023-01-01T00:00:00+00:00", "features": [], "emojis": [],
}
MOCK_CHANNEL = {
    "id": "1000000000000000002", "name": "general", "type": "guild_text",
    "guild_id": MOCK_GUILD["id"], "position": 0, "category_id": None,
    "topic": "General channel (mock)", "nsfw": False, "slowmode_delay": 0, "last_message_id": "1000000000000000012",
}
MOCK_MESSAGE = {
    "id": "1000000000000000012", "channel_id": MOCK_CHANNEL["id"], "guild_id": MOCK_GUILD["id"],
    "author": {"id": "1000000000000000009", "name": "human", "display_name": "human", "bot": False, "avatar_url": None},
    "content": "Hello bot! (fake message --mock)", "created_at": "2024-05-01T12:00:00+00:00",
    "edited_at": None, "pinned": False, "type": "default", "attachments": [], "embeds": [],
    "reactions": [{"emoji": "👍", "count": 2, "me": False}],
    "mentions": [], "mention_everyone": False, "reply_to": None,
}


def run_mock(args) -> dict:
    c = args.command
    if c == "whoami":
        data = {"id": "1000000000000000099", "name": "agent-bot", "bot": True, "guilds": 1, "latency_ms": 12.3}
    elif c == "guilds":
        data = [MOCK_GUILD]
    elif c == "guild":
        data = dict(MOCK_GUILD, roles=[])
    elif c in ("channels",):
        data = [MOCK_CHANNEL]
    elif c == "channel":
        data = MOCK_CHANNEL
    elif c in ("messages", "pins", "search"):
        if c == "search":
            data = {"query": args.query, "count": 1, "results": [MOCK_MESSAGE]}
        else:
            data = [MOCK_MESSAGE]
    elif c in ("send", "edit"):
        data = dict(MOCK_MESSAGE, content=args.text)
    elif c in ("delete", "react", "unreact", "delete-channel"):
        data = {"ok_action": True, "command": c}
    elif c in ("members",):
        data = [member_dict_fake()]
    elif c == "member":
        data = member_dict_fake()
    elif c in ("roles", "emojis", "threads"):
        data = []
    elif c == "create-channel":
        data = dict(MOCK_CHANNEL, name=args.name)
    elif c == "create-thread":
        data = dict(MOCK_CHANNEL, name=args.name, type="public_thread", parent_id=MOCK_CHANNEL["id"])
    elif c == "dm":
        data = dict(MOCK_MESSAGE, guild_id=None, content=args.text)
    elif c == "profile":
        data = MOCK_MESSAGE["author"] | {"created_at": "2022-06-01T00:00:00+00:00", "banner_url": None}
    else:
        data = {"status": "mock: command not simulated", "command": c}
    return {"ok": True, "command": c, "mock": True, "data": data}


def member_dict_fake() -> dict:
    return {
        "id": "1000000000000000009", "name": "human", "display_name": "human", "bot": False, "avatar_url": None,
        "nick": None, "joined_at": "2023-02-01T00:00:00+00:00", "roles": [], "premium_since": None,
        "guild_id": MOCK_GUILD["id"],
    }


# ---------------------------------------------------------------------------
# discord.py client loop
# ---------------------------------------------------------------------------

async def run_with_client(token: str, args) -> dict:
    import discord

    intents = discord.Intents.default()
    intents.message_content = True   # privileged intent, also enable it in the developer portal
    intents.members = True           # privileged intent

    client = discord.Client(intents=intents)
    ready = asyncio.Event()

    @client.event
    async def on_ready():
        ready.set()

    if args.command == "watch":
        watched = {str(c) for c in args.channels}

        @client.event
        async def on_message(m):
            if str(m.channel.id) in watched:
                emit({"ok": True, "event": "message", "data": message_dict(m)})

    starter = asyncio.create_task(client.start(token))
    try:
        ready_task = asyncio.create_task(ready.wait())
        done, _ = await asyncio.wait({ready_task, starter}, timeout=args.timeout,
                                      return_when=asyncio.FIRST_COMPLETED)
        if starter in done:
            exc = starter.exception()
            if exc:
                raise exc
            raise ConnectionError("connection closed before ready (invalid token?)")
        if ready_task not in done:
            raise TimeoutError(f"could not connect to the Discord gateway within {args.timeout}s (valid token? bot invited?)")

        if args.command == "watch":
            t = args.watch_timeout
            if t and t > 0:
                await asyncio.sleep(t)
            else:
                while not client.is_closed():
                    await asyncio.sleep(3600)
            return {"ok": True, "command": "watch", "data": {"status": "stopped", "watched": sorted(watched)}}

        handler = COMMANDS[args.command]
        data = await asyncio.wait_for(handler(client, args), timeout=max(args.timeout, 120))
        return {"ok": True, "command": args.command, "data": data}
    finally:
        with contextlib.suppress(Exception):
            await client.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(asyncio.shield(starter), timeout=10)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="discord-cli",
        description="Discord CLI client with JSON output — designed to be driven by an AI agent.",
    )
    p.add_argument("--token", help="bot token (otherwise DISCORD_TOKEN or a .env file)")
    p.add_argument("--env", default=".env", help=".env file to read (default: .env)")
    p.add_argument("--mock", action="store_true", help="demo mode: fake data, no network calls")
    p.add_argument("--pretty", action="store_true", help="indented JSON (human-readable)")
    p.add_argument("--timeout", type=float, default=30.0, help="connection timeout (s, default 30)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("whoami", help="bot identity (id, name, latency)")

    sub.add_parser("guilds", help="list of servers the bot is in")

    g = sub.add_parser("guild", help="server details + roles")
    g.add_argument("guild_id")

    c = sub.add_parser("channels", help="channels of a server")
    c.add_argument("guild_id")
    c.add_argument("--type", help="filter: text, voice, forum, category, stage...")
    c.add_argument("--category", help="filter by category (id)")

    c = sub.add_parser("channel", help="channel details")
    c.add_argument("channel_id")

    m = sub.add_parser("messages", help="channel history (most recent first)")
    m.add_argument("channel_id")
    m.add_argument("-n", "--limit", type=int, default=50, help="number of messages (default 50, max 1000)")
    m.add_argument("--before", help="message id: read before this one")
    m.add_argument("--after", help="message id: read after this one")

    s = sub.add_parser("send", help="send a message to a channel")
    s.add_argument("channel_id")
    s.add_argument("text")
    s.add_argument("--reply-to", help="reply to this message (id)")
    s.add_argument("--file", action="append", default=[], help="attach a file (repeatable)")
    s.add_argument("--embed-title")
    s.add_argument("--embed-description")
    s.add_argument("--embed-color", help="hex color, e.g. 5865F2")

    e = sub.add_parser("edit", help="edit a message (bot's own messages only)")
    e.add_argument("channel_id")
    e.add_argument("message_id")
    e.add_argument("text")

    d = sub.add_parser("delete", help="delete a message")
    d.add_argument("channel_id")
    d.add_argument("message_id")

    r = sub.add_parser("react", help="add a reaction to a message")
    r.add_argument("channel_id")
    r.add_argument("message_id")
    r.add_argument("emoji", help="e.g. 👍 or <:name:id> / custom emoji id")

    u = sub.add_parser("unreact", help="remove the bot's reaction")
    u.add_argument("channel_id")
    u.add_argument("message_id")
    u.add_argument("emoji")

    pi = sub.add_parser("pins", help="pinned messages of a channel")
    pi.add_argument("channel_id")

    mb = sub.add_parser("members", help="members of a server")
    mb.add_argument("guild_id")
    mb.add_argument("-n", "--limit", type=int, default=100)

    mb = sub.add_parser("member", help="member details")
    mb.add_argument("guild_id")
    mb.add_argument("user_id")

    ro = sub.add_parser("roles", help="roles of a server")
    ro.add_argument("guild_id")

    em = sub.add_parser("emojis", help="emojis of a server")
    em.add_argument("guild_id")

    se = sub.add_parser("search", help="search message history")
    se.add_argument("query")
    se.add_argument("--channel", help="target channel (id)")
    se.add_argument("--guild", help="whole server (id) — slow, bounded by --max")
    se.add_argument("-n", "--limit", type=int, default=20, help="max results")
    se.add_argument("--max", type=int, default=2000, help="max messages scanned in total")

    cc = sub.add_parser("create-channel", help="create a channel")
    cc.add_argument("guild_id")
    cc.add_argument("name")
    cc.add_argument("--type", default="text", choices=["text", "voice", "category", "stage", "forum"])
    cc.add_argument("--category", help="parent category (id)")
    cc.add_argument("--topic")
    cc.add_argument("--nsfw", action="store_true")

    dc = sub.add_parser("delete-channel", help="delete a channel")
    dc.add_argument("channel_id")

    th = sub.add_parser("threads", help="threads of a channel (active, + archived with --archived)")
    th.add_argument("channel_id")
    th.add_argument("--archived", action="store_true")
    th.add_argument("-n", "--limit", type=int, default=50)

    ct = sub.add_parser("create-thread", help="create a thread in a channel")
    ct.add_argument("channel_id")
    ct.add_argument("name")
    ct.add_argument("--message-id", help="attach to this message (id)")
    ct.add_argument("--private", action="store_true")

    dm = sub.add_parser("dm", help="send a private message to a user")
    dm.add_argument("user_id")
    dm.add_argument("text")

    pr = sub.add_parser("profile", help="global profile of a user")
    pr.add_argument("user_id")

    w = sub.add_parser("watch", help="real-time stream (JSON lines) of new messages — Ctrl-C to quit")
    w.add_argument("channels", nargs="+", help="channel ids to watch")
    w.add_argument("--timeout", dest="watch_timeout", type=float, default=0,
                   help="stop after N seconds (0 = forever)")

    return p


def main() -> None:
    global _PRETTY, _TOKEN
    args = build_parser().parse_args()
    _PRETTY = args.pretty

    # discord.py logging -> stderr only, never stdout
    import logging
    logging.basicConfig(stream=sys.stderr, level=logging.ERROR)

    try:
        if args.mock:
            if args.command == "watch":
                for i in range(2):
                    emit({"ok": True, "event": "message", "mock": True,
                          "data": dict(MOCK_MESSAGE, id=str(1000000000000000012 + i),
                                       content=f"fake event {i + 1} (--mock)")})
                emit({"ok": True, "command": "watch", "mock": True,
                      "data": {"status": "stopped", "watched": [str(c) for c in args.channels]}})
                return
            emit(run_mock(args))
            return

        _TOKEN = resolve_token(args)
        if not _TOKEN:
            raise ValueError(
                "No token found. Set DISCORD_TOKEN in the environment, "
                "a .env file (see .env.example), or pass --token. "
                "Tip: --mock to test without a token."
            )
        emit(asyncio.run(run_with_client(_TOKEN, args)))
    except KeyboardInterrupt:
        emit({"ok": False, "command": args.command, "error": {"type": "KeyboardInterrupt", "message": "interrupted (Ctrl-C)"}})
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001 - every error must come out as clean JSON
        fail(args.command, exc)


if __name__ == "__main__":
    main()
