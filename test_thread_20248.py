#!/usr/bin/env python3
"""
Test script to scrape thread 20248 which has known attachments.
This verifies that our CSS selectors correctly find and download attachments.

NOTE: This is a manual integration test requiring network access.
For automated tests, see tests/
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from ma2_forums_miner.scraper import ForumScraper


async def test_thread_20248():
    """Test scraping thread 20248 with known attachment."""

    print("=" * 80)
    print("Testing Thread 20248 - Known to have CopyIfoutput.xml attachment")
    print("=" * 80)

    scraper = ForumScraper()

    thread_url = "https://forum.malighting.com/forum/thread/20248-abort-out-of-macro/"

    # Initialize the HTTP client (required before calling fetch_thread)
    import httpx
    scraper.client = httpx.AsyncClient(
        http2=True, timeout=30.0, follow_redirects=True,
        headers={'User-Agent': 'Mozilla/5.0 (compatible; MA2Miner/1.0)'}
    )

    try:
        print(f"\nScraping: {thread_url}")
        metadata = await scraper.fetch_thread(thread_url)

        if not metadata:
            print("Failed to scrape thread")
            return False

        print(f"\nThread: {metadata.title}")
        print(f"   Author: {metadata.author}")
        print(f"   Assets found: {len(metadata.assets)}")

        if metadata.assets:
            print("\nATTACHMENTS FOUND:")
            for asset in metadata.assets:
                print(f"   - {asset.filename} ({asset.url})")

            output_dir = Path("output/test_thread_20248")
            output_dir.mkdir(parents=True, exist_ok=True)

            success = await scraper.download_asset(metadata.assets[0], output_dir)
            if success:
                print(f"Downloaded: {metadata.assets[0].filename}")
                print(f"   Size: {metadata.assets[0].size} bytes")
                print(f"   SHA256: {metadata.assets[0].checksum}")
                return True
            else:
                print("Failed to download attachment")
                return False
        else:
            print("\nNO ATTACHMENTS FOUND - CSS selectors may not match")
            return False
    finally:
        await scraper.client.aclose()


if __name__ == "__main__":
    result = asyncio.run(test_thread_20248())
    sys.exit(0 if result else 1)
