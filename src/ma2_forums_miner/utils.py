"""
Utility functions for the MA2 Forums Miner.

This module provides helper functions for file operations and path management.
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Union, Optional


def sha256_file(file_path: Union[str, Path]) -> str:
    """
    Calculate the SHA256 checksum of a file.
    
    This function reads the file in chunks to handle large files efficiently
    without loading the entire file into memory at once.
    
    Args:
        file_path: Path to the file to checksum
        
    Returns:
        SHA256 checksum string in the format "sha256:hexdigest"
        Example: "sha256:abc123def456..."
        
    How it works:
        1. Create a SHA256 hash object
        2. Read the file in 8KB chunks (efficient for both small and large files)
        3. Update the hash with each chunk
        4. Return the final hexadecimal digest with "sha256:" prefix
        
    Why chunks?
        Reading in chunks means we can hash files of any size without
        running out of memory. An 8KB chunk size is a good balance between
        I/O overhead and memory usage.
    
    Example:
        checksum = sha256_file("/path/to/file.xml")
        # Returns: "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    """
    # -------------------------------------------------------
    # Create SHA256 hasher instance
    # -------------------------------------------------------
    sha256_hash = hashlib.sha256()
    
    # -------------------------------------------------------
    # Read and hash the file in chunks
    # -------------------------------------------------------
    # Using 8192 bytes (8KB) as chunk size - this is a common default
    # that balances memory usage with I/O efficiency
    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files efficiently
        for byte_block in iter(lambda: f.read(8192), b""):
            sha256_hash.update(byte_block)
    
    # -------------------------------------------------------
    # Return formatted checksum
    # -------------------------------------------------------
    # Format: "sha256:hexdigest" for consistency and clarity
    return f"sha256:{sha256_hash.hexdigest()}"


def safe_thread_folder(thread_id: str, title: str, max_length: int = 50) -> str:
    """
    Generate a filesystem-safe folder name for a thread.
    
    This function creates a folder name that:
    1. Is safe for all filesystems (Windows, Linux, macOS)
    2. Is human-readable (includes the thread title)
    3. Is unique (includes the thread ID)
    4. Has a reasonable length limit
    
    Args:
        thread_id: The unique thread identifier (e.g., "30890")
        title: The thread title (e.g., "Moving Fixtures Between Layers?")
        max_length: Maximum length for the title portion (default: 50 chars)
        
    Returns:
        A filesystem-safe folder name in the format "thread_{id}_{slug}"
        Example: "thread_30890_Moving_Fixtures_Between_Layers"
        
    Implementation details:
        - Removes/replaces problematic characters: / \\ : * ? " < > |
        - Converts spaces to underscores for easier command-line usage
        - Truncates title to max_length to avoid filesystem path limits
        - Always includes thread_id to ensure uniqueness
        
    Why this format?
        - "thread_" prefix makes it clear what these folders contain
        - Thread ID first enables easy sorting and lookup
        - Slugified title makes folders human-readable
        - Underscores instead of hyphens match Python naming conventions
    
    Example:
        folder = safe_thread_folder("30890", "Moving Fixtures Between Layers?")
        # Returns: "thread_30890_Moving_Fixtures_Between_Layers"
        
        folder = safe_thread_folder("12345", "How to: Export/Import Shows?")
        # Returns: "thread_12345_How_to_ExportImport_Shows"
    """
    # -------------------------------------------------------
    # STEP 1: Clean the title for filesystem safety
    # -------------------------------------------------------
    # Remove or replace characters that are problematic on various filesystems:
    # - Forward slash (/) and backslash (\): directory separators
    # - Colon (:): drive letters on Windows, illegal on macOS
    # - Asterisk (*), Question mark (?), Quotes ("): wildcards/special chars
    # - Angle brackets (< >): I/O redirection in shells
    # - Pipe (|): command chaining in shells
    # - Multiple spaces: replace with single space for cleanliness
    
    # Remove illegal characters
    clean_title = re.sub(r'[/\\:*?"<>|]', '', title)
    
    # Replace multiple spaces with single space
    clean_title = re.sub(r'\s+', ' ', clean_title)
    
    # -------------------------------------------------------
    # STEP 2: Convert to slug format
    # -------------------------------------------------------
    # Replace spaces with underscores for easier command-line usage
    # and consistency with Python naming conventions
    slug = clean_title.strip().replace(' ', '_')
    
    # -------------------------------------------------------
    # STEP 3: Truncate to maximum length
    # -------------------------------------------------------
    # Limit length to avoid filesystem path limits (typically 255 chars per component)
    # We keep it shorter (default 50) to leave room for the thread_id prefix
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip('_')
    
    # -------------------------------------------------------
    # STEP 4: Combine thread ID with slug
    # -------------------------------------------------------
    # Format: "thread_{id}_{title_slug}"
    # The thread_id ensures uniqueness even if titles are similar
    folder_name = f"thread_{thread_id}_{slug}"
    
    return folder_name


def load_thread_metadata(thread_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Load metadata.json from a thread directory.
    
    Args:
        thread_dir: Path to the thread directory
        
    Returns:
        Dictionary with thread metadata, or None if file doesn't exist or is invalid
        
    Example:
        metadata = load_thread_metadata(Path("output/threads/thread_12345_Title"))
        if metadata:
            print(f"Thread: {metadata['title']}")
    """
    metadata_file = thread_dir / "metadata.json"
    
    if not metadata_file.exists():
        return None
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Warning: Could not load {metadata_file}: {e}")
        return None


def parse_iso_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse an ISO 8601 date string to a datetime object.
    
    Args:
        date_str: ISO 8601 formatted date string (e.g., "2024-01-15T10:30:00Z")
        
    Returns:
        datetime object, or None if date_str is None or invalid
        
    Example:
        dt = parse_iso_date("2024-01-15T10:30:00Z")
        # Returns: datetime(2024, 1, 15, 10, 30, 0)
    """
    if not date_str:
        return None
    
    try:
        # Handle various ISO 8601 formats
        # Try with timezone first
        if date_str.endswith('Z'):
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            return datetime.fromisoformat(date_str)
    except (ValueError, AttributeError) as e:
        print(f"⚠️  Warning: Could not parse date '{date_str}': {e}")
        return None


def get_sorted_threads_by_date(
    output_dir: Path, 
    reverse: bool = False
) -> List[Dict[str, Any]]:
    """
    Get all threads sorted chronologically by their start date (post_date).
    
    This function loads all thread metadata from the output directory and
    returns them sorted by the date the thread was started (original post date).
    
    Args:
        output_dir: Path to the threads output directory (e.g., "output/threads")
        reverse: If True, sort newest first; if False, sort oldest first (default)
        
    Returns:
        List of thread metadata dictionaries sorted by post_date
        Threads with no date are placed at the end
        
    Example:
        # Get threads sorted from oldest to newest
        threads = get_sorted_threads_by_date(Path("output/threads"))
        for thread in threads:
            print(f"{thread['post_date']}: {thread['title']}")
        
        # Get threads sorted from newest to oldest
        threads = get_sorted_threads_by_date(Path("output/threads"), reverse=True)
    """
    threads = []
    
    if not output_dir.exists():
        print(f"⚠️  Warning: Output directory {output_dir} does not exist")
        return threads
    
    # Load all thread metadata
    for thread_dir in output_dir.iterdir():
        if not thread_dir.is_dir():
            continue
        
        metadata = load_thread_metadata(thread_dir)
        if metadata:
            threads.append(metadata)
    
    # Sort by post_date
    # Threads with no date go to the end
    def sort_key(thread: Dict[str, Any]) -> tuple:
        """
        Sort key function for threads.
        Returns tuple (has_date, datetime) for proper sorting.
        Threads without dates are sorted to the end.
        """
        date_str = thread.get('post_date')
        parsed_date = parse_iso_date(date_str)
        
        if parsed_date:
            # Primary sort: by date
            # Secondary: threads with dates come first (0 < 1)
            return (0, parsed_date)
        else:
            # Threads without dates go to end
            # Use thread_id as secondary sort for consistency
            thread_id = thread.get('thread_id', '0')
            try:
                tid = int(thread_id)
            except (ValueError, TypeError):
                tid = 0
            return (1, datetime.min if not reverse else datetime.max, tid)
    
    threads.sort(key=sort_key, reverse=reverse)
    
    return threads
