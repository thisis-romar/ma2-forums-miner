#!/usr/bin/env python3
"""
Test script to examine forum pagination structure.
This helps us understand if pagination detection is working correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add scraper to path
sys.path.insert(0, str(Path(__file__).parent))

import httpx
from bs4 import BeautifulSoup

BOARD_URL = "https://forum.malighting.com/forum/board/35-grandma2-macro-share/"


async def test_pagination():
    """Fetch the forum board and examine its pagination structure."""

    print("=" * 80)
    print("Testing Forum Pagination Structure")
    print("=" * 80)

    async with httpx.AsyncClient(http2=True, follow_redirects=True, timeout=30.0) as client:
        print(f"\n📥 Fetching: {BOARD_URL}")
        response = await client.get(BOARD_URL)

        if response.status_code != 200:
            print(f"❌ Failed: HTTP {response.status_code}")
            return

        print(f"✅ Success: HTTP {response.status_code}")

        soup = BeautifulSoup(response.text, "lxml")

        # Check pagination structure
        print("\n" + "=" * 80)
        print("Pagination Analysis")
        print("=" * 80)

        # Method 1: Look for .pageNavigation elements
        pagination_divs = soup.select('.pageNavigation')
        print(f"\n1. Found {len(pagination_divs)} .pageNavigation elements")

        if pagination_divs:
            for i, div in enumerate(pagination_divs[:2]):  # Show first 2
                print(f"\n   Pagination element {i+1}:")
                print(f"   {div.prettify()[:500]}")

        # Method 2: Look for pagination links
        pagination_links = soup.select('.pageNavigation a')
        print(f"\n2. Found {len(pagination_links)} .pageNavigation a links")

        if pagination_links:
            print("\n   Page links found:")
            for link in pagination_links[:10]:  # Show first 10
                href = link.get('href', '')
                text = link.text.strip()
                print(f"   - {text:20s} → {href}")

        # Method 3: Look for any links with /page/ in them
        all_page_links = soup.find_all('a', href=lambda x: x and '/page/' in x)
        print(f"\n3. Found {len(all_page_links)} links containing '/page/'")

        if all_page_links:
            print("\n   All /page/ links:")
            for link in all_page_links[:15]:
                href = link.get('href', '')
                text = link.text.strip()
                print(f"   - {text:20s} → {href}")

        # Method 4: Check thread list
        print("\n" + "=" * 80)
        print("Thread List Analysis")
        print("=" * 80)

        # Try different selectors for thread links
        selectors = [
            'a.wbbTopicLink',
            'a[href*="/forum/thread/"]',
            '.messageGroupLink',
            'a.topicLink',
        ]

        for selector in selectors:
            threads = soup.select(selector)
            print(f"\n   Selector '{selector}': {len(threads)} threads")
            if threads and len(threads) > 0:
                print(f"   First 3 thread URLs:")
                for thread in threads[:3]:
                    href = thread.get('href', '')
                    title = thread.text.strip()[:50]
                    print(f"   - {title} → {href}")

        # Method 5: Look for "Next" button
        print("\n" + "=" * 80)
        print("Navigation Buttons")
        print("=" * 80)

        next_buttons = soup.find_all('a', class_=lambda x: x and 'next' in x.lower() if x else False)
        print(f"\n   Found {len(next_buttons)} 'next' buttons")

        for btn in next_buttons:
            print(f"   - Class: {btn.get('class')}")
            print(f"     Text: {btn.text.strip()}")
            print(f"     Href: {btn.get('href')}")

        # Check for any element with "page" in class or id
        print("\n" + "=" * 80)
        print("Elements with 'page' in class/id")
        print("=" * 80)

        page_elements = soup.find_all(lambda tag:
            (tag.get('class') and any('page' in str(c).lower() for c in tag.get('class'))) or
            (tag.get('id') and 'page' in str(tag.get('id')).lower())
        )
        print(f"\n   Found {len(page_elements)} elements with 'page' in class/id")

        for elem in page_elements[:5]:
            print(f"\n   Element: {elem.name}")
            print(f"   Class: {elem.get('class')}")
            print(f"   ID: {elem.get('id')}")
            if elem.name == 'a':
                print(f"   Href: {elem.get('href')}")


if __name__ == "__main__":
    asyncio.run(test_pagination())
