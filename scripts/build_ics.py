#!/usr/bin/env python3
"""Build innovation-calendar.ics from data/events.csv.

Only rows with status "confirmed" are written. Events are all-day entries
spanning start..end; deadlines and opening dates are single all-day entries
with the stated time in the summary. Run with --check to verify that the
committed .ics matches the CSV.
"""
import csv
import datetime as dt
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "events.csv"
ICS = ROOT / "innovation-calendar.ics"
PRODID = "-//innovation-phd-calendar//EN"
CAL_NAME = "Innovation, science & IP economics: conferences and deadlines"


def fold(line: str) -> str:
    """Fold a content line at 75 octets (RFC 5545 §3.1)."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not parts else 74
        if len(cur) + len(b) > limit:
            parts.append(cur)
            cur = b
        else:
            cur += b
    parts.append(cur)
    return "\r\n ".join(p.decode("utf-8") for p in parts)


def esc(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def uid(row: dict) -> str:
    key = f"{row['name']}|{row['item']}|{row['start']}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16] + "@innovation-phd-calendar"


def build(rows) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:{esc(CAL_NAME)}"]
    # fixed stamp so the file only changes when the data change
    stamp = "20260101T000000Z"
    for r in rows:
        if r["status"] != "confirmed":
            continue
        start = dt.date.fromisoformat(r["start"])
        end = dt.date.fromisoformat(r["end"] or r["start"])
        label = {"deadline": "Deadline: ", "opens": "Opens: "}.get(r["item"], "")
        summary = label + r["name"]
        if r["time_note"]:
            summary += f" ({r['time_note']})"
        desc_parts = [f"Type: {r['kind']}"]
        if r["location"]:
            desc_parts.append(f"Location: {r['location']}")
        desc_parts.append(f"Source: {r['url']}")
        desc_parts.append("From github.com/amc-econ/innovation-phd-calendar")
        lines += ["BEGIN:VEVENT",
                  f"UID:{uid(r)}",
                  f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
                  f"DTEND;VALUE=DATE:{end + dt.timedelta(days=1):%Y%m%d}",
                  f"SUMMARY:{esc(summary)}",
                  f"DESCRIPTION:{esc(chr(10).join(desc_parts))}",
                  f"URL:{r['url']}"]
        if r["location"]:
            lines.append(f"LOCATION:{esc(r['location'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"


def main() -> int:
    with CSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    text = build(rows)
    if "--check" in sys.argv:
        current = ICS.read_bytes().decode("utf-8") if ICS.exists() else ""
        if current != text:
            print("innovation-calendar.ics is out of date: run scripts/build_ics.py")
            return 1
        print("innovation-calendar.ics matches data/events.csv")
        return 0
    ICS.write_bytes(text.encode("utf-8"))
    n = sum(1 for r in rows if r["status"] == "confirmed")
    print(f"wrote {ICS.name} with {n} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
