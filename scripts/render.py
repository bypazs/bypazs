#!/usr/bin/env python3
"""Render the profile's CVE section and counters from data/cves.yml.

Usage:
    python scripts/render.py          # rewrite README.md and banners in place
    python scripts/render.py --check  # exit 1 if anything is out of date (CI)
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "cves.yml"
README = ROOT / "README.md"
BANNERS = [ROOT / "banner.svg", ROOT / "banner-light.svg"]

REQUIRED = ("id", "url", "product", "class", "detail")
CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$")
START, END = "<!-- cve:start -->", "<!-- cve:end -->"


def load() -> list[dict]:
    entries = yaml.safe_load(DATA.read_text(encoding="utf-8")) or []
    errors, seen = [], set()
    for i, e in enumerate(entries, 1):
        missing = [k for k in REQUIRED if not e.get(k)]
        if missing:
            errors.append(f"entry {i}: missing {', '.join(missing)}")
        cid = e.get("id", "")
        if cid and not CVE_RE.match(cid):
            errors.append(f"entry {i}: bad CVE id {cid!r}")
        if cid in seen:
            errors.append(f"entry {i}: duplicate {cid}")
        seen.add(cid)
        if not str(e.get("url", "")).startswith("https://"):
            errors.append(f"entry {i}: url must be https")
    if errors:
        sys.exit("data/cves.yml is invalid:\n  " + "\n  ".join(errors))
    # newest first: by year, then sequence number
    return sorted(
        entries,
        key=lambda e: tuple(int(x) for x in e["id"].split("-")[1:]),
        reverse=True,
    )


def section(entries: list[dict]) -> str:
    featured = [e for e in entries if e.get("featured")]
    others = [e for e in entries if not e.get("featured")]
    out = [START, ""]

    if featured:
        out += [
            "### Featured",
            "",
            "| CVE | Product | Vulnerability | CVSS | Role |",
            "|:----|:--------|:--------------|:----:|:----:|",
        ]
        out += [
            f"| [{e['id']}]({e['url']}) | {e['product']} | {e['detail']} "
            f"| {e.get('cvss', '—')} | {e.get('role', '—')} |"
            for e in featured
        ]
        out.append("")

    if others:
        years = sorted({int(e["id"].split("-")[1]) for e in others})
        span = f"{years[0]} – {years[-1]}" if len(years) > 1 else str(years[0])
        out += [
            "<details>",
            f"<summary><b>{span} — {len(others)} CVEs</b> (click to expand)</summary>",
            "",
            "<br/>",
            "",
            "| CVE | Product | Vulnerability |",
            "|:----|:--------|:--------------|",
        ]
        out += [f"| [{e['id']}]({e['url']}) | {e['product']} | {e['detail']} |" for e in others]
        out += ["", "</details>", ""]

    by_class = Counter(e["class"] for e in entries)
    summary = " · ".join(f"{c} ×{n}" for c, n in by_class.most_common())
    out += [f"**By class:** {summary}", "", END]
    return "\n".join(out)


def render_readme(text: str, entries: list[dict]) -> str:
    n = len(entries)
    if START not in text or END not in text:
        sys.exit(f"README.md is missing the {START} / {END} markers")
    text = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        lambda _: section(entries),
        text,
        flags=re.S,
    )
    text = re.sub(r"badge/CVEs-\d+-", f"badge/CVEs-{n}-", text)
    text = re.sub(r"\d+ published CVEs", f"{n} published CVEs", text)
    text = re.sub(r"eWPTX, \d+ CVEs", f"eWPTX, {n} CVEs", text)
    return text


def render_banner(text: str, n: int) -> str:
    return re.sub(r'(id="cve-count"[^>]*>)\d+(<)', rf"\g<1>{n}\g<2>", text)


def main() -> None:
    check = "--check" in sys.argv
    entries = load()
    targets = [(README, lambda t: render_readme(t, entries))]
    targets += [(b, lambda t: render_banner(t, len(entries))) for b in BANNERS if b.exists()]

    stale = []
    for path, fn in targets:
        old = path.read_text(encoding="utf-8")
        new = fn(old)
        if new != old:
            stale.append(path.name)
            if not check:
                path.write_text(new, encoding="utf-8")

    if check and stale:
        sys.exit(f"Out of date: {', '.join(stale)} — run `python scripts/render.py`")
    print(f"{len(entries)} CVEs · " + (f"updated {', '.join(stale)}" if stale else "up to date"))


if __name__ == "__main__":
    main()
