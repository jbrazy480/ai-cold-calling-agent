"""Strict CSV parsing, with line numbers for operator errors."""
import csv
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Lead:
    name: str
    phone: str
    company: str = ""
    timezone: str = ""
    consent: str = "no"
    dnc: str = "no"
    notes: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def read_leads(path: str | Path) -> list[Lead]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, strict=True)
        expected = set(Lead.__dataclass_fields__)
        fields = reader.fieldnames or []
        if not {"name", "phone", "consent", "dnc"} <= set(fields):
            raise ValueError("CSV requires name, phone, consent, dnc columns")
        if len(fields) != len(set(fields)) or set(fields) - expected:
            raise ValueError("CSV contains duplicate or unknown columns")
        leads, seen = [], set()
        try:
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"CSV line {reader.line_num}: wrong column count")
                row = {key: value.strip() for key, value in row.items()}
                for key in ("consent", "dnc"):
                    row[key] = row[key].lower()
                    if row[key] not in {"yes", "no"}:
                        raise ValueError(f"CSV line {reader.line_num}: {key} must be yes or no")
                if not row["name"] or not row["phone"]:
                    raise ValueError(f"CSV line {reader.line_num}: name and phone cannot be empty")
                if row["phone"] in seen:
                    raise ValueError(f"CSV line {reader.line_num}: duplicate phone")
                seen.add(row["phone"])
                leads.append(Lead(**row))
        except csv.Error as exc:
            raise ValueError(f"CSV line {reader.line_num}: {exc}") from exc
        return leads
