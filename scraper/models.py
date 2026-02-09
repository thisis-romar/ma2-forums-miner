"""
Data models for MA2 Forums Miner.

This module defines typed data structures for representing scraped forum data.
Using dataclasses provides clear structure, type hints, and easy JSON serialization.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class Post:
    """
    Represents a single post (original or reply) in a thread.

    Attributes:
        author: Username of the post author
        post_date: ISO 8601 formatted date/time when posted
        post_text: The full text content of this post
        post_number: Position in thread (1 = original post, 2+ = replies)
        post_id: Unique identifier for this post (format: "{thread_id}-{post_number}")
        content_hash: SHA256 hash of post content for change detection

    Example:
        post = Post(
            author="johndoe",
            post_date="2024-01-15T10:30:00Z",
            post_text="Here's how to solve this problem...",
            post_number=2,
            post_id="30890-2",
            content_hash="sha256:abc123..."
        )
    """
    author: str
    post_date: Optional[str] = None
    post_text: str = ""
    post_number: int = 1
    post_id: Optional[str] = None
    content_hash: Optional[str] = None

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
        mime_type: MIME type from Content-Type header or inferred from file extension
        last_modified: Last-Modified HTTP header value (if available)
        etag: ETag HTTP header value (if available)

    Example:
        asset = Asset(
            filename="moving_fixtures.xml",
            url="https://forum.malighting.com/attachment/12345/",
            size=2048,
            download_count=15,
            checksum="sha256:abc123def456...",
            post_number=1,
            mime_type="application/xml",
            last_modified="Mon, 14 Jan 2024 16:20:00 GMT",
            etag='"abc123"'
        )
    """
    filename: str
    url: str
    size: Optional[int] = None
    download_count: Optional[int] = None
    checksum: Optional[str] = None
    post_number: Optional[int] = None
    mime_type: Optional[str] = None
    last_modified: Optional[str] = None
    etag: Optional[str] = None
    
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
        schema_version: Version of this metadata schema (for future migrations)
        scraped_at: ISO 8601 timestamp when this data was scraped

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
            assets=[...],
            schema_version="1.0",
            scraped_at="2024-01-15T10:30:00Z"
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
    schema_version: str = "1.0"
    scraped_at: Optional[str] = None
    
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


# -------------------------------------------------------
# STATE TRACKING MODELS
# -------------------------------------------------------
# These models implement multi-level state tracking for:
# - Detecting content changes (thread updates, post edits)
# - Avoiding unnecessary re-downloads
# - Content fingerprinting for change detection
# -------------------------------------------------------


@dataclass
class ThreadState:
    """
    State tracking for a forum thread to detect changes over time.
    
    This model enables delta scraping at a more granular level than just
    "thread seen/unseen". It tracks thread statistics to detect when threads
    have been updated with new replies or views.
    
    Attributes:
        thread_id: Unique identifier for the thread
        url: Thread URL for reference
        last_seen_at: ISO 8601 timestamp of last successful scrape
        reply_count_seen: Number of replies when last scraped
        views_seen: Number of views when last scraped
        last_modified: ISO 8601 timestamp from thread's last modification (if available)
        
    Example:
        state = ThreadState(
            thread_id="30890",
            url="https://forum.../thread/30890-...",
            last_seen_at="2024-01-15T10:30:00Z",
            reply_count_seen=5,
            views_seen=1234,
            last_modified="2024-01-14T16:20:00Z"
        )
    """
    thread_id: str
    url: str
    last_seen_at: str  # ISO 8601 timestamp
    reply_count_seen: int = 0
    views_seen: int = 0
    last_modified: Optional[str] = None  # ISO 8601 timestamp if available
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def needs_update(self, current_replies: int, current_views: int) -> bool:
        """
        Determine if thread needs to be re-scraped based on changed statistics.
        
        Args:
            current_replies: Current reply count from forum
            current_views: Current view count from forum
            
        Returns:
            True if thread has new replies (indicating new content to scrape)
        """
        # Re-scrape if reply count increased (new content available)
        return current_replies > self.reply_count_seen


@dataclass
class PostState:
    """
    State tracking for individual posts to detect edits and changes.
    
    Tracks the content hash of each post to detect when posts are edited
    after initial scrape. This enables re-scraping edited content.
    
    Attributes:
        post_id: Unique identifier for the post (thread_id + post_number)
        thread_id: Thread this post belongs to
        post_number: Position in thread (1 = original, 2+ = replies)
        content_hash: SHA256 hash of post content for change detection
        observed_at: ISO 8601 timestamp when this version was observed
        edited_at: ISO 8601 timestamp of last edit (if available from forum)
        
    Example:
        state = PostState(
            post_id="30890-1",
            thread_id="30890",
            post_number=1,
            content_hash="sha256:abc123...",
            observed_at="2024-01-15T10:30:00Z",
            edited_at=None
        )
    """
    post_id: str  # Format: "{thread_id}-{post_number}"
    thread_id: str
    post_number: int
    content_hash: str  # SHA256 hash of post content
    observed_at: str  # ISO 8601 timestamp
    edited_at: Optional[str] = None  # ISO 8601 timestamp if available
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class AssetState:
    """
    State tracking for downloadable assets to detect changes and avoid re-downloads.
    
    Tracks asset metadata including content hash, MIME type, and HTTP headers
    (ETag, Last-Modified) for efficient change detection.
    
    Attributes:
        url: Full URL of the asset
        filename: Local filename where asset is saved
        content_hash: SHA256 hash of asset content for integrity verification
        mime_type: MIME type from Content-Type header
        size: File size in bytes
        downloaded_at: ISO 8601 timestamp of successful download
        last_modified: Last-Modified header value (if provided by server)
        etag: ETag header value (if provided by server)
        
    Example:
        state = AssetState(
            url="https://forum.../attachment/12345/",
            filename="macro.xml",
            content_hash="sha256:abc123...",
            mime_type="application/xml",
            size=2048,
            downloaded_at="2024-01-15T10:30:00Z",
            last_modified="Mon, 14 Jan 2024 16:20:00 GMT",
            etag='"abc123"'
        )
    """
    url: str
    filename: str
    content_hash: str  # SHA256 hash
    mime_type: Optional[str] = None
    size: Optional[int] = None
    downloaded_at: Optional[str] = None  # ISO 8601 timestamp
    last_modified: Optional[str] = None  # HTTP Last-Modified header
    etag: Optional[str] = None  # HTTP ETag header
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def needs_redownload(self, server_last_modified: Optional[str] = None, 
                         server_etag: Optional[str] = None) -> bool:
        """
        Determine if asset needs to be re-downloaded based on server headers.
        
        Args:
            server_last_modified: Last-Modified header from server
            server_etag: ETag header from server
            
        Returns:
            True if asset has changed on server (based on headers)
        """
        # If we have no stored headers, can't determine change
        if not self.last_modified and not self.etag:
            return False
        
        # Check ETag first (more reliable)
        if self.etag and server_etag:
            return self.etag != server_etag
        
        # Fall back to Last-Modified
        if self.last_modified and server_last_modified:
            return self.last_modified != server_last_modified
        
        return False


@dataclass
class ScraperState:
    """
    Complete state tracking for the scraper across all threads, posts, and assets.
    
    This replaces the simple manifest.json (list of URLs) with a comprehensive
    state model that enables:
    - Fine-grained delta scraping (only re-scrape changed content)
    - Content change detection (edited posts, updated threads)
    - Efficient asset management (avoid re-downloading unchanged files)
    
    Attributes:
        schema_version: Version of this state schema (for future migrations)
        last_updated: ISO 8601 timestamp of last state update
        threads: Dictionary mapping thread_id to ThreadState
        posts: Dictionary mapping post_id to PostState
        assets: Dictionary mapping asset URL to AssetState
        
    Example:
        state = ScraperState(
            schema_version="1.0",
            last_updated="2024-01-15T10:30:00Z",
            threads={"30890": ThreadState(...)},
            posts={"30890-1": PostState(...)},
            assets={"https://...": AssetState(...)}
        )
    """
    schema_version: str = "1.0"
    last_updated: Optional[str] = None  # ISO 8601 timestamp
    threads: Dict[str, ThreadState] = field(default_factory=dict)
    posts: Dict[str, PostState] = field(default_factory=dict)
    assets: Dict[str, AssetState] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "schema_version": self.schema_version,
            "last_updated": self.last_updated,
            "threads": {k: v.to_dict() for k, v in self.threads.items()},
            "posts": {k: v.to_dict() for k, v in self.posts.items()},
            "assets": {k: v.to_dict() for k, v in self.assets.items()}
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ScraperState':
        """Create ScraperState from dictionary (for loading from JSON)."""
        threads = {
            k: ThreadState(**v) for k, v in data.get("threads", {}).items()
        }
        posts = {
            k: PostState(**v) for k, v in data.get("posts", {}).items()
        }
        assets = {
            k: AssetState(**v) for k, v in data.get("assets", {}).items()
        }
        
        return cls(
            schema_version=data.get("schema_version", "1.0"),
            last_updated=data.get("last_updated"),
            threads=threads,
            posts=posts,
            assets=assets
        )
