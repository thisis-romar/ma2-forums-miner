"""Async forum scraper module for MA Lighting grandMA2 Macro Share forum."""

import asyncio
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse, parse_qs

import aiohttp
from bs4 import BeautifulSoup


class ForumScraper:
    """Async scraper for MA Lighting grandMA2 Macro Share forum."""
    
    BASE_URL = "https://forum.malighting.com"
    BOARD_URL = f"{BASE_URL}/forum/board/35-grandma2-macro-share/"
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """Initialize the scraper.
        
        Args:
            session: Optional aiohttp session. If None, creates a new one.
        """
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
            
    async def get_page(self, url: str) -> str:
        """Fetch a page and return its HTML content.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string
        """
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            raise Exception(f"Failed to fetch {url}: {e}") from e
            
    async def get_thread_list_page(self, page: int = 1) -> BeautifulSoup:
        """Get a thread list page.
        
        Args:
            page: Page number (1-indexed)
            
        Returns:
            BeautifulSoup object of the page
        """
        url = self.BOARD_URL
        if page > 1:
            url = f"{url}page/{page}/"
        html = await self.get_page(url)
        return BeautifulSoup(html, "lxml")
        
    def extract_threads_from_page(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract thread information from a thread list page.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            List of thread dictionaries with metadata
        """
        threads = []
        
        # Find all thread rows
        thread_rows = soup.select('li[data-thread-id]')
        
        for row in thread_rows:
            thread_id = row.get('data-thread-id')
            
            # Extract thread title and URL
            title_elem = row.select_one('a.wbbTopicLink')
            if not title_elem:
                continue
                
            title = title_elem.text.strip()
            thread_url = urljoin(self.BASE_URL, title_elem['href'])
            
            # Extract author
            author_elem = row.select_one('.username')
            author = author_elem.text.strip() if author_elem else "Unknown"
            
            # Extract date
            time_elem = row.select_one('time')
            date = time_elem['datetime'] if time_elem and time_elem.get('datetime') else None
            
            # Extract reply count
            stats_elem = row.select_one('.statsReplies')
            replies = 0
            if stats_elem:
                replies_text = stats_elem.text.strip()
                replies_match = re.search(r'\d+', replies_text)
                if replies_match:
                    replies = int(replies_match.group())
            
            # Extract view count
            views_elem = row.select_one('.statsViews')
            views = 0
            if views_elem:
                views_text = views_elem.text.strip()
                views_match = re.search(r'\d+', views_text)
                if views_match:
                    views = int(views_match.group())
            
            threads.append({
                'thread_id': thread_id,
                'title': title,
                'url': thread_url,
                'author': author,
                'date': date,
                'replies': replies,
                'views': views,
            })
            
        return threads
        
    def get_max_page_number(self, soup: BeautifulSoup) -> int:
        """Extract the maximum page number from pagination.
        
        Args:
            soup: BeautifulSoup object of a thread list page
            
        Returns:
            Maximum page number (1 if no pagination found)
        """
        pagination = soup.select('.pageNavigation a')
        max_page = 1
        
        for link in pagination:
            href = link.get('href', '')
            match = re.search(r'/page/(\d+)/', href)
            if match:
                page_num = int(match.group(1))
                max_page = max(max_page, page_num)
                
        return max_page
        
    async def get_all_threads(self) -> List[Dict]:
        """Get all threads from all pages.
        
        Returns:
            List of all thread dictionaries
        """
        # Get first page to determine total pages
        first_page = await self.get_thread_list_page(1)
        max_page = self.get_max_page_number(first_page)
        
        # Extract threads from first page
        all_threads = self.extract_threads_from_page(first_page)
        
        # Get remaining pages concurrently
        if max_page > 1:
            tasks = [
                self.get_thread_list_page(page)
                for page in range(2, max_page + 1)
            ]
            
            pages = await asyncio.gather(*tasks)
            
            for page in pages:
                threads = self.extract_threads_from_page(page)
                all_threads.extend(threads)
                
        return all_threads
        
    async def get_thread_details(self, thread_url: str) -> Dict:
        """Get detailed information about a specific thread.
        
        Args:
            thread_url: URL of the thread
            
        Returns:
            Dictionary with thread details including posts and attachments
        """
        html = await self.get_page(thread_url)
        soup = BeautifulSoup(html, "lxml")
        
        posts = []
        attachments = []
        
        # Extract posts
        post_elements = soup.select('article.message')
        
        for post_elem in post_elements:
            post_id = post_elem.get('data-post-id')
            
            # Extract author
            author_elem = post_elem.select_one('.username')
            author = author_elem.text.strip() if author_elem else "Unknown"
            
            # Extract date
            time_elem = post_elem.select_one('time')
            date = time_elem['datetime'] if time_elem and time_elem.get('datetime') else None
            
            # Extract content
            content_elem = post_elem.select_one('.messageContent')
            content = content_elem.text.strip() if content_elem else ""
            
            posts.append({
                'post_id': post_id,
                'author': author,
                'date': date,
                'content': content,
            })
            
            # Extract attachments from this post
            attachment_links = post_elem.select('a.attachment')
            for link in attachment_links:
                href = link.get('href')
                if href:
                    attachment_url = urljoin(self.BASE_URL, href)
                    filename = link.text.strip()
                    
                    # Check if it's a desired file type
                    if any(filename.lower().endswith(ext) for ext in ['.xml', '.zip', '.gz', '.show']):
                        attachments.append({
                            'url': attachment_url,
                            'filename': filename,
                            'post_id': post_id,
                        })
        
        return {
            'posts': posts,
            'attachments': attachments,
        }
