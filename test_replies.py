#!/usr/bin/env python3
"""
Test script to verify that replies/posts are being captured correctly.
"""

import asyncio
import sys
import json
from pathlib import Path

# Add src to path to import the package
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ma2_forums_miner.scraper import ForumScraper


async def test_thread_with_replies():
    """Test scraping a thread to verify all posts (original + replies) are captured."""

    print("=" * 80)
    print("Testing Thread Scraping - Verifying Post/Reply Capture")
    print("=" * 80)

    # Initialize scraper
    scraper = ForumScraper()
    
    # Initialize HTTP client (normally done in run() method)
    import httpx
    scraper.client = httpx.AsyncClient(
        http2=True,
        timeout=30.0,
        follow_redirects=True,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    )

    # Test with thread 20248 which is known to exist
    thread_url = "https://forum.malighting.com/forum/thread/20248-abort-out-of-macro/"

    print(f"\n📥 Scraping: {thread_url}")
    
    try:
        metadata = await scraper.fetch_thread(thread_url)
    finally:
        # Close the client
        await scraper.client.aclose()

    if not metadata:
        print("❌ Failed to scrape thread")
        return False

    # Display results
    print(f"\n📊 Thread: {metadata.title}")
    print(f"   Thread ID: {metadata.thread_id}")
    print(f"   Author: {metadata.author}")
    print(f"   Post Date: {metadata.post_date}")
    print(f"   Replies Count: {metadata.replies}")
    print(f"   Posts Captured: {len(metadata.posts)}")
    
    # Check if posts field is populated
    if not metadata.posts:
        print("\n❌ NO POSTS CAPTURED!")
        print("   The posts field is empty or None")
        return False
    
    print(f"\n✅ POSTS FOUND: {len(metadata.posts)}")
    print(f"   Expected: {metadata.replies + 1} (original + replies)")
    
    # Display each post
    for i, post in enumerate(metadata.posts, 1):
        print(f"\n   Post #{post.post_number}:")
        print(f"      Author: {post.author}")
        print(f"      Date: {post.post_date}")
        print(f"      Text preview: {post.post_text[:100] if post.post_text else 'No text'}...")
    
    # Verify the data structure can be serialized to JSON
    print(f"\n🔍 Testing JSON serialization...")
    try:
        metadata_dict = metadata.to_dict()
        json_str = json.dumps(metadata_dict, indent=2)
        print(f"✅ Successfully serialized to JSON")
        print(f"   JSON size: {len(json_str)} characters")
        
        # Check if posts field exists in dict
        if 'posts' in metadata_dict:
            print(f"   ✅ 'posts' field exists in JSON")
            print(f"   ✅ Contains {len(metadata_dict['posts'])} posts")
        else:
            print(f"   ❌ 'posts' field missing from JSON!")
            return False
            
    except Exception as e:
        print(f"❌ JSON serialization failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    result = asyncio.run(test_thread_with_replies())
    sys.exit(0 if result else 1)
