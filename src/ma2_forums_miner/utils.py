"""
Utility functions for the MA2 Forums Miner.

This module provides helper functions for file operations and path management.
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Union


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


def date_folder(post_date: Optional[str]) -> Tuple[str, str]:
    """Parse an ISO 8601 date string into year and date folder components.

    Args:
        post_date: ISO 8601 formatted date string (e.g. "2024-01-15T10:30:00Z")
                   or None / empty string.

    Returns:
        Tuple of (year, date) strings, e.g. ("2024", "2024-01-15").
        Returns ("unknown_year", "unknown_date") when the date cannot be parsed.
    """
    if not post_date:
        return ("unknown_year", "unknown_date")
    try:
        # Handle various ISO 8601 formats
        cleaned = post_date.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return (str(dt.year), dt.strftime("%Y-%m-%d"))
    except (ValueError, TypeError):
        # Try bare date (YYYY-MM-DD)
        match = re.match(r"(\d{4})-(\d{2})-(\d{2})", post_date)
        if match:
            return (match.group(1), match.group(0))
        return ("unknown_year", "unknown_date")


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
