"""
Data models for MA2 Forums Miner.

This module defines typed data structures for representing scraped forum data.
Using dataclasses provides clear structure, type hints, and easy JSON serialization.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional


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
    
    Example:
        asset = Asset(
            filename="moving_fixtures.xml",
            url="https://forum.malighting.com/attachment/12345/",
            size=2048,
            download_count=15,
            checksum="sha256:abc123def456..."
        )
    """
    filename: str
    url: str
    size: Optional[int] = None
    download_count: Optional[int] = None
    checksum: Optional[str] = None
    
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
    including the initial post, statistics, and any attached files.
    
    Attributes:
        thread_id: Unique identifier for the thread (extracted from forum)
        title: Thread title/subject line
        url: Full URL to the thread on the forum
        author: Username of the thread creator
        post_date: ISO 8601 formatted date/time when the thread was created
                  Example: "2024-01-15T10:30:00Z"
        post_text: The full text content of the first/initial post in the thread
                  This is the main content we'll use for clustering and analysis
        replies: Number of replies/responses to the thread
        views: Number of times the thread has been viewed
        assets: List of Asset objects representing downloadable attachments
        
    Design note:
        We focus on the FIRST post's text because that typically contains the
        main question/topic. Reply text could be added in the future, but for
        initial clustering, the opening post is most representative.
    
    Example:
        metadata = ThreadMetadata(
            thread_id="30890",
            title="Moving Fixtures Between Layers",
            url="https://forum.malighting.com/thread/30890-...",
            author="johndoe",
            post_date="2024-01-15T10:30:00Z",
            post_text="How can I move fixtures from layer 1 to layer 2?",
            replies=5,
            views=1234,
            assets=[
                Asset(filename="macro.xml", url="https://...", ...)
            ]
        )
    """
    thread_id: str
    title: str
    url: str
    author: str
    post_date: Optional[str] = None
    post_text: str = ""
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
        data = asdict(self)
        # Ensure assets are properly converted (asdict handles this, but being explicit)
        data['assets'] = [asset.to_dict() if hasattr(asset, 'to_dict') else asset 
                         for asset in self.assets]
        return data
