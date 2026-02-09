#!/usr/bin/env python3
"""
Integration test for StateManager with ForumScraper.

This test validates that the scraper correctly uses StateManager
instead of manifest.json for state tracking.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Add scraper to path
sys.path.insert(0, str(Path(__file__).parent))

from scraper.scraper import ForumScraper


async def test_scraper_integration():
    """Test that ForumScraper integrates correctly with StateManager."""
    
    print("=" * 80)
    print("Integration Test: ForumScraper + StateManager")
    print("=" * 80)
    
    # Create temporary directories for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output_dir = tmpdir / "output" / "threads"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        test_db = tmpdir / "test_state.db"
        
        try:
            # Test 1: Initialize scraper with StateManager
            print("\n✅ Test 1: Initialize ForumScraper")
            scraper = ForumScraper(
                output_dir=output_dir,
                state_db_path=str(test_db)
            )
            assert scraper.state_manager is not None
            print(f"   ✓ Scraper initialized with StateManager")
            print(f"   ✓ State DB: {test_db}")
            print(f"   ✓ Output dir: {output_dir}")
            
            # Test 2: Verify StateManager is empty initially
            print("\n✅ Test 2: Verify empty state")
            thread_count = scraper.state_manager.get_thread_count()
            assert thread_count == 0
            print(f"   ✓ Initial thread count: {thread_count}")
            
            # Test 3: Verify should_scrape works
            print("\n✅ Test 3: Verify should_scrape()")
            should_scrape = scraper.state_manager.should_scrape("12345")
            assert should_scrape == True
            print(f"   ✓ should_scrape('12345') = {should_scrape}")
            
            # Test 4: Simulate a successful thread scrape
            print("\n✅ Test 4: Simulate thread state update")
            test_metadata = {
                'thread_id': '12345',
                'url': 'https://forum.malighting.com/forum/thread/12345-test/',
                'title': 'Test Thread',
                'reply_count': 5,
                'view_count': 100
            }
            scraper.state_manager.update_thread_state(test_metadata)
            
            thread_count = scraper.state_manager.get_thread_count()
            assert thread_count == 1
            print(f"   ✓ Thread state updated")
            print(f"   ✓ New thread count: {thread_count}")
            
            # Test 5: Verify should_scrape now returns False
            print("\n✅ Test 5: Verify should_scrape() after update")
            should_scrape = scraper.state_manager.should_scrape("12345")
            assert should_scrape == False
            print(f"   ✓ should_scrape('12345') = {should_scrape}")
            
            # Test 6: Verify get_visited_set works
            print("\n✅ Test 6: Verify get_visited_set()")
            visited = scraper.state_manager.get_visited_set()
            assert len(visited) == 1
            assert test_metadata['url'] in visited
            print(f"   ✓ get_visited_set() returned {len(visited)} URL")
            print(f"   ✓ Contains: {test_metadata['url']}")
            
            # Test 7: Test persistence - create new scraper instance
            print("\n✅ Test 7: Test state persistence")
            scraper2 = ForumScraper(
                output_dir=output_dir,
                state_db_path=str(test_db)
            )
            thread_count2 = scraper2.state_manager.get_thread_count()
            assert thread_count2 == 1
            print(f"   ✓ New scraper instance reads existing state")
            print(f"   ✓ Thread count: {thread_count2}")
            
            visited2 = scraper2.state_manager.get_visited_set()
            assert len(visited2) == 1
            print(f"   ✓ get_visited_set() still works: {len(visited2)} URL")
            
            print("\n" + "=" * 80)
            print("✅ All integration tests passed!")
            print("=" * 80)
            
            return True
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        except Exception as e:
            print(f"\n❌ Error during test: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = asyncio.run(test_scraper_integration())
    sys.exit(0 if success else 1)
