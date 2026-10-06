#!/usr/bin/env python3
"""Find submission deadlines a fixed number of days ahead and write a reminder.

Reads data/events.csv, selects rows with item "deadline" whose start date is
exactly --days after --today, and writes a plain-text reminder to --out.
When run inside GitHub Actions it also sets the outputs "found" and "subject".
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "events.csv"
REPO = "github.com/amc-econ/innovation-conferences-calendar"


def set_output(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("reminder.md"))
    args = ap.parse_args()

    target = args.today + dt.timedelta(days=args.days)
    with CSV.open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if r["item"] == "deadline" and r["start"] == target.isoformat()]

    if not rows:
        print(f"No deadline on {target.isoformat()} ({args.days} days after {args.today.isoformat()}).")
        set_output("found", "false")
        return 0

    blocks = []
    for r in rows:
        when = f"{target.day} {target:%B %Y}"
        if r["time_note"]:
            when += f" ({r['time_note']})"
        status = ("Confirmed by the organiser." if r["status"] == "confirmed"
                  else "Expected date, not yet confirmed. Check the website.")
        blocks.append(f"{r['name']}\nDeadline: {when}\nStatus: {status}\nLink: {r['url']}")
    body = (f"These submission deadlines are {args.days} days away, on {target.day} {target:%B %Y}.\n\n"
            + "\n\n".join(blocks) + f"\n\nFrom {REPO}\n")
    subject = "Deadline in one week: " + ", ".join(r["name"] for r in rows)

    args.out.write_text(body, encoding="utf-8")
    print(body)
    set_output("found", "true")
    set_output("subject", subject)
    return 0


if __name__ == "__main__":
    sys.exit(main())
