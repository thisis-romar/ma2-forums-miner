"""
Resilient HTML parsing with CSS selector fallback chains.

This module provides robust parsing that can adapt to forum template changes
by trying multiple selector strategies.
"""

from typing import List, Optional, Callable, Any
from bs4 import BeautifulSoup, Tag


class SelectorChain:
    """
    CSS selector fallback chain for resilient parsing.
    
    Tries multiple selectors in order until one succeeds. This makes the
    scraper more resilient to HTML template changes.
    """
    
    def __init__(self, selectors: List[str], name: str = "unnamed"):
        """
        Initialize selector chain.
        
        Args:
            selectors: List of CSS selectors to try in order
            name: Descriptive name for this selector chain (for logging)
        """
        self.selectors = selectors
        self.name = name
        self.last_successful_index = 0  # Optimization: start with last successful
    
    def select_one(self, soup: BeautifulSoup) -> Optional[Tag]:
        """
        Find first matching element using selector fallback chain.
        
        Tries selectors in order until one finds a match.
        
        Args:
            soup: BeautifulSoup object to search
            
        Returns:
            First matching element or None if no selector matched
        """
        # Try last successful selector first (optimization)
        if self.last_successful_index < len(self.selectors):
            result = soup.select_one(self.selectors[self.last_successful_index])
            if result:
                return result
        
        # Try all selectors in order
        for i, selector in enumerate(self.selectors):
            if i == self.last_successful_index:
                continue  # Already tried above
            
            result = soup.select_one(selector)
            if result:
                self.last_successful_index = i
                if i > 0:
                    print(f"⚠️  {self.name}: Using fallback selector #{i+1}: {selector}")
                return result
        
        print(f"❌ {self.name}: All selectors failed")
        return None
    
    def select(self, soup: BeautifulSoup) -> List[Tag]:
        """
        Find all matching elements using selector fallback chain.
        
        Returns results from the first selector that finds any matches.
        
        Args:
            soup: BeautifulSoup object to search
            
        Returns:
            List of matching elements (empty if no selector matched)
        """
        # Try last successful selector first
        if self.last_successful_index < len(self.selectors):
            results = soup.select(self.selectors[self.last_successful_index])
            if results:
                return results
        
        # Try all selectors in order
        for i, selector in enumerate(self.selectors):
            if i == self.last_successful_index:
                continue
            
            results = soup.select(selector)
            if results:
                self.last_successful_index = i
                if i > 0:
                    print(f"⚠️  {self.name}: Using fallback selector #{i+1}: {selector}")
                return results
        
        print(f"❌ {self.name}: All selectors failed")
        return []


class ResilientParser:
    """
    Collection of resilient parsing strategies for forum HTML.
    
    Each parsing operation has multiple fallback selectors to handle
    template changes gracefully.
    """
    
    # Selector chains for different forum elements
    THREAD_TITLE = SelectorChain([
        'h1.topic-title',
        '.contentTitle',
        'h1[itemprop="headline"]',
        '.topicHeader h1',
        'article.message:first-child h2',
    ], name="thread_title")
    
    POST_ELEMENTS = SelectorChain([
        'article.message',
        '.message',
        '[data-role="message"]',
        '.post',
        '.forumPost',
    ], name="post_elements")
    
    POST_AUTHOR = SelectorChain([
        '.username',
        '.author',
        '[itemprop="author"]',
        '.postAuthor',
        '.userInfo h3',
    ], name="post_author")
    
    POST_DATE = SelectorChain([
        'time[datetime]',
        '.datetime',
        '[data-timestamp]',
        '.postDate',
    ], name="post_date")
    
    POST_CONTENT = SelectorChain([
        '.messageContent',
        '.messageText',
        '[itemprop="text"]',
        '.postContent',
        '.postBody',
    ], name="post_content")
    
    THREAD_STATS = SelectorChain([
        '.stats',
        '.threadStats',
        '[data-stats]',
        '.topicStats',
    ], name="thread_stats")
    
    PAGINATION = SelectorChain([
        '.pageNavigation',
        '.pagination',
        '[role="navigation"]',
        '.pageNav',
    ], name="pagination")
    
    THREAD_LINKS = SelectorChain([
        'a.wbbTopicLink',
        'a[href*="/forum/thread/"]',
        '.topicLink',
        'a[data-topic-id]',
    ], name="thread_links")
    
    ATTACHMENTS = SelectorChain([
        '.attachmentList a[href*="/attachment/"]',
        'a.attachment[href*="/attachment/"]',
        '[data-attachment] a',
        'a[href*="/attachment/"]',
    ], name="attachments")
    
    @staticmethod
    def extract_thread_title(soup: BeautifulSoup) -> str:
        """
        Extract thread title with fallback.
        
        Args:
            soup: BeautifulSoup of thread page
            
        Returns:
            Thread title or "Unknown Title" if not found
        """
        elem = ResilientParser.THREAD_TITLE.select_one(soup)
        return elem.text.strip() if elem else "Unknown Title"
    
    @staticmethod
    def extract_posts(soup: BeautifulSoup) -> List[Tag]:
        """
        Extract post elements with fallback.
        
        Args:
            soup: BeautifulSoup of thread page
            
        Returns:
            List of post elements
        """
        return ResilientParser.POST_ELEMENTS.select(soup)
    
    @staticmethod
    def extract_post_author(post_elem: Tag) -> str:
        """
        Extract author from post element with fallback.
        
        Args:
            post_elem: BeautifulSoup Tag of a post
            
        Returns:
            Author username or "Unknown"
        """
        # Create temporary soup from the post element for selector chain
        temp_soup = BeautifulSoup(str(post_elem), 'lxml')
        elem = ResilientParser.POST_AUTHOR.select_one(temp_soup)
        return elem.text.strip() if elem else "Unknown"
    
    @staticmethod
    def extract_post_date(post_elem: Tag) -> Optional[str]:
        """
        Extract post date from post element with fallback.
        
        Args:
            post_elem: BeautifulSoup Tag of a post
            
        Returns:
            ISO 8601 date string or None
        """
        temp_soup = BeautifulSoup(str(post_elem), 'lxml')
        elem = ResilientParser.POST_DATE.select_one(temp_soup)
        
        if elem:
            # Try to get datetime attribute first
            if elem.get('datetime'):
                return elem['datetime']
            # Fall back to data-timestamp
            if elem.get('data-timestamp'):
                return elem['data-timestamp']
            # Last resort: parse text content
            return elem.text.strip() if elem.text else None
        
        return None
    
    @staticmethod
    def extract_post_content(post_elem: Tag) -> str:
        """
        Extract post content text with fallback.
        
        Args:
            post_elem: BeautifulSoup Tag of a post
            
        Returns:
            Post text content or empty string
        """
        temp_soup = BeautifulSoup(str(post_elem), 'lxml')
        elem = ResilientParser.POST_CONTENT.select_one(temp_soup)
        return elem.get_text(strip=True) if elem else ""
    
    @staticmethod
    def extract_thread_links(soup: BeautifulSoup) -> List[Tag]:
        """
        Extract thread links from board page with fallback.
        
        Args:
            soup: BeautifulSoup of board/list page
            
        Returns:
            List of thread link elements
        """
        return ResilientParser.THREAD_LINKS.select(soup)
    
    @staticmethod
    def extract_attachments(soup: BeautifulSoup) -> List[Tag]:
        """
        Extract attachment links with fallback.
        
        Args:
            soup: BeautifulSoup of thread page
            
        Returns:
            List of attachment link elements
        """
        return ResilientParser.ATTACHMENTS.select(soup)
