"""
Utility functions for the MA2 Forums Miner.

This module provides helper functions for file operations and path management.
"""

import hashlib
import re
import mimetypes
from pathlib import Path
from typing import Union


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


def sha256_string(text: str) -> str:
    """
    Calculate the SHA256 hash of a string.
    
    Used for content fingerprinting to detect changes in post text.
    
    Args:
        text: String to hash
        
    Returns:
        SHA256 hash in format "sha256:hexdigest"
        
    Example:
        hash_val = sha256_string("Hello, world!")
        # Returns: "sha256:315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
    """
    sha256_hash = hashlib.sha256()
    sha256_hash.update(text.encode('utf-8'))
    return f"sha256:{sha256_hash.hexdigest()}"


def infer_mime_type(filename: str, content_type: str = None) -> str:
    """
    Infer MIME type from filename extension or Content-Type header.
    
    Prefers Content-Type header if provided, falls back to extension-based
    inference using Python's mimetypes module.
    
    Args:
        filename: Name of the file
        content_type: Content-Type header value (if available)
        
    Returns:
        MIME type string (e.g., "application/xml", "application/zip")
        Returns "application/octet-stream" if type cannot be determined
        
    Example:
        mime = infer_mime_type("macro.xml", "application/xml")
        # Returns: "application/xml"
        
        mime = infer_mime_type("script.xml")
        # Returns: "application/xml" (inferred from extension)
        
        mime = infer_mime_type("unknown.dat")
        # Returns: "application/octet-stream" (unknown type)
    """
    # Prefer explicit Content-Type header
    if content_type:
        # Extract just the MIME type, ignore parameters like charset
        mime = content_type.split(';')[0].strip()
        if mime:
            return mime
    
    # Fall back to extension-based inference
    guessed_type, _ = mimetypes.guess_type(filename)
    if guessed_type:
        return guessed_type
    
    # Default to generic binary type
    return "application/octet-stream"
