#!/usr/bin/env python3
"""
Test script to scrape thread 20248 which has known attachments.
This verifies that our CSS selectors correctly find and download attachments.
"""

import asyncio
import sys
from pathlib import Path

# Add scraper to path
sys.path.insert(0, str(Path(__file__).parent))

from scraper.scraper import ForumScraper


async def test_thread_20248():
    """Test scraping thread 20248 with known attachment."""

    print("=" * 80)
    print("Testing Thread 20248 - Known to have CopyIfoutput.xml attachment")
    print("=" * 80)

    # Initialize scraper
    scraper = ForumScraper()

    # Thread URL
    thread_url = "https://forum.malighting.com/forum/thread/20248-abort-out-of-macro/"

    # Scrape just this one thread
    print(f"\n📥 Scraping: {thread_url}")
    metadata = await scraper.scrape_thread(thread_url)

    if not metadata:
        print("❌ Failed to scrape thread")
        return False

    # Display results
    print(f"\n📊 Thread: {metadata.title}")
    print(f"   Author: {metadata.author}")
    print(f"   Assets found: {len(metadata.assets)}")

    if metadata.assets:
        print("\n✅ ATTACHMENTS FOUND:")
        for asset in metadata.assets:
            print(f"   - {asset.filename}")
            print(f"     URL: {asset.url}")
            print(f"     Downloads: {asset.download_count}")

        # Try to download the first attachment
        if metadata.assets:
            print(f"\n📥 Testing download of: {metadata.assets[0].filename}")
            output_dir = Path("output/test_thread_20248")
            output_dir.mkdir(parents=True, exist_ok=True)

            success = await scraper.download_asset(metadata.assets[0], output_dir)
            if success:
                print(f"✅ Successfully downloaded to: {output_dir / metadata.assets[0].filename}")
                print(f"   Size: {metadata.assets[0].size} bytes")
                print(f"   SHA256: {metadata.assets[0].checksum}")
                return True
            else:
                print(f"❌ Failed to download attachment")
                return False
    else:
        print("\n❌ NO ATTACHMENTS FOUND")
        print("   This means our CSS selectors are not matching the HTML!")
        print("   Expected to find: CopyIfoutput.xml")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_thread_20248())
    sys.exit(0 if result else 1)
