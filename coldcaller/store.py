"""Cross-process state and serialized CSV/JSONL exports using SQLite."""
import csv
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .leads import Lead

TERMINAL = {"completed", "busy", "failed", "no-answer", "canceled", "error"}


class Store:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "state.sqlite3"
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, sid TEXT UNIQUE, phone TEXT, payload TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS tools (key TEXT PRIMARY KEY, output TEXT)")

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _export(self, db):
        rows = [json.loads(row[0]) for row in db.execute("SELECT payload FROM calls ORDER BY rowid")]
        fields = ["id", "sid", "name", "phone", "status", "outcome", "answers", "booked_time", "skip_reason"]
        # The SQLite writer lock also serializes exports across server and dialer.
        for suffix in ("jsonl", "csv"):
            target = self.directory / f"results.{suffix}"
            temp = target.with_suffix(f".{suffix}.tmp")
            with temp.open("w", newline="") as handle:
                if suffix == "jsonl":
                    for row in rows:
                        handle.write(json.dumps(row) + "\n")
                else:
                    writer = csv.DictWriter(handle, fields, extrasaction="ignore")
                    writer.writeheader()
                    for row in rows:
                        cleaned = {**row, "answers": json.dumps(row.get("answers", {}))}
                        # Prevent spreadsheet formula interpretation when opening lead-provided text.
                        for key, value in cleaned.items():
                            if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                                cleaned[key] = "'" + value
                        writer.writerow(cleaned)
            temp.replace(target)

    def add(self, lead: Lead, status: str, reason: str = "", campaign: dict | None = None) -> dict:
        row = {"id": uuid.uuid4().hex, "sid": None, **lead.as_dict(), "status": status,
               "outcome": "", "answers": {}, "booked_time": "", "skip_reason": reason,
               "created_at": datetime.now(timezone.utc).isoformat(), "campaign": campaign or {}}
        with self.transaction() as db:
            db.execute("INSERT INTO calls VALUES (?,?,?,?)", (row["id"], None, lead.phone, json.dumps(row)))
            self._export(db)
        return row

    def get(self, identifier: str) -> dict | None:
        with self.transaction() as db:
            row = db.execute("SELECT payload FROM calls WHERE id=? OR sid=?", (identifier, identifier)).fetchone()
            return json.loads(row[0]) if row else None

    def update(self, identifier: str, **changes) -> dict:
        with self.transaction() as db:
            raw = db.execute("SELECT payload FROM calls WHERE id=? OR sid=?", (identifier, identifier)).fetchone()
            if not raw:
                raise KeyError(identifier)
            row = json.loads(raw[0])
            if row["status"] in TERMINAL and changes.get("status") not in TERMINAL:
                changes.pop("status", None)
            row.update(changes)
            db.execute("UPDATE calls SET sid=?,payload=? WHERE id=?", (row["sid"], json.dumps(row), row["id"]))
            self._export(db)
            return row

    def attempts(self, phone: str) -> int:
        with self.transaction() as db:
            return sum(json.loads(row[0])["status"] not in {"skipped", "planned", "simulated"}
                       for row in db.execute("SELECT payload FROM calls WHERE phone=?", (phone,)))

    def tool_result(self, key: str) -> dict | None:
        with self.transaction() as db:
            row = db.execute("SELECT output FROM tools WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else None

    def save_tool_result(self, key: str, output: dict):
        with self.transaction() as db:
            db.execute("INSERT OR REPLACE INTO tools VALUES (?,?)", (key, json.dumps(output)))

    def add_dnc(self, path: Path, phone: str):
        with self.transaction():
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = path.read_text() if path.exists() else ""
            if phone not in {line.strip() for line in existing.splitlines()}:
                with path.open("a") as handle:
                    handle.write(("\n" if existing and not existing.endswith("\n") else "") + phone + "\n")

    def save_booking(self, booking: dict):
        with self.transaction():
            with (self.directory / "bookings.jsonl").open("a") as handle:
                handle.write(json.dumps(booking) + "\n")
