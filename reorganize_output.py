#!/usr/bin/env python3
"""Reorganize existing flat thread directories into the new hierarchy.

Moves threads from:
    output/threads/thread_{id}_{title}/

Into:
    output/threads/{asset_type_category}/{YYYY}/{YYYY-MM-DD}/thread_{id}_{title}/

Also patches each metadata.json:
    - Extracts post_date from post_text when missing
    - Adds asset_types, asset_type_category, and needs_rescrape fields
"""

import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── date extraction (mirrors utils.extract_date_from_post_text) ──────────

_MONTH_NAMES = (
    "January|February|March|April|May|June|"
    "July|August|September|October|November|December"
)

_POST_TEXT_DATE_RE = re.compile(
    rf"^({_MONTH_NAMES})\s+(\d{{1,2}}),\s+(\d{{4}})\s+at\s+(\d{{1,2}}):(\d{{2}})\s*([APap][Mm])"
)


def extract_date(post_text: str) -> Optional[str]:
    if not post_text:
        return None
    m = _POST_TEXT_DATE_RE.match(post_text)
    if not m:
        return None
    month_name, day, year, hour, minute, ampm = m.groups()
    try:
        dt = datetime.strptime(
            f"{month_name} {day}, {year} {hour}:{minute} {ampm.upper()}",
            "%B %d, %Y %I:%M %p",
        )
        return dt.isoformat()
    except ValueError:
        return None


def date_folder(post_date: Optional[str]):
    if not post_date:
        return ("unknown_year", "unknown_date")
    try:
        cleaned = post_date.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return (str(dt.year), dt.strftime("%Y-%m-%d"))
    except (ValueError, TypeError):
        match = re.match(r"(\d{4})-(\d{2})-(\d{2})", post_date)
        if match:
            return (match.group(1), match.group(0))
        return ("unknown_year", "unknown_date")


def asset_type_category(asset_types):
    if len(asset_types) == 0:
        return "no_assets"
    if len(asset_types) > 1:
        return "mixed"
    return asset_types[0].lstrip(".")


def main():
    output_dir = Path("output/threads")
    if not output_dir.exists():
        print("No output/threads directory found")
        sys.exit(1)

    # Only process flat thread_* directories (not already nested)
    thread_dirs = sorted([
        d for d in output_dir.iterdir()
        if d.is_dir() and d.name.startswith("thread_") and (d / "metadata.json").exists()
    ])

    if not thread_dirs:
        print("No flat thread directories to reorganize")
        return

    print(f"Found {len(thread_dirs)} flat thread directories to reorganize")

    stats = defaultdict(int)
    dates_extracted = 0
    needs_rescrape = 0

    for thread_dir in thread_dirs:
        meta_path = thread_dir / "metadata.json"
        with open(meta_path, "r") as f:
            meta = json.load(f)

        # ── 1. Extract date from post_text if post_date is missing ──
        post_date = meta.get("post_date")
        if not post_date:
            extracted = extract_date(meta.get("post_text", ""))
            if extracted:
                meta["post_date"] = extracted
                post_date = extracted
                dates_extracted += 1

        # ── 2. Compute asset type fields ──
        assets = meta.get("assets", [])
        types = sorted(set(
            Path(a["filename"]).suffix.lower()
            for a in assets
            if a.get("filename") and Path(a["filename"]).suffix
        ))
        category = asset_type_category(types)

        # Add file_type to each asset
        for a in assets:
            a["file_type"] = Path(a.get("filename", "")).suffix.lower()

        meta["asset_types"] = types
        meta["asset_type_category"] = category

        # ── 3. Flag threads needing re-scrape for replies ──
        has_posts_array = isinstance(meta.get("posts"), list) and len(meta.get("posts", [])) > 0
        meta["needs_rescrape"] = not has_posts_array
        if not has_posts_array:
            needs_rescrape += 1

        # ── 4. Write updated metadata ──
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2, sort_keys=True)

        # ── 5. Move to new location ──
        year, date_str = date_folder(post_date)
        new_parent = output_dir / category / year / date_str
        new_path = new_parent / thread_dir.name

        if new_path.exists():
            print(f"  SKIP (target exists): {thread_dir.name}")
            stats["skipped"] += 1
            continue

        new_parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(thread_dir), str(new_path))
        stats[category] += 1

    print()
    print("=" * 60)
    print("Reorganization complete")
    print("=" * 60)
    print(f"  Dates extracted from post_text: {dates_extracted}")
    print(f"  Threads needing re-scrape:      {needs_rescrape}")
    print(f"  Skipped (already at target):    {stats.get('skipped', 0)}")
    print()
    print("Threads moved by category:")
    for cat in sorted(stats):
        if cat != "skipped":
            print(f"  {cat:>12}: {stats[cat]}")

    # Show final directory tree (top 2 levels)
    print()
    print("New directory structure:")
    for cat_dir in sorted(output_dir.iterdir()):
        if cat_dir.is_dir():
            thread_count = sum(1 for _ in cat_dir.rglob("metadata.json"))
            print(f"  {cat_dir.name}/ ({thread_count} threads)")
            for year_dir in sorted(cat_dir.iterdir()):
                if year_dir.is_dir():
                    ycount = sum(1 for _ in year_dir.rglob("metadata.json"))
                    print(f"    {year_dir.name}/ ({ycount} threads)")


if __name__ == "__main__":
    main()
