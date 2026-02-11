"""
MA2 Forums Miner - Scraper Package

This package provides async web scraping functionality for the
MA Lighting grandMA2 Macro Share forum.

Main components:
- ForumScraper: Main scraper class with async/concurrency control
- ThreadMetadata: Data model for thread information
- Asset: Data model for downloadable attachments
- Utility functions for file operations

Usage:
    from ma2_forums_miner.scraper import ForumScraper
    import asyncio
    
    scraper = ForumScraper()
    asyncio.run(scraper.run())
"""

from .models import Asset, Post, ThreadMetadata
from .scraper import ForumScraper
from .utils import sha256_file, safe_thread_folder, date_folder, extract_date_from_post_text

__all__ = [
    'ForumScraper',
    'ThreadMetadata',
    'Post',
    'Asset',
    'sha256_file',
    'safe_thread_folder',
    'date_folder',
    'extract_date_from_post_text',
]

__version__ = '1.0.0'
