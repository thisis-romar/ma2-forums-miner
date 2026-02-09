#!/usr/bin/env python3
"""
Test script to validate the StateManager functionality.

This verifies that:
- StateManager can initialize a database
- Thread state can be stored and retrieved
- should_scrape() correctly identifies new vs existing threads
- get_visited_set() returns correct URLs
"""

import sys
import tempfile
from pathlib import Path

# Add scraper to path
sys.path.insert(0, str(Path(__file__).parent))

from scraper.state_manager import StateManager


def test_state_manager():
    """Test StateManager functionality."""
    
    print("=" * 80)
    print("Testing StateManager")
    print("=" * 80)
    
    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        test_db_path = f.name
    
    try:
        # Test 1: Initialize StateManager
        print("\n✅ Test 1: Initialize StateManager")
        state_manager = StateManager(test_db_path)
        assert state_manager is not None
        assert state_manager.get_thread_count() == 0
        print(f"   ✓ StateManager initialized with empty database")
        
        # Test 2: should_scrape returns True for new thread
        print("\n✅ Test 2: should_scrape() for new thread")
        should_scrape = state_manager.should_scrape("12345")
        assert should_scrape == True
        print(f"   ✓ should_scrape('12345') = {should_scrape} (expected True)")
        
        # Test 3: Add a thread state
        print("\n✅ Test 3: update_thread_state()")
        test_metadata = {
            'thread_id': '12345',
            'url': 'https://forum.malighting.com/forum/thread/12345-test-thread/',
            'title': 'Test Thread Title',
            'reply_count': 5,
            'view_count': 100
        }
        state_manager.update_thread_state(test_metadata)
        assert state_manager.get_thread_count() == 1
        print(f"   ✓ Thread state added successfully")
        print(f"   ✓ Thread count: {state_manager.get_thread_count()}")
        
        # Test 4: should_scrape returns False for existing thread
        print("\n✅ Test 4: should_scrape() for existing thread")
        should_scrape = state_manager.should_scrape("12345")
        assert should_scrape == False
        print(f"   ✓ should_scrape('12345') = {should_scrape} (expected False)")
        
        # Test 5: get_visited_set returns correct URLs
        print("\n✅ Test 5: get_visited_set()")
        visited = state_manager.get_visited_set()
        assert len(visited) == 1
        assert test_metadata['url'] in visited
        print(f"   ✓ get_visited_set() returned {len(visited)} URL(s)")
        print(f"   ✓ Contains expected URL: {test_metadata['url']}")
        
        # Test 6: Update existing thread state
        print("\n✅ Test 6: Update existing thread state")
        updated_metadata = {
            'thread_id': '12345',
            'url': 'https://forum.malighting.com/forum/thread/12345-test-thread/',
            'title': 'Updated Test Thread Title',
            'reply_count': 10,  # Updated
            'view_count': 200   # Updated
        }
        state_manager.update_thread_state(updated_metadata)
        assert state_manager.get_thread_count() == 1  # Should still be 1
        
        thread_state = state_manager.get_thread_state("12345")
        assert thread_state is not None
        assert thread_state.title == "Updated Test Thread Title"
        assert thread_state.reply_count == 10
        assert thread_state.view_count == 200
        print(f"   ✓ Thread state updated successfully")
        print(f"   ✓ New title: {thread_state.title}")
        print(f"   ✓ New reply_count: {thread_state.reply_count}")
        print(f"   ✓ New view_count: {thread_state.view_count}")
        
        # Test 7: Add multiple threads
        print("\n✅ Test 7: Add multiple threads")
        for i in range(67890, 67895):
            metadata = {
                'thread_id': str(i),
                'url': f'https://forum.malighting.com/forum/thread/{i}-thread-{i}/',
                'title': f'Thread {i}',
                'reply_count': i % 10,
                'view_count': i * 10
            }
            state_manager.update_thread_state(metadata)
        
        assert state_manager.get_thread_count() == 6  # 1 + 5 new threads
        visited = state_manager.get_visited_set()
        assert len(visited) == 6
        print(f"   ✓ Added 5 more threads")
        print(f"   ✓ Total thread count: {state_manager.get_thread_count()}")
        print(f"   ✓ get_visited_set() size: {len(visited)}")
        
        # Test 8: Verify get_thread_state retrieves correct data
        print("\n✅ Test 8: get_thread_state()")
        thread_state = state_manager.get_thread_state("67890")
        assert thread_state is not None
        assert thread_state.thread_id == "67890"
        assert thread_state.title == "Thread 67890"
        assert thread_state.reply_count == 0  # 67890 % 10 = 0
        print(f"   ✓ Retrieved thread state: {thread_state}")
        
        # Test 9: get_thread_state returns None for non-existent thread
        print("\n✅ Test 9: get_thread_state() for non-existent thread")
        thread_state = state_manager.get_thread_state("99999")
        assert thread_state is None
        print(f"   ✓ get_thread_state('99999') = None (expected)")
        
        print("\n" + "=" * 80)
        print("✅ All tests passed!")
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
        
    finally:
        # Clean up test database
        try:
            Path(test_db_path).unlink()
            print(f"\n🧹 Cleaned up test database: {test_db_path}")
        except:
            pass


if __name__ == "__main__":
    success = test_state_manager()
    sys.exit(0 if success else 1)
