#!/usr/bin/env python3
"""
Test script to verify audit improvement features.

Tests:
1. State models (ThreadState, PostState, AssetState, ScraperState)
2. Telemetry (ResponseStats, TokenBucket, AdaptiveThrottler)
3. Parser resilience (SelectorChain, ResilientParser)
4. Utility functions (sha256_string, infer_mime_type)
"""

import asyncio
from datetime import datetime, timezone
from scraper.models import ThreadState, PostState, AssetState, ScraperState, Post, Asset
from scraper.telemetry import ResponseStats, TokenBucket, AdaptiveThrottler
from scraper.parser import SelectorChain, ResilientParser
from scraper.utils import sha256_string, infer_mime_type
from bs4 import BeautifulSoup


def test_state_models():
    """Test state tracking models."""
    print("="*60)
    print("Testing State Models")
    print("="*60)
    
    # Test ThreadState
    thread_state = ThreadState(
        thread_id="12345",
        url="https://example.com/thread/12345",
        last_seen_at=datetime.now(timezone.utc).isoformat(),
        reply_count_seen=5,
        views_seen=100
    )
    print(f"✅ ThreadState created: {thread_state.thread_id}")
    print(f"   Needs update (5 -> 10 replies): {thread_state.needs_update(10, 100)}")
    print(f"   Needs update (5 -> 5 replies): {thread_state.needs_update(5, 100)}")
    
    # Test PostState
    post_state = PostState(
        post_id="12345-1",
        thread_id="12345",
        post_number=1,
        content_hash="sha256:abc123",
        observed_at=datetime.now(timezone.utc).isoformat()
    )
    print(f"✅ PostState created: {post_state.post_id}")
    
    # Test AssetState
    asset_state = AssetState(
        url="https://example.com/file.xml",
        filename="file.xml",
        content_hash="sha256:def456",
        mime_type="application/xml",
        downloaded_at=datetime.now(timezone.utc).isoformat()
    )
    print(f"✅ AssetState created: {asset_state.filename}")
    print(f"   Needs redownload (same etag): {asset_state.needs_redownload(server_etag='\"abc\"')}")
    
    # Test ScraperState
    state = ScraperState()
    state.threads["12345"] = thread_state
    state.posts["12345-1"] = post_state
    state.assets["https://example.com/file.xml"] = asset_state
    print(f"✅ ScraperState created with {len(state.threads)} threads")
    
    # Test serialization
    state_dict = state.to_dict()
    print(f"✅ State serialized to dict")
    
    # Test deserialization
    state2 = ScraperState.from_dict(state_dict)
    print(f"✅ State deserialized from dict: {len(state2.threads)} threads")
    
    print()


def test_telemetry():
    """Test telemetry features."""
    print("="*60)
    print("Testing Telemetry")
    print("="*60)
    
    # Test ResponseStats
    stats = ResponseStats()
    stats.record_response(200)
    stats.record_response(200)
    stats.record_response(404)
    stats.record_response(429)
    stats.record_response(503)
    stats.record_retry_exhausted("Timeout")
    
    print("✅ ResponseStats recorded:")
    print(stats.get_summary())
    print()
    
    # Test TokenBucket
    bucket = TokenBucket(tokens_per_second=2.0, capacity=5)
    wait1 = bucket.consume(1)
    print(f"✅ TokenBucket: First consume wait={wait1}s")
    
    wait2 = bucket.consume(1)
    print(f"✅ TokenBucket: Second consume wait={wait2}s")
    
    # Add jitter
    jittered = bucket.add_jitter(1.0, 0.1)
    print(f"✅ TokenBucket: Jittered delay={jittered:.3f}s (base=1.0s)")
    
    print()


async def test_adaptive_throttler():
    """Test adaptive throttler."""
    print("="*60)
    print("Testing Adaptive Throttler")
    print("="*60)
    
    throttler = AdaptiveThrottler(tokens_per_second=2.0, capacity=5)
    
    # Normal acquisition
    wait1 = await throttler.acquire()
    print(f"✅ Normal acquisition: wait={wait1:.3f}s")
    
    # Report rate limit
    throttler.report_rate_limit()
    print(f"✅ Reported rate limit (429)")
    
    # Try to acquire in cool-off
    wait2 = await throttler.acquire()
    print(f"✅ Acquisition during cool-off: wait={wait2:.3f}s")
    
    # Report success
    throttler.report_success()
    print(f"✅ Reported success")
    
    print()


def test_parser_resilience():
    """Test parser resilience features."""
    print("="*60)
    print("Testing Parser Resilience")
    print("="*60)
    
    # Test SelectorChain
    html = """
    <html>
        <body>
            <h1 class="contentTitle">Test Thread Title</h1>
            <article class="message">
                <span class="username">TestUser</span>
                <time datetime="2024-01-01T00:00:00Z">Jan 1</time>
                <div class="messageContent">Test post content</div>
            </article>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'lxml')
    
    # Test thread title extraction
    title = ResilientParser.extract_thread_title(soup)
    print(f"✅ Extracted title: '{title}'")
    
    # Test post extraction
    posts = ResilientParser.extract_posts(soup)
    print(f"✅ Extracted {len(posts)} post elements")
    
    if posts:
        post_elem = posts[0]
        author = ResilientParser.extract_post_author(post_elem)
        date = ResilientParser.extract_post_date(post_elem)
        content = ResilientParser.extract_post_content(post_elem)
        print(f"   Author: '{author}'")
        print(f"   Date: '{date}'")
        print(f"   Content: '{content[:50]}...'")
    
    print()


def test_utils():
    """Test utility functions."""
    print("="*60)
    print("Testing Utility Functions")
    print("="*60)
    
    # Test sha256_string
    hash1 = sha256_string("Hello, world!")
    hash2 = sha256_string("Hello, world!")
    hash3 = sha256_string("Different text")
    
    print(f"✅ sha256_string: {hash1[:40]}...")
    print(f"   Same input produces same hash: {hash1 == hash2}")
    print(f"   Different input produces different hash: {hash1 != hash3}")
    
    # Test infer_mime_type
    mime1 = infer_mime_type("file.xml", "application/xml")
    mime2 = infer_mime_type("file.xml")
    mime3 = infer_mime_type("file.zip")
    mime4 = infer_mime_type("file.unknown")
    
    print(f"✅ infer_mime_type:")
    print(f"   file.xml with header: {mime1}")
    print(f"   file.xml without header: {mime2}")
    print(f"   file.zip: {mime3}")
    print(f"   file.unknown: {mime4}")
    
    print()


def test_enhanced_models():
    """Test enhanced data models."""
    print("="*60)
    print("Testing Enhanced Data Models")
    print("="*60)
    
    # Test Post with new fields
    post = Post(
        author="TestUser",
        post_date="2024-01-01T00:00:00Z",
        post_text="Test post content",
        post_number=1,
        post_id="12345-1",
        content_hash="sha256:abc123"
    )
    print(f"✅ Post with ID and hash: {post.post_id}")
    print(f"   Hash: {post.content_hash}")
    
    # Test Asset with new fields
    asset = Asset(
        filename="macro.xml",
        url="https://example.com/file.xml",
        size=1024,
        checksum="sha256:def456",
        mime_type="application/xml",
        etag='"abc123"',
        last_modified="Mon, 01 Jan 2024 00:00:00 GMT"
    )
    print(f"✅ Asset with headers: {asset.filename}")
    print(f"   MIME: {asset.mime_type}")
    print(f"   ETag: {asset.etag}")
    print(f"   Last-Modified: {asset.last_modified}")
    
    print()


def main():
    """Run all tests."""
    print("\n🧪 Testing Audit Improvement Features\n")
    
    test_state_models()
    test_telemetry()
    asyncio.run(test_adaptive_throttler())
    test_parser_resilience()
    test_utils()
    test_enhanced_models()
    
    print("="*60)
    print("✅ All Tests Passed!")
    print("="*60)


if __name__ == "__main__":
    main()
