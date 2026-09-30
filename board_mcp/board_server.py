"""Agent board as MCP tools — SDK 2.0 `MCPServer` (no FastMCP).

Exposes the append-only board over stdio so any MCP-capable agent (Hermes, Codex, Claude Code,
qwen-code …) can read, post and acknowledge work without a human relaying messages.

Run:   python board_mcp/board_server.py          (stdio server)
Env:   BOARD_ROOT   directory for board.jsonl + inbox/   (default: ./board_data)

Tools: board_read · board_post · board_ack · board_digest · board_stats · board_protocol
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server import MCPServer          # SDK >= 2.0 — v2 high-level API
from board_store import Board, KINDS, PRIORITIES

ROOT = os.environ.get("BOARD_ROOT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "board_data"))
BOARD = Board(ROOT)

mcp = MCPServer(
    "gnv-board",
    instructions=(
        "Append-only agent board for multi-agent handoff. Read what is addressed to you, post work, "
        "and ACK every row you receive — an unacked row is both an open loop and a repeating "
        "notification. No human needs to relay messages."
    ),
)


@mcp.tool()
def board_read(to: str = "", sender: str = "", status: str = "", limit: int = 0) -> dict:
    """Read board rows, optionally filtered by recipient (`to`), sender (`sender`) and/or
    `status` (open|ack). `limit` keeps the last N."""
    rows = BOARD.read(to=to, sender=sender, status=status, limit=limit)
    return {"count": len(rows), "rows": rows}


@mcp.tool()
def board_post(from_agent: str, to: str, topic: str, body: str, kind: str = "note",
               priority: str = "NORMAL", refs: str = "", reply_to: str = "") -> dict:
    """Post a message (append-only; also delivered as markdown into inbox/for_<agent>/).
    `to` accepts several agents separated by spaces or commas. kind: note|request|verdict|finding|handoff."""
    targets = [x for x in to.replace(",", " ").split() if x]
    if not targets:
        return {"error": "`to` requires at least one agent"}
    if kind not in KINDS:
        return {"error": f"kind must be one of {list(KINDS)}"}
    if priority.upper() not in PRIORITIES:
        return {"error": f"priority must be one of {list(PRIORITIES)}"}
    row = BOARD.post(from_agent, targets, topic, body, kind=kind, priority=priority,
                     refs=[r.strip() for r in refs.split(",") if r.strip()],
                     reply_to=reply_to or None)
    return {"posted": row}


@mcp.tool()
def board_ack(row_id: str, by: str, note: str = "") -> dict:
    """Acknowledge a row: appends an ack row and flips the original to status=ack.
    Originals are never deleted."""
    try:
        ack = BOARD.ack(row_id, by, note or None)
    except KeyError:
        return {"error": f"no row with id {row_id}"}
    return {"acked": row_id, "by": ack["from"]}


@mcp.tool()
def board_digest(to: str) -> dict:
    """Everything still awaiting `to`'s acknowledgement (status=open). This is the delivery
    primitive — an empty result means nothing is owed."""
    rows = BOARD.digest(to)
    return {"count": len(rows), "open_rows": rows}


@mcp.tool()
def board_stats() -> dict:
    """Board health: row count, open count, per-agent pending, and the tail of recent rows."""
    rows = BOARD.rows()
    agents = sorted({a for r in rows for a in r["to"]})
    return {
        "board_path": BOARD.path,
        "rows": len(rows),
        "open_total": len([r for r in rows if r.get("status") != "ack" and r["kind"] != "ack"]),
        "pending_by_agent": {a: len(BOARD.digest(a)) for a in agents},
        "recent": rows[-8:],
    }


@mcp.tool()
def board_protocol() -> dict:
    """The board contract: append-only source of truth, row schema, duties, delivery guarantee."""
    return {
        "contract": [
            "1. One append-only source of truth (board.jsonl); never hand-edit derived views.",
            "2. Post, don't relay: anything another agent needs becomes a row.",
            "3. Ack every row received — an unacked row is an open loop and a repeating notification.",
            "4. Attach refs (paths/URLs) so the other side verifies instead of trusting prose.",
            "5. Delivery is at-least-once: digest prints open rows, so failed sends re-send.",
        ],
        "root": ROOT,
    }


if __name__ == "__main__":
    asyncio.run(mcp.run_stdio_async())
