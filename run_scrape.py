#!/usr/bin/env python3
"""
Entry point for the MA2 Forums Miner scraper.

This script initializes and runs the async forum scraper.
It's designed to be simple and straightforward - all the complexity
is handled inside the ForumScraper class.

Usage:
    python run_scrape.py

What this does:
    1. Imports the ForumScraper class
    2. Creates a scraper instance with default settings
    3. Runs the async scraping process using asyncio.run()

The scraper will:
    - Load the manifest to track already-scraped threads (delta scraping)
    - Discover all threads from the forum board
    - Download metadata and attachments for new threads only
    - Save each thread to its own folder in output/threads/
    - Update the manifest after each successful thread

Output structure:
    output/threads/thread_{id}_{title}/
        metadata.json       # Thread metadata and asset info
        attachment1.xml     # Downloaded files
        attachment2.zip
        ...

For GitHub Actions:
    This script is designed to be run in CI/CD pipelines.
    It's idempotent - running it multiple times safely handles
    incremental updates without duplicating work.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path to import the package
# This allows running the script from repository root
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ma2_forums_miner.scraper import ForumScraper


def main():
    """
    Main entry point.
    
    This function simply creates a scraper and runs it.
    All configuration is handled by the ForumScraper class.
    """
    print("MA2 Forums Miner - Async Scraper")
    print("="*60)
    print()
    
    # Create scraper with default settings
    scraper = ForumScraper()
    
    # Run the async scraper
    # asyncio.run() handles:
    # - Creating an event loop
    # - Running the coroutine
    # - Cleaning up the event loop
    asyncio.run(scraper.run())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Scraping interrupted by user")
        print("   Manifest has been saved - progress is preserved!")
        print("   Run again to continue where you left off.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
