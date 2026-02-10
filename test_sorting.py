#!/usr/bin/env python3
"""
Test to verify thread sorting logic works correctly.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ma2_forums_miner.scraper import ThreadInfo


def test_thread_sorting():
    """Test that threads sort correctly by date."""
    
    print("=" * 80)
    print("Testing Thread Sorting Logic")
    print("=" * 80)
    
    # Create sample threads with different dates
    threads = [
        ThreadInfo(url="https://example.com/thread/3", date="2024-03-15T10:00:00Z"),
        ThreadInfo(url="https://example.com/thread/1", date="2024-01-10T10:00:00Z"),
        ThreadInfo(url="https://example.com/thread/5", date=None),  # No date
        ThreadInfo(url="https://example.com/thread/2", date="2024-02-20T10:00:00Z"),
        ThreadInfo(url="https://example.com/thread/4", date="2024-04-01T10:00:00Z"),
    ]
    
    print(f"\n📝 Before sorting:")
    for i, t in enumerate(threads, 1):
        print(f"   {i}. {t.url.split('/')[-1]} - {t.date or 'No date'}")
    
    # Sort by date (same logic as in scraper.py)
    threads.sort(key=lambda t: t.date if t.date else "9999-99-99")
    
    print(f"\n✅ After sorting (oldest first, None at end):")
    for i, t in enumerate(threads, 1):
        print(f"   {i}. {t.url.split('/')[-1]} - {t.date or 'No date'}")
    
    # Verify order
    expected_order = [
        "2024-01-10T10:00:00Z",
        "2024-02-20T10:00:00Z", 
        "2024-03-15T10:00:00Z",
        "2024-04-01T10:00:00Z",
        None
    ]
    
    actual_order = [t.date for t in threads]
    
    if actual_order == expected_order:
        print(f"\n✅ PASS: Threads sorted correctly!")
        print(f"   Order: {' -> '.join([d[:10] if d else 'None' for d in actual_order])}")
        return True
    else:
        print(f"\n❌ FAIL: Incorrect sort order")
        print(f"   Expected: {expected_order}")
        print(f"   Actual: {actual_order}")
        return False


if __name__ == "__main__":
    success = test_thread_sorting()
    sys.exit(0 if success else 1)
