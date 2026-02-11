#!/usr/bin/env python3
"""
Generate detailed statistics from scraped threads.
Creates a comprehensive README section with per-thread details.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict


def load_thread_metadata(thread_dir: Path) -> Dict[str, Any]:
    """Load metadata.json from a thread directory."""
    metadata_file = thread_dir / "metadata.json"
    if not metadata_file.exists():
        return None

    with open(metadata_file, 'r') as f:
        return json.load(f)


def get_file_size_str(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    if size_bytes is None:
        return "unknown"

    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def analyze_threads() -> Dict[str, Any]:
    """Analyze all scraped threads and generate statistics."""

    output_dir = Path("output/threads")
    if not output_dir.exists():
        print("❌ No output/threads directory found")
        return None

    # Find thread dirs: support both flat (thread_*) and date-nested (YYYY/YYYY-MM-DD/thread_*)
    thread_dirs = sorted([
        d for d in output_dir.rglob("thread_*")
        if d.is_dir() and (d / "metadata.json").exists()
    ])
    print(f"📊 Analyzing {len(thread_dirs)} threads...")

    stats = {
        'total_threads': 0,
        'threads_with_attachments': 0,
        'threads_without_attachments': 0,
        'total_files': 0,
        'file_types': defaultdict(int),
        'total_size': 0,
        'threads': [],
        'year_distribution': defaultdict(int),
        'oldest_thread_id': float('inf'),
        'newest_thread_id': 0,
        # Asset-type grouping: maps extension -> list of thread entries
        'threads_by_asset_type': defaultdict(list),
        # Threads containing more than one distinct file extension
        'multi_type_threads': [],
        # Threads that need re-scraping (no posts array / missing replies)
        'needs_rescrape': 0,
    }

    for thread_dir in thread_dirs:
        metadata = load_thread_metadata(thread_dir)
        if not metadata:
            continue

        stats['total_threads'] += 1

        # Extract thread ID from URL or directory name
        thread_id = metadata.get('thread_id', '')
        if thread_id:
            try:
                tid = int(thread_id)
                stats['oldest_thread_id'] = min(stats['oldest_thread_id'], tid)
                stats['newest_thread_id'] = max(stats['newest_thread_id'], tid)
            except ValueError:
                pass

        # Analyze assets
        assets = metadata.get('assets', [])
        has_attachments = len(assets) > 0

        if has_attachments:
            stats['threads_with_attachments'] += 1
        else:
            stats['threads_without_attachments'] += 1

        # Count files and sizes
        actual_files = []
        for asset in assets:
            filename = asset.get('filename', '')
            if filename:
                stats['total_files'] += 1

                # Count file type
                ext = Path(filename).suffix.lower()
                stats['file_types'][ext] += 1

                # Check if file actually exists
                file_path = thread_dir / filename
                if file_path.exists():
                    size = file_path.stat().st_size
                    stats['total_size'] += size
                    actual_files.append({
                        'filename': filename,
                        'size': size,
                        'exists': True
                    })
                else:
                    actual_files.append({
                        'filename': filename,
                        'size': asset.get('size'),
                        'exists': False
                    })

        # Extract year from post_date
        post_date = metadata.get('post_date', '')
        if post_date:
            year = post_date[:4] if len(post_date) >= 4 else 'unknown'
            stats['year_distribution'][year] += 1

        # Collect unique asset types for this thread
        thread_asset_types = sorted(set(
            Path(a.get('filename', '')).suffix.lower()
            for a in assets
            if Path(a.get('filename', '')).suffix
        ))

        # Store thread info
        thread_info = {
            'id': thread_id,
            'title': metadata.get('title', 'Unknown'),
            'author': metadata.get('author', 'Unknown'),
            'date': post_date,
            'url': metadata.get('url', ''),
            'replies': metadata.get('replies', 0),
            'views': metadata.get('views', 0),
            'attachment_count': len(assets),
            'files': actual_files,
            'asset_types': thread_asset_types,
        }
        stats['threads'].append(thread_info)

        # Group this thread under each of its asset types
        for ext in thread_asset_types:
            stats['threads_by_asset_type'][ext].append(thread_info)

        # Flag threads with more than one distinct file type
        if len(thread_asset_types) > 1:
            stats['multi_type_threads'].append(thread_info)

        # Track threads needing re-scrape for replies
        if metadata.get('needs_rescrape', False):
            stats['needs_rescrape'] += 1

    return stats


def generate_readme_section(stats: Dict[str, Any]) -> str:
    """Generate README markdown section with statistics."""

    if not stats:
        return "No statistics available."

    # Sort threads by ID
    stats['threads'].sort(key=lambda x: int(x['id']) if x['id'].isdigit() else 0)

    md = []

    # Summary table
    md.append("## 📊 Scraping Statistics\n")
    md.append("### Summary\n")
    md.append("| Metric | Count |")
    md.append("|--------|-------|")
    total = stats['total_threads'] or 1  # avoid division by zero
    md.append(f"| **Total Threads** | {stats['total_threads']} |")
    md.append(f"| **Threads with Attachments** | {stats['threads_with_attachments']} ({stats['threads_with_attachments']/total*100:.1f}%) |")
    md.append(f"| **Threads without Attachments** | {stats['threads_without_attachments']} ({stats['threads_without_attachments']/total*100:.1f}%) |")
    md.append(f"| **Total Attachment Files** | {stats['total_files']} |")
    md.append(f"| **Total Downloaded Size** | {get_file_size_str(stats['total_size'])} |")

    if stats['oldest_thread_id'] != float('inf'):
        md.append(f"| **Thread ID Range** | {stats['oldest_thread_id']} - {stats['newest_thread_id']} |")

    if stats['needs_rescrape']:
        md.append(f"| **Needs Re-scrape (missing replies)** | {stats['needs_rescrape']} ({stats['needs_rescrape']/total*100:.1f}%) |")

    md.append("")

    # File types breakdown
    if stats['file_types']:
        md.append("### File Types\n")
        md.append("| Extension | Count |")
        md.append("|-----------|-------|")
        for ext, count in sorted(stats['file_types'].items()):
            ext_display = ext if ext else "(no extension)"
            md.append(f"| `{ext_display}` | {count} |")
        md.append("")

    # Year distribution
    if stats['year_distribution']:
        md.append("### Threads by Year\n")
        md.append("| Year | Threads |")
        md.append("|------|---------|")
        for year in sorted(stats['year_distribution'].keys(), reverse=True):
            count = stats['year_distribution'][year]
            md.append(f"| {year} | {count} |")
        md.append("")

    # Threads grouped by asset type
    if stats['threads_by_asset_type']:
        md.append("### Threads by Asset Type\n")
        for ext in sorted(stats['threads_by_asset_type'].keys()):
            threads = stats['threads_by_asset_type'][ext]
            md.append(f"#### `{ext}` ({len(threads)} threads)\n")
            md.append("| ID | Title | Date | Files |")
            md.append("|----|-------|------|-------|")
            for t in threads:
                title = t['title'][:45] + "..." if len(t['title']) > 45 else t['title']
                date = t['date'][:10] if t['date'] else "Unknown"
                ext_files = [f['filename'] for f in t['files'] if f['filename'].lower().endswith(ext)]
                files_str = ", ".join(f"`{fn}`" for fn in ext_files) or "*-*"
                md.append(f"| {t['id']} | {title} | {date} | {files_str} |")
            md.append("")

    # Multi-type threads
    if stats['multi_type_threads']:
        md.append("### Threads with Multiple Asset Types\n")
        md.append("| ID | Title | Date | Asset Types |")
        md.append("|----|-------|------|-------------|")
        for t in stats['multi_type_threads']:
            title = t['title'][:45] + "..." if len(t['title']) > 45 else t['title']
            date = t['date'][:10] if t['date'] else "Unknown"
            types_str = ", ".join(f"`{x}`" for x in t['asset_types'])
            md.append(f"| {t['id']} | {title} | {date} | {types_str} |")
        md.append("")

    # Detailed thread list
    md.append("### Detailed Thread List\n")
    md.append("| ID | Title | Date | Files | Attachments |")
    md.append("|----|-------|------|-------|-------------|")

    for thread in stats['threads']:
        tid = thread['id']
        title = thread['title'][:50] + "..." if len(thread['title']) > 50 else thread['title']
        date = thread['date'][:10] if thread['date'] else "Unknown"
        file_count = thread['attachment_count']

        # Format attachments
        if thread['files']:
            attachments = []
            for f in thread['files']:
                fname = f['filename']
                size_str = get_file_size_str(f['size']) if f['size'] else "?"
                status = "✅" if f['exists'] else "❌"
                attachments.append(f"{status} `{fname}` ({size_str})")
            attachments_str = "<br>".join(attachments)
        else:
            attachments_str = "*none*"

        md.append(f"| {tid} | {title} | {date} | {file_count} | {attachments_str} |")

    md.append("")

    return "\n".join(md)


def main():
    """Main entry point."""
    print("=" * 80)
    print("MA2 Forums Miner - Statistics Generator")
    print("=" * 80)
    print()

    stats = analyze_threads()

    if not stats:
        print("❌ Failed to generate statistics")
        sys.exit(1)

    # Generate README section
    readme_section = generate_readme_section(stats)

    # Save to file
    output_file = Path("STATISTICS.md")
    with open(output_file, 'w') as f:
        f.write(readme_section)

    print(f"\n✅ Statistics saved to: {output_file}")
    print(f"\n📊 Summary:")
    print(f"   - Total threads: {stats['total_threads']}")
    print(f"   - With attachments: {stats['threads_with_attachments']}")
    print(f"   - Total files: {stats['total_files']}")
    print(f"   - Total size: {get_file_size_str(stats['total_size'])}")

    # Also print the section
    print("\n" + "=" * 80)
    print("README Section Preview:")
    print("=" * 80)
    print(readme_section)


if __name__ == "__main__":
    main()
