"""
Data models for MA2 Forums Miner.

This module defines typed data structures for representing scraped forum data.
Using dataclasses provides clear structure, type hints, and easy JSON serialization.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Post:
    """
    Represents a single post (original or reply) in a thread.

    Attributes:
        author: Username of the post author
        post_date: ISO 8601 formatted date/time when posted
        post_text: The full text content of this post
        post_number: Position in thread (1 = original post, 2+ = replies)

    Example:
        post = Post(
            author="johndoe",
            post_date="2024-01-15T10:30:00Z",
            post_text="Here's how to solve this problem...",
            post_number=2
        )
    """
    author: str
    post_date: Optional[str] = None
    post_text: str = ""
    post_number: int = 1

    def to_dict(self) -> dict:
        """Convert the post to a dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class Asset:
    """
    Represents a downloadable attachment from a forum thread.

    Attributes:
        filename: The name of the file (e.g., "macro.xml", "show.gz")
        url: The full URL where the file can be downloaded
        size: Size of the file in bytes (populated after download)
        download_count: Number of times this asset has been downloaded (from forum metadata)
        checksum: SHA256 hash of the file content for integrity verification
                 Format: "sha256:abc123..." for consistency
        post_number: Which post this asset was attached to (1 = original, 2+ = replies)
                    None if unable to determine

    Example:
        asset = Asset(
            filename="moving_fixtures.xml",
            url="https://forum.malighting.com/attachment/12345/",
            size=2048,
            download_count=15,
            checksum="sha256:abc123def456...",
            post_number=1
        )
    """
    filename: str
    url: str
    size: Optional[int] = None
    download_count: Optional[int] = None
    checksum: Optional[str] = None
    post_number: Optional[int] = None
    
    def to_dict(self) -> dict:
        """
        Convert the asset to a dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the asset with all fields.
        """
        return asdict(self)


@dataclass
class ThreadMetadata:
    """
    Complete metadata for a forum thread.

    This represents all the information we extract from a single forum thread,
    including ALL posts (original + replies), statistics, and attached files.

    Attributes:
        thread_id: Unique identifier for the thread (extracted from forum)
        title: Thread title/subject line
        url: Full URL to the thread on the forum
        author: Username of the thread creator (from first post)
        post_date: ISO 8601 formatted date/time when the thread was created
                  Example: "2024-01-15T10:30:00Z"
        post_text: DEPRECATED - Use posts[0].post_text instead
                  Kept for backward compatibility with existing data
        posts: List of Post objects (original post + all replies)
               posts[0] is the original post
               posts[1:] are the replies in chronological order
        replies: Number of replies/responses to the thread
        views: Number of times the thread has been viewed
        assets: List of Asset objects representing downloadable attachments

    Design note:
        We now capture the COMPLETE discussion thread including all replies.
        The first post (posts[0]) contains the main question/topic.
        All replies (posts[1:]) provide answers, follow-ups, and context.

    Example:
        metadata = ThreadMetadata(
            thread_id="30890",
            title="Moving Fixtures Between Layers",
            url="https://forum.malighting.com/thread/30890-...",
            author="johndoe",
            post_date="2024-01-15T10:30:00Z",
            post_text="",  # Deprecated - left empty
            posts=[
                Post(author="johndoe", post_text="How can I move fixtures?", post_number=1),
                Post(author="helper", post_text="You can use this macro...", post_number=2)
            ],
            replies=1,
            views=1234,
            assets=[...]
        )
    """
    thread_id: str
    title: str
    url: str
    author: str
    post_date: Optional[str] = None
    post_text: str = ""  # Deprecated - kept for backward compatibility
    posts: List[Post] = field(default_factory=list)
    replies: int = 0
    views: int = 0
    assets: List[Asset] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """
        Convert the thread metadata to a dictionary for JSON serialization.
        
        This recursively converts the ThreadMetadata and all nested Asset
        objects into plain dictionaries that can be written to JSON.
        
        Returns:
            Dictionary representation with all fields serialized.
        """
        # asdict() automatically handles nested dataclasses recursively
        return asdict(self)
