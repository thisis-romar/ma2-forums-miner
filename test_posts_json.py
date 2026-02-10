#!/usr/bin/env python3
"""
Test to verify that ThreadMetadata properly serializes posts field to JSON.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ma2_forums_miner.models import Post, ThreadMetadata, Asset


def test_posts_serialization():
    """Test that posts field is properly included in JSON output."""
    
    print("=" * 80)
    print("Testing Posts Serialization")
    print("=" * 80)
    
    # Create sample posts
    posts = [
        Post(
            author="john_doe",
            post_date="2024-01-15T10:30:00Z",
            post_text="This is my question about macros...",
            post_number=1
        ),
        Post(
            author="helper_user",
            post_date="2024-01-15T14:20:00Z",
            post_text="Here's how you can solve it...",
            post_number=2
        ),
        Post(
            author="another_user",
            post_date="2024-01-16T09:00:00Z",
            post_text="Thanks! This helped me too.",
            post_number=3
        )
    ]
    
    # Create thread metadata with posts
    metadata = ThreadMetadata(
        thread_id="12345",
        title="How to use macros",
        url="https://forum.example.com/thread/12345",
        author="john_doe",
        post_date="2024-01-15T10:30:00Z",
        post_text="This is my question about macros...",  # Deprecated but kept
        posts=posts,
        replies=2,  # 2 replies after original
        views=150,
        assets=[]
    )
    
    print(f"\n📝 Thread Metadata:")
    print(f"   Thread ID: {metadata.thread_id}")
    print(f"   Title: {metadata.title}")
    print(f"   Author: {metadata.author}")
    print(f"   Replies: {metadata.replies}")
    print(f"   Posts captured: {len(metadata.posts)}")
    
    # Convert to dict
    print(f"\n🔄 Converting to dictionary...")
    metadata_dict = metadata.to_dict()
    
    # Check if posts field exists
    if 'posts' not in metadata_dict:
        print(f"❌ FAIL: 'posts' field missing from dictionary!")
        return False
    
    print(f"✅ 'posts' field exists in dictionary")
    print(f"   Contains {len(metadata_dict['posts'])} posts")
    
    # Convert to JSON
    print(f"\n📄 Converting to JSON...")
    try:
        json_str = json.dumps(metadata_dict, indent=2)
        print(f"✅ JSON serialization successful")
        print(f"   JSON size: {len(json_str)} characters")
    except Exception as e:
        print(f"❌ FAIL: JSON serialization failed: {e}")
        return False
    
    # Verify JSON structure
    print(f"\n🔍 Verifying JSON structure...")
    parsed = json.loads(json_str)
    
    if 'posts' not in parsed:
        print(f"❌ FAIL: 'posts' field missing from JSON!")
        return False
    
    if len(parsed['posts']) != 3:
        print(f"❌ FAIL: Expected 3 posts, got {len(parsed['posts'])}")
        return False
    
    # Check first post structure
    first_post = parsed['posts'][0]
    required_fields = ['author', 'post_date', 'post_text', 'post_number']
    for field in required_fields:
        if field not in first_post:
            print(f"❌ FAIL: Post missing '{field}' field")
            return False
    
    print(f"✅ All posts have required fields")
    
    # Display sample JSON excerpt
    print(f"\n📋 Sample JSON output:")
    print(f"```json")
    sample_json = {
        "thread_id": parsed['thread_id'],
        "title": parsed['title'],
        "posts": [
            {
                "author": p['author'],
                "post_number": p['post_number'],
                "post_text": p['post_text'][:50] + "..."
            }
            for p in parsed['posts'][:2]
        ]
    }
    print(json.dumps(sample_json, indent=2))
    print(f"```")
    
    print(f"\n✅ PASS: Posts field properly serialized to JSON!")
    return True


if __name__ == "__main__":
    success = test_posts_serialization()
    sys.exit(0 if success else 1)
