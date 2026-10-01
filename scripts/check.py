#!/usr/bin/env python3
"""Monthly maintenance check.

1. Fetch every URL in README.md and in data/events.csv; report any that do
   not return HTTP 2xx/3xx.
2. Report dates in data/events.csv that need attention: confirmed deadlines
   that have passed, confirmed events that have taken place, and expected
   deadlines that fall within the next 60 days (the organiser's call is
   probably out and should be verified).

Writes a Markdown report (--report PATH) and exits with
  0  nothing to report
  1  at least one broken link
  2  no broken links, but dates need attention
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
CSV = ROOT / "data" / "events.csv"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/128.0 Safari/537.36")
URL_RE = re.compile(r"https?://[^\s)>`\"']+")


def fetch_once(url: str) -> int | str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # noqa: BLE001
        return type(e).__name__


def ok(code: int | str) -> bool:
    return isinstance(code, int) and 200 <= code < 400


def fetch(url: str) -> tuple[str, int | str]:
    """Fetch a URL; retry once after a pause on a 5xx or a network error."""
    code = fetch_once(url)
    if not ok(code) and (not isinstance(code, int) or code >= 500):
        time.sleep(5)
        code = fetch_once(url)
    return url, code


def all_urls() -> list[str]:
    urls = {u.rstrip(".,") for u in URL_RE.findall(README.read_text(encoding="utf-8"))}
    with CSV.open(encoding="utf-8", newline="") as f:
        urls |= {r["url"] for r in csv.DictReader(f) if r["url"]}
    return sorted(urls)


def check_links() -> list[tuple[str, int | str]]:
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(fetch, all_urls()))
    return [(u, c) for u, c in results if not ok(c)]


def check_dates(today: dt.date) -> dict[str, list[str]]:
    out = {"passed": [], "held": [], "verify": []}
    with CSV.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            start = dt.date.fromisoformat(r["start"])
            end = dt.date.fromisoformat(r["end"] or r["start"])
            line = f"{r['name']} ({start.isoformat()}) — {r['url']}"
            if r["status"] == "confirmed":
                if r["item"] in ("deadline", "opens") and start < today:
                    out["passed"].append(line)
                elif r["item"] == "event" and end < today:
                    out["held"].append(line)
            elif r["status"] == "expected":
                if start <= today + dt.timedelta(days=60):
                    out["verify"].append(line)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", type=pathlib.Path)
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    args = ap.parse_args()

    bad = check_links()
    dates = check_dates(args.today)

    lines = [f"# Maintenance check — {args.today.isoformat()}", ""]
    lines.append("## Links")
    if bad:
        lines += [f"- `{c}` {u}" for u, c in bad]
    else:
        lines.append("All links return HTTP 2xx/3xx.")
    lines += ["", "## Dates"]
    sections = [
        ("passed", "Confirmed deadlines that have passed (replace with the next edition when the call is out)"),
        ("held", "Confirmed events that have taken place (update the entry)"),
        ("verify", "Expected deadlines within 60 days (check whether the call is out; if so, replace the row with confirmed dates)"),
    ]
    any_dates = False
    for key, title in sections:
        if dates[key]:
            any_dates = True
            lines += [f"### {title}"] + [f"- {l}" for l in dates[key]] + [""]
    if not any_dates:
        lines.append("No dates need attention.")
    report = "\n".join(lines) + "\n"
    print(report)
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    if bad:
        return 1
    if any_dates:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
