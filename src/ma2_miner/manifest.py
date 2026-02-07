"""Manifest module for tracking scraped threads and enabling delta scraping."""

import json
from pathlib import Path
from typing import Dict, Set, Optional
from datetime import datetime


class Manifest:
    """Manifest for tracking scraped threads."""
    
    def __init__(self, manifest_path: str = "manifest.json"):
        """Initialize the manifest.
        
        Args:
            manifest_path: Path to the manifest file
        """
        self.manifest_path = Path(manifest_path)
        self.data: Dict[str, Dict] = {}
        self.load()
        
    def load(self):
        """Load manifest from file."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load manifest: {e}")
                self.data = {}
        else:
            self.data = {}
            
    def save(self):
        """Save manifest to file."""
        try:
            # Create parent directory if needed
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.manifest_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving manifest: {e}")
            
    def is_thread_scraped(self, thread_id: str) -> bool:
        """Check if a thread has been scraped.
        
        Args:
            thread_id: Thread ID to check
            
        Returns:
            True if thread has been scraped, False otherwise
        """
        return thread_id in self.data
        
    def mark_thread_scraped(
        self,
        thread_id: str,
        thread_data: Dict,
        output_dir: str,
        attachment_count: int = 0
    ):
        """Mark a thread as scraped.
        
        Args:
            thread_id: Thread ID
            thread_data: Thread metadata
            output_dir: Directory where thread was saved
            attachment_count: Number of attachments downloaded
        """
        self.data[thread_id] = {
            'scraped_at': datetime.now().isoformat(),
            'title': thread_data.get('title', ''),
            'url': thread_data.get('url', ''),
            'output_dir': output_dir,
            'attachment_count': attachment_count,
            'post_count': len(thread_data.get('posts', [])),
        }
        
    def get_scraped_thread_ids(self) -> Set[str]:
        """Get set of all scraped thread IDs.
        
        Returns:
            Set of thread IDs
        """
        return set(self.data.keys())
        
    def get_thread_info(self, thread_id: str) -> Optional[Dict]:
        """Get information about a scraped thread.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            Thread info dictionary or None if not found
        """
        return self.data.get(thread_id)
        
    def get_statistics(self) -> Dict:
        """Get statistics about scraped threads.
        
        Returns:
            Dictionary with statistics
        """
        if not self.data:
            return {
                'total_threads': 0,
                'total_attachments': 0,
                'total_posts': 0,
            }
            
        total_attachments = sum(t.get('attachment_count', 0) for t in self.data.values())
        total_posts = sum(t.get('post_count', 0) for t in self.data.values())
        
        return {
            'total_threads': len(self.data),
            'total_attachments': total_attachments,
            'total_posts': total_posts,
        }
