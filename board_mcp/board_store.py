"""A minimal append-only agent board (public demo slice).

Design contract, learned the hard way in production:

* **Append-only.** One JSON object per line. Nothing is ever rewritten except a row's `status`,
  and even that is expressed as a new `ack` row — history is never destroyed.
* **Silence is earned by acknowledging.** The delivery primitive (`digest`) prints every row whose
  status is still `open`, so a notification that fails to deliver simply re-sends next tick instead
  of disappearing. An earlier cursor-based design consumed rows *before* delivery was confirmed and
  silently ate a message; that class of bug is why this file exists.
* **Delivery has a second channel.** Every post is also written as a readable markdown file into
  the target's inbox directory, so an agent that prefers files keeps working unchanged.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timezone

KINDS = ("note", "request", "verdict", "finding", "handoff", "ack")
PRIORITIES = ("HIGH", "NORMAL", "LOW")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def slug(text: str, limit: int = 48) -> str:
    return (re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")[:limit] or "message")


class Board:
    """File-backed board. `root/board.jsonl` is the source of truth; `root/inbox/for_<agent>/`
    receives human-readable copies."""

    def __init__(self, root: str):
        self.root = root
        self.path = os.path.join(root, "board.jsonl")
        self.inbox = os.path.join(root, "inbox")
        os.makedirs(self.inbox, exist_ok=True)

    # ---------------------------------------------------------------- read
    def rows(self) -> list[dict]:
        if not os.path.isfile(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue          # a torn line must never break the board
        return out

    def read(self, to: str = "", sender: str = "", status: str = "", limit: int = 0) -> list[dict]:
        rows = self.rows()
        if to:
            t = to.lower()
            rows = [r for r in rows if t in [x.lower() for x in r["to"]]]
        if sender:
            rows = [r for r in rows if r["from"].lower() == sender.lower()]
        if status:
            rows = [r for r in rows if r.get("status") == status]
        return rows[-limit:] if limit else rows

    def digest(self, to: str) -> list[dict]:
        """Every row still awaiting this agent's ack (the delivery primitive)."""
        prio = {p: i for i, p in enumerate(PRIORITIES)}
        rows = [r for r in self.rows()
                if to.lower() in [x.lower() for x in r["to"]]
                and r["kind"] != "ack" and r.get("status") != "ack"]
        return sorted(rows, key=lambda r: (prio.get(r["priority"], 1), r["ts"]))

    # --------------------------------------------------------------- write
    def post(self, sender: str, to: list[str], topic: str, body: str, kind: str = "note",
             priority: str = "NORMAL", refs: list[str] | None = None,
             reply_to: str | None = None) -> dict:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        priority = priority.upper()
        if priority not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}")
        row = {
            "id": datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(2),
            "ts": now_iso(), "from": sender.lower(),
            "to": [x.lower() for x in to], "kind": kind, "priority": priority,
            "topic": topic.strip(), "body": body.strip(),
            "refs": refs or [], "reply_to": reply_to, "status": "open",
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        for agent in row["to"]:
            d = os.path.join(self.inbox, f"for_{agent}")
            os.makedirs(d, exist_ok=True)
            ts = datetime.fromisoformat(row["ts"]).strftime("%Y-%m-%d_%H-%M")
            with open(os.path.join(d, f"{ts}_{row['priority']}_{slug(row['topic'])}.md"),
                      "w", encoding="utf-8", newline="\n") as f:
                f.write(f"# [{row['priority']}] {row['from']} -> {agent}\n\n"
                        f"**id:** `{row['id']}`  \n**kind:** {row['kind']}\n\n{row['body']}\n")
        return row

    def ack(self, row_id: str, by: str, note: str | None = None) -> dict:
        rows = self.rows()
        target = next((r for r in rows if r["id"] == row_id), None)
        if not target:
            raise KeyError(row_id)
        target["status"] = "ack"
        ack = {
            "id": datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(2),
            "ts": now_iso(), "from": by.lower(), "to": [target["from"]], "kind": "ack",
            "priority": "NORMAL", "topic": f"ack {row_id}: {target['topic'][:60]}",
            "body": note or f"acknowledged {row_id}", "refs": [row_id],
            "reply_to": row_id, "status": "ack",
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ack, ensure_ascii=False) + "\n")
            for r in rows:
                if r["id"] == row_id:
                    pass
        # rewrite ONLY the acked row's status, keeping every line intact
        with open(self.path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return ack
