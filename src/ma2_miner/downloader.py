"""Async downloader module for thread attachments."""

import asyncio
import os
from pathlib import Path
from typing import List, Dict, Optional

import aiohttp
import aiofiles


class Downloader:
    """Async downloader for thread attachments."""
    
    def __init__(self, output_dir: str = "output", session: Optional[aiohttp.ClientSession] = None):
        """Initialize the downloader.
        
        Args:
            output_dir: Base directory for downloads
            session: Optional aiohttp session. If None, creates a new one.
        """
        self.output_dir = Path(output_dir)
        self.session = session
        self._own_session = session is None
        
    async def __aenter__(self):
        """Async context manager entry."""
        if self._own_session:
            self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._own_session and self.session:
            await self.session.close()
            
    async def download_file(self, url: str, output_path: Path) -> bool:
        """Download a file from URL to output path.
        
        Args:
            url: URL to download from
            output_path: Path to save the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create parent directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with self.session.get(url) as response:
                response.raise_for_status()
                
                # Write file in chunks
                async with aiofiles.open(output_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                        
            return True
            
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return False
            
    async def download_attachments(
        self,
        attachments: List[Dict],
        thread_dir: Path
    ) -> List[str]:
        """Download all attachments for a thread.
        
        Args:
            attachments: List of attachment dictionaries
            thread_dir: Directory to save attachments
            
        Returns:
            List of successfully downloaded file paths
        """
        downloaded = []
        
        # Create attachments subdirectory
        attachments_dir = thread_dir / "attachments"
        attachments_dir.mkdir(parents=True, exist_ok=True)
        
        # Download each attachment
        tasks = []
        for attachment in attachments:
            filename = attachment['filename']
            url = attachment['url']
            output_path = attachments_dir / filename
            
            # Avoid duplicate filenames
            counter = 1
            while output_path.exists():
                name_parts = filename.rsplit('.', 1)
                if len(name_parts) == 2:
                    filename = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                else:
                    filename = f"{filename}_{counter}"
                output_path = attachments_dir / filename
                counter += 1
                
            tasks.append(self._download_with_path(url, output_path))
            
        results = await asyncio.gather(*tasks)
        
        for attachment, (success, path) in zip(attachments, results):
            if success:
                downloaded.append(str(path))
                
        return downloaded
        
    async def _download_with_path(self, url: str, path: Path) -> tuple:
        """Helper to download and return path.
        
        Args:
            url: URL to download
            path: Output path
            
        Returns:
            Tuple of (success: bool, path: Path)
        """
        success = await self.download_file(url, path)
        return (success, path)
