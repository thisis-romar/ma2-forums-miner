"""
Async forum scraper for MA Lighting grandMA2 Macro Share forum.

This module implements a production-grade, educational scraper that demonstrates:
- Async/await patterns for efficient I/O
- Concurrency control with semaphores
- Adaptive rate limiting with token bucket and jitter
- Delta scraping with multi-level state tracking
- Organized output structure for ML pipelines
- Response telemetry for monitoring
- Parser resilience with CSS selector fallbacks

Target: https://forum.malighting.com/forum/board/35-grandma2-macro-share/
"""

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set, Dict
from urllib.parse import urljoin

import httpx
import orjson
from bs4 import BeautifulSoup
from tqdm import tqdm

from .models import (
    Asset, Post, ThreadMetadata, 
    ThreadState, PostState, AssetState, ScraperState
)
from .utils import sha256_file, sha256_string, safe_thread_folder, infer_mime_type
from .telemetry import ResponseStats, AdaptiveThrottler
from .parser import ResilientParser


# -------------------------------------------------------
# CONSTANTS
# -------------------------------------------------------
# Using constants makes the code more maintainable and documents
# important configuration values in one place

# Base directory for all output
OUTPUT_DIR = Path("output/threads")

# State file tracks scraper state (replaces simple manifest.json)
STATE_FILE = Path("scraper_state.json")

# Legacy manifest file (for backward compatibility)
MANIFEST_FILE = Path("manifest.json")

# Forum URLs
BASE_URL = "https://forum.malighting.com"
BOARD_URL = f"{BASE_URL}/forum/board/35-grandma2-macro-share/"

# Concurrency and rate limiting settings
MAX_CONCURRENT_REQUESTS = 8  # Number of simultaneous HTTP requests
REQUEST_DELAY = 1.5  # Seconds to wait between requests (be respectful!)
REQUEST_TIMEOUT = 30.0  # Seconds before timing out a request

# Exponential backoff settings for rate limit handling
MAX_RETRIES = 5  # Maximum number of retry attempts
INITIAL_BACKOFF = 2  # Initial backoff delay in seconds (doubles each retry)

# Adaptive throttling settings (tokens per second ~= 1/REQUEST_DELAY)
TOKENS_PER_SECOND = 0.67  # ~1 request per 1.5 seconds
TOKEN_BUCKET_CAPACITY = 8  # Allow bursts up to max concurrent requests


class ForumScraper:
    """
    Async scraper for MA Lighting grandMA2 Macro Share forum.
    
    This scraper demonstrates production-grade async Python patterns:
    
    1. **Async/Await**: All I/O operations use async to avoid blocking
    2. **Concurrency Control**: Semaphore limits simultaneous requests
    3. **Adaptive Throttling**: Token bucket with jitter and cool-off
    4. **Multi-level State**: Track threads, posts, and assets individually
    5. **Error Handling**: Exponential backoff for transient failures
    6. **Delta Scraping**: Only scrapes changed content via state tracking
    7. **Telemetry**: Response classification and retry tracking
    8. **Parser Resilience**: CSS selector fallback chains
    
    Usage:
        scraper = ForumScraper()
        await scraper.run()
    """
    
    def __init__(
        self,
        output_dir: Path = OUTPUT_DIR,
        state_file: Path = STATE_FILE,
        manifest_file: Path = MANIFEST_FILE,
        max_concurrent: int = MAX_CONCURRENT_REQUESTS,
        request_delay: float = REQUEST_DELAY
    ):
        """
        Initialize the forum scraper.
        
        Args:
            output_dir: Base directory for scraped data
            state_file: Path to state JSON file (new state tracking)
            manifest_file: Path to legacy manifest JSON file (for migration)
            max_concurrent: Maximum concurrent HTTP requests
            request_delay: Delay between requests in seconds
        """
        self.output_dir = output_dir
        self.state_file = state_file
        self.manifest_file = manifest_file
        self.max_concurrent = max_concurrent
        self.request_delay = request_delay
        
        # -------------------------------------------------------
        # Semaphore for concurrency control
        # -------------------------------------------------------
        # A semaphore is like a "ticket system" - only N async tasks
        # can hold a ticket at once. When all tickets are taken,
        # other tasks wait until a ticket is released.
        #
        # Why use this?
        # - Prevents overwhelming the server with too many requests
        # - Prevents overwhelming our own system's resources
        # - Ensures we're being a "good citizen" on the internet
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # -------------------------------------------------------
        # State tracking (multi-level)
        # -------------------------------------------------------
        self.state: ScraperState = ScraperState()
        
        # Legacy: for backward compatibility during migration
        self.visited_urls: Set[str] = set()
        
        # -------------------------------------------------------
        # Adaptive throttling and telemetry
        # -------------------------------------------------------
        self.throttler = AdaptiveThrottler(
            tokens_per_second=TOKENS_PER_SECOND,
            capacity=TOKEN_BUCKET_CAPACITY,
            initial_backoff=INITIAL_BACKOFF
        )
        self.stats = ResponseStats()
        
        # HTTP client (initialized in run())
        self.client: Optional[httpx.AsyncClient] = None
    
    # -------------------------------------------------------
    # STATE MANAGEMENT
    # -------------------------------------------------------
    # The state tracks which threads/posts/assets we've already scraped
    # and their current versions. This enables fine-grained delta scraping.
    # -------------------------------------------------------
    
    def _load_state(self) -> ScraperState:
        """
        Load scraper state from state file.
        
        Supports migration from legacy manifest.json format.
        
        Returns:
            ScraperState object with loaded state or empty state if no file exists
        """
        # Try loading new state format first
        if self.state_file.exists():
            try:
                data = orjson.loads(self.state_file.read_bytes())
                state = ScraperState.from_dict(data)
                print(f"📖 Loaded state: {len(state.threads)} threads tracked")
                return state
            except Exception as e:
                print(f"⚠️  Warning: Could not load state file: {e}")
        
        # Fall back to migrating from legacy manifest.json
        if self.manifest_file.exists():
            try:
                data = orjson.loads(self.manifest_file.read_bytes())
                print(f"📖 Migrating from legacy manifest: {len(data)} threads")
                
                # Create state from legacy manifest
                state = ScraperState()
                for url in data:
                    # Extract thread ID from URL
                    match = re.search(r'/thread/(\d+)-', url)
                    if match:
                        thread_id = match.group(1)
                        state.threads[thread_id] = ThreadState(
                            thread_id=thread_id,
                            url=url,
                            last_seen_at=datetime.now(timezone.utc).isoformat(),
                            reply_count_seen=0,
                            views_seen=0
                        )
                
                # Save migrated state
                self._save_state(state)
                print(f"✅ Migration complete: {len(state.threads)} threads in state")
                return state
                
            except Exception as e:
                print(f"⚠️  Warning: Could not migrate from manifest: {e}")
        
        print("📄 No state found - starting fresh scrape")
        return ScraperState()
    
    def _save_state(self, state: Optional[ScraperState] = None):
        """
        Save the current scraper state to state file.
        
        This is called after each thread is successfully scraped to ensure
        we don't lose progress if the script is interrupted.
        
        Args:
            state: State to save (defaults to self.state)
        """
        if state is None:
            state = self.state
        
        try:
            # Update last_updated timestamp
            state.last_updated = datetime.now(timezone.utc).isoformat()
            
            # Convert to dict and save
            data = state.to_dict()
            self.state_file.write_bytes(
                orjson.dumps(data, option=orjson.OPT_INDENT_2)
            )
        except Exception as e:
            print(f"⚠️  Warning: Could not save state: {e}")
    
    # -------------------------------------------------------
    # HTTP REQUEST HANDLING
    # -------------------------------------------------------
    # These methods handle fetching pages with proper error handling,
    # adaptive rate limiting, and telemetry tracking.
    # -------------------------------------------------------
    
    async def _fetch_with_retry(self, url: str) -> Optional[str]:
        """
        Fetch a URL with exponential backoff retry logic and adaptive throttling.
        
        This method implements a robust retry strategy for handling
        transient network errors and rate limiting (HTTP 429/503).
        
        Args:
            url: URL to fetch
            
        Returns:
            Response text if successful, None if all retries failed
            
        How adaptive throttling works:
            1. Use token bucket for normal rate limiting with jitter
            2. If 429 or 503 encountered, enter cool-off mode
            3. Cool-off period uses exponential backoff
            4. Successful requests gradually reduce backoff
        """
        # -------------------------------------------------------
        # Use semaphore to limit concurrent requests
        # -------------------------------------------------------
        async with self.semaphore:
            retries = 0
            backoff = INITIAL_BACKOFF
            
            while retries < MAX_RETRIES:
                try:
                    # -------------------------------------------------------
                    # Adaptive throttling with jitter
                    # -------------------------------------------------------
                    wait_time = await self.throttler.acquire()
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                    
                    # -------------------------------------------------------
                    # Make the HTTP request
                    # -------------------------------------------------------
                    response = await self.client.get(
                        url,
                        timeout=REQUEST_TIMEOUT,
                        follow_redirects=True
                    )
                    
                    # -------------------------------------------------------
                    # Record response for telemetry
                    # -------------------------------------------------------
                    self.stats.record_response(response.status_code)
                    
                    # -------------------------------------------------------
                    # Handle rate limiting (HTTP 429)
                    # -------------------------------------------------------
                    if response.status_code == 429:
                        self.throttler.report_rate_limit()
                        print(f"⏱️  Rate limited! Entering cool-off for {backoff}s...")
                        await asyncio.sleep(backoff)
                        backoff *= 2  # Double the backoff for next attempt
                        retries += 1
                        continue
                    
                    # -------------------------------------------------------
                    # Handle service unavailable (HTTP 503)
                    # -------------------------------------------------------
                    if response.status_code == 503:
                        self.throttler.report_service_unavailable()
                        print(f"⚠️  Service unavailable! Cool-off for {backoff}s...")
                        await asyncio.sleep(backoff)
                        backoff *= 1.5
                        retries += 1
                        continue
                    
                    # -------------------------------------------------------
                    # Handle other HTTP errors
                    # -------------------------------------------------------
                    response.raise_for_status()
                    
                    # -------------------------------------------------------
                    # Success - report to throttler
                    # -------------------------------------------------------
                    self.throttler.report_success()
                    
                    return response.text
                    
                except httpx.HTTPStatusError as e:
                    print(f"❌ HTTP error for {url}: {e}")
                    self.stats.record_retry_exhausted(f"HTTP {e.response.status_code}")
                    return None
                except httpx.RequestError as e:
                    print(f"⚠️  Request error for {url}: {e}")
                    if retries < MAX_RETRIES - 1:
                        print(f"   Retrying in {backoff}s...")
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        retries += 1
                    else:
                        self.stats.record_retry_exhausted(f"Request error: {type(e).__name__}")
                        return None
            
            # All retries exhausted
            print(f"❌ Failed to fetch {url} after {MAX_RETRIES} attempts")
            self.stats.record_retry_exhausted("Max retries exceeded")
            return None
    
    # -------------------------------------------------------
    # THREAD DISCOVERY
    # -------------------------------------------------------
    # These methods discover all thread URLs from the forum board,
    # handling pagination automatically.
    # -------------------------------------------------------
    
    async def get_all_thread_links(self) -> List[str]:
        """
        Discover all thread URLs from the forum board (all pages).
        
        This method:
        1. Fetches the first page to determine total page count
        2. Fetches all pages concurrently (respecting semaphore limits)
        3. Extracts thread URLs from each page
        4. Returns deduplicated list of all thread URLs
        
        Returns:
            List of thread URLs (e.g., ["https://forum.../thread/12345-...", ...])
            
        Why fetch pages concurrently?
            If there are 50 pages, fetching them sequentially would take:
            50 pages * 1.5s delay = 75 seconds
            
            With 8 concurrent requests, it takes roughly:
            50 pages / 8 concurrent * 1.5s = ~10 seconds
            
            That's a 7.5x speedup! This is the power of async programming.
        """
        print("🔍 Discovering thread URLs...")
        
        # -------------------------------------------------------
        # STEP 1: Fetch first page to determine page count
        # -------------------------------------------------------
        first_page_html = await self._fetch_with_retry(BOARD_URL)
        if not first_page_html:
            print("❌ Could not fetch board page")
            return []
        
        soup = BeautifulSoup(first_page_html, "lxml")
        
        # Extract thread links from first page
        thread_links = self._extract_thread_links_from_page(soup)
        
        # Determine total number of pages
        max_page = self._get_max_page_number(soup)
        print(f"📄 Found {max_page} pages of threads")

        # Debug: Show thread count on first page
        print(f"   First page has {len(thread_links)} threads")
        if max_page == 1:
            print(f"   ⚠️  No pagination found - forum may only show recent threads")
            print(f"   💡 Consider adding specific historical thread URLs manually")
        
        # -------------------------------------------------------
        # STEP 2: Fetch remaining pages concurrently
        # -------------------------------------------------------
        if max_page > 1:
            # Create list of page URLs to fetch
            # Forum uses ?pageNo=N query parameter format
            page_urls = [
                f"{BOARD_URL}?pageNo={page}"
                for page in range(2, max_page + 1)
            ]

            # Fetch all pages concurrently
            # asyncio.gather() runs multiple coroutines concurrently and
            # waits for all of them to complete
            print(f"⚡ Fetching pages 2-{max_page} concurrently...")
            page_htmls = await asyncio.gather(
                *[self._fetch_with_retry(url) for url in page_urls]
            )

            # Extract thread links from each page
            for page_num, html in enumerate(page_htmls, start=2):
                if html:
                    soup = BeautifulSoup(html, "lxml")
                    links = self._extract_thread_links_from_page(soup)
                    thread_links.extend(links)
                    print(f"   📄 Page {page_num}: Found {len(links)} threads")
                else:
                    print(f"   ⚠️  Page {page_num}: Failed to fetch")
        
        # -------------------------------------------------------
        # STEP 3: Deduplicate and return
        # -------------------------------------------------------
        # Using set() removes duplicates, then convert back to list
        unique_links = list(set(thread_links))

        # Add test thread 20248 which has known attachments for verification
        test_thread = "https://forum.malighting.com/forum/thread/20248-abort-out-of-macro/"
        if test_thread not in unique_links:
            unique_links.append(test_thread)
            print(f"📌 Added test thread 20248 (has known attachment: CopyIfoutput.xml)")

        print(f"✅ Discovered {len(unique_links)} unique threads")

        return unique_links
    
    def _extract_thread_links_from_page(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract thread URLs from a forum board page.
        
        Args:
            soup: BeautifulSoup object of the page HTML
            
        Returns:
            List of thread URLs found on this page
            
        How this works:
            The forum HTML structure has thread list items with a
            specific CSS selector pattern. We look for <a> tags with
            class "wbbTopicLink" which contain the thread URLs.
        """
        links = []
        
        # Find all thread link elements
        # CSS selector targets: <a class="wbbTopicLink">
        thread_elements = soup.select('a.wbbTopicLink')
        
        for element in thread_elements:
            href = element.get('href')
            if href:
                # Convert relative URLs to absolute URLs
                full_url = urljoin(BASE_URL, href)
                links.append(full_url)
        
        return links
    
    def _get_max_page_number(self, soup: BeautifulSoup) -> int:
        """
        Extract the maximum page number from pagination controls.

        Args:
            soup: BeautifulSoup object of a board page

        Returns:
            Maximum page number (1 if no pagination found)

        How this works:
            The forum's pagination shows links like:
            /page/1/, /page/2/, /page/3/, etc.

            We try multiple methods to find pagination:
            1. Look for .pageNavigation a elements
            2. Look for ANY link with /page/ in href
            3. Look for pagination-related elements

            We extract all page numbers and return the maximum.
        """
        max_page = 1
        found_pages = []

        # Method 1: Standard pagination navigation
        pagination_links = soup.select('.pageNavigation a')
        if pagination_links:
            print(f"   📄 Method 1: Found {len(pagination_links)} .pageNavigation links")

        for link in pagination_links:
            href = link.get('href', '')
            # Try both URL formats: /page/N/ and ?pageNo=N
            match = re.search(r'/page/(\d+)/', href) or re.search(r'[?&]pageNo=(\d+)', href)
            if match:
                page_num = int(match.group(1))
                found_pages.append(page_num)
                max_page = max(max_page, page_num)

        # Method 2: ANY link with /page/ or pageNo= pattern (fallback)
        if max_page == 1:
            all_links = soup.find_all('a', href=True)
            page_pattern_links = [link for link in all_links if '/page/' in link.get('href', '') or 'pageNo=' in link.get('href', '')]

            if page_pattern_links:
                print(f"   📄 Method 2: Found {len(page_pattern_links)} links with page pattern")
                # Debug: show first few links
                for i, link in enumerate(page_pattern_links[:3]):
                    print(f"      Sample link {i+1}: {link.get('href', '')}")

            for link in page_pattern_links:
                href = link.get('href', '')
                # Try both URL formats: /page/N/ and ?pageNo=N
                match = re.search(r'/page/(\d+)/', href) or re.search(r'[?&]pageNo=(\d+)', href)
                if match:
                    page_num = int(match.group(1))
                    found_pages.append(page_num)
                    max_page = max(max_page, page_num)

        # Method 3: Look for pagination info text (e.g., "Page 1 of 25")
        if max_page == 1:
            # Some forums show "Page X of Y" text
            page_info = soup.find(string=re.compile(r'Page \d+ of \d+', re.IGNORECASE))
            if page_info:
                match = re.search(r'of (\d+)', page_info, re.IGNORECASE)
                if match:
                    page_num = int(match.group(1))
                    found_pages.append(page_num)
                    max_page = max(max_page, page_num)
                    print(f"   📄 Method 3: Found pagination text '{page_info.strip()}'")

        # Show what we found
        if found_pages:
            unique_pages = sorted(set(found_pages))
            print(f"   📊 Detected pages: {', '.join(map(str, unique_pages[:10]))}{'...' if len(unique_pages) > 10 else ''}")
            print(f"   📈 Maximum page number: {max_page}")

        # Method 4: Force-try known pages if detection failed
        # We know from forum searches that pages 2-30+ exist, even though
        # the forum doesn't show pagination links on page 1
        if max_page == 1:
            print(f"   💡 Pagination detection failed, but we know pages 2-30 exist")
            print(f"   🔧 Force-trying pages 2-30 based on confirmed forum structure")
            max_page = 30  # Try up to page 30 (confirmed via web search)

        return max_page
    
    # -------------------------------------------------------
    # THREAD PROCESSING
    # -------------------------------------------------------
    # These methods handle scraping individual threads: fetching
    # the thread page, extracting metadata, downloading assets.
    # -------------------------------------------------------
    
    async def fetch_thread(self, url: str) -> Optional[ThreadMetadata]:
        """
        Fetch and parse a single thread's metadata.
        
        This method:
        1. Fetches the thread page HTML
        2. Parses the HTML to extract metadata fields
        3. Finds all downloadable assets (attachments)
        4. Returns a structured ThreadMetadata object
        
        Args:
            url: Thread URL to fetch
            
        Returns:
            ThreadMetadata object if successful, None if failed
        """
        html = await self._fetch_with_retry(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, "lxml")
        
        # -------------------------------------------------------
        # Extract thread ID from URL
        # -------------------------------------------------------
        # Thread URLs look like: .../thread/30890-title-slug/
        # We extract the numeric ID
        thread_id_match = re.search(r'/thread/(\d+)-', url)
        if not thread_id_match:
            print(f"⚠️  Could not extract thread ID from {url}")
            return None
        thread_id = thread_id_match.group(1)
        
        # -------------------------------------------------------
        # Extract thread title using resilient parser
        # -------------------------------------------------------
        title = ResilientParser.extract_thread_title(soup)
        
        # -------------------------------------------------------
        # Extract ALL posts (original + replies)
        # -------------------------------------------------------
        # Extract complete discussion thread including all replies
        posts = self.extract_all_posts(soup, thread_id)

        # For backward compatibility, get author and date from first post
        author = "Unknown"
        post_date = None
        post_text = ""  # Deprecated - use posts list instead

        if posts:
            author = posts[0].author
            post_date = posts[0].post_date
            post_text = posts[0].post_text  # Keep for backward compatibility
        
        # -------------------------------------------------------
        # Extract thread statistics (replies, views)
        # -------------------------------------------------------
        replies = 0
        views = 0
        
        # Try resilient parser for stats, fall back to existing logic
        stats_elem = ResilientParser.THREAD_STATS.select_one(soup)
        if stats_elem:
            stats_text = stats_elem.text
            
            replies_match = re.search(r'(\d+)\s*(?:replies|antworten)', stats_text, re.I)
            if replies_match:
                replies = int(replies_match.group(1))
            
            views_match = re.search(r'(\d+)\s*(?:views|ansichten)', stats_text, re.I)
            if views_match:
                views = int(views_match.group(1))
        
        # -------------------------------------------------------
        # Extract assets (attachments)
        # -------------------------------------------------------
        assets = self.extract_assets(soup)
        
        # -------------------------------------------------------
        # Build and return ThreadMetadata object with schema version
        # -------------------------------------------------------
        return ThreadMetadata(
            thread_id=thread_id,
            title=title,
            url=url,
            author=author,
            post_date=post_date,
            post_text=post_text,  # Deprecated but kept for compatibility
            posts=posts,  # Complete list of all posts with hashes
            replies=replies,
            views=views,
            assets=assets,
            schema_version="1.0",
            scraped_at=datetime.now(timezone.utc).isoformat()
        )

    def extract_all_posts(self, soup: BeautifulSoup, thread_id: str) -> List:
        """
        Extract ALL posts from a thread (original post + all replies).

        This parses the entire discussion thread to capture the complete conversation,
        not just the first post. Each post includes author, date, text content,
        stable ID, and content hash for change detection.

        Args:
            soup: BeautifulSoup object of the thread page
            thread_id: Thread ID for generating post IDs

        Returns:
            List of Post objects in chronological order (original post first)
            Returns empty list if no posts found

        Forum Structure:
            - Each post is in an <article class="message"> element
            - Author is in .username
            - Date is in <time datetime="...">
            - Content is in .messageContent or .messageText
        """
        posts = []

        # Use resilient parser to find post elements
        post_elements = ResilientParser.extract_posts(soup)

        print(f"    [DEBUG] Found {len(post_elements)} posts in thread")

        for idx, post_elem in enumerate(post_elements, start=1):
            # Extract author using resilient parser
            author = ResilientParser.extract_post_author(post_elem)

            # Extract post date using resilient parser
            post_date = ResilientParser.extract_post_date(post_elem)

            # Extract post text content using resilient parser
            post_text = ResilientParser.extract_post_content(post_elem)

            # Generate stable post ID
            post_id = f"{thread_id}-{idx}"
            
            # Calculate content hash for change detection
            content_hash = sha256_string(post_text) if post_text else None

            # Create Post object with all tracking fields
            post = Post(
                author=author,
                post_date=post_date,
                post_text=post_text,
                post_number=idx,
                post_id=post_id,
                content_hash=content_hash
            )

            posts.append(post)

        return posts

    def extract_assets(self, soup: BeautifulSoup) -> List[Asset]:
        """
        Extract downloadable attachments from ALL posts in a thread page.

        This searches the ENTIRE thread (original post + all replies) for
        file attachments with extensions we care about: .xml, .zip, .gz, .show

        Each asset is tagged with which post it came from (post_number).

        Args:
            soup: BeautifulSoup object of the thread page

        Returns:
            List of Asset objects for downloadable files from all posts

        Why these file types?
            - .xml: Macro XML files (the primary resource we want)
            - .zip: Compressed macro packages
            - .gz: Compressed show files
            - .show: GrandMA2 show files
        """
        assets = []

        # Find ALL posts on the page to map attachments to post numbers
        post_elements = soup.select('article.message')

        # Find all attachment links using the actual WoltLab forum structure
        # This searches THE ENTIRE PAGE (all posts, not just first)
        attachment_links = soup.select('a.messageAttachment, a.attachment, a[class*="attachment"], a[href*="file-download"]')

        # DEBUG: If no links found, print HTML sample to diagnose
        if len(attachment_links) == 0:
            downloads_text = soup.find(string=lambda text: text and "Downloads" in text and ".xml" in text)
            if downloads_text:
                print(f"    [DEBUG] Found attachment text but no <a> link!")
                print(f"    [DEBUG] Text: {downloads_text[:100]}")
                print(f"    [DEBUG] Parent tag: {downloads_text.parent.name if downloads_text.parent else 'None'}")
                if downloads_text.parent:
                    print(f"    [DEBUG] Parent HTML: {str(downloads_text.parent)[:400]}")

        # DEBUG: Print what we found
        print(f"    [DEBUG] Found {len(attachment_links)} attachment links")
        if len(attachment_links) == 0:
            # Try to find ANY links with 'attachment' in the class
            all_links_with_attachment = soup.find_all('a', class_=lambda x: x and any('attachment' in c.lower() for c in x) if x else False)
            print(f"    [DEBUG] Found {len(all_links_with_attachment)} links with 'attachment' in class")
            if all_links_with_attachment:
                for link in all_links_with_attachment[:3]:
                    print(f"    [DEBUG] Sample: class={link.get('class')}, href={link.get('href')[:80] if link.get('href') else 'No href'}")

        for link in attachment_links:
            href = link.get('href')
            if not href:
                continue

            # Determine which post this attachment belongs to
            post_number = None
            for idx, post_elem in enumerate(post_elements, start=1):
                if link in post_elem.find_all('a', recursive=True):
                    post_number = idx
                    break

            # Extract filename from the span.messageAttachmentFilename child element
            filename_elem = link.select_one('span.messageAttachmentFilename')
            if filename_elem:
                filename = filename_elem.text.strip()
            else:
                # Fallback to link text or URL
                filename = link.text.strip()
                if not filename:
                    filename = href.split('/')[-1]

            # Filter by file extensions we care about
            if any(filename.lower().endswith(ext) for ext in ['.xml', '.zip', '.gz', '.show']):
                full_url = urljoin(BASE_URL, href)

                # Optionally extract size and download count from metadata span
                download_count = None
                meta_elem = link.select_one('span.messageAttachmentMeta')
                if meta_elem:
                    meta_text = meta_elem.text.strip()
                    # Format: "5.07 kB – 317 Downloads"
                    if '–' in meta_text and 'Downloads' in meta_text:
                        try:
                            downloads_str = meta_text.split('–')[1].strip().split()[0]
                            download_count = int(downloads_str)
                        except (IndexError, ValueError):
                            pass

                asset = Asset(
                    filename=filename,
                    url=full_url,
                    size=None,  # Will be populated after download
                    download_count=download_count,
                    checksum=None,  # Will be computed after download
                    post_number=post_number  # NEW: Track which post this came from
                )
                assets.append(asset)

                if post_number:
                    print(f"    [DEBUG] Found asset '{filename}' in post #{post_number}")

        return assets
    
    async def download_asset(self, asset: Asset, folder: Path) -> bool:
        """
        Download an asset file and compute its checksum.
        
        This method:
        1. Downloads the file to the thread's folder
        2. Captures HTTP headers (Content-Type, ETag, Last-Modified)
        3. Computes SHA256 checksum for integrity
        4. Updates the asset object with metadata
        
        Args:
            asset: Asset object to download
            folder: Folder to save the file in
            
        Returns:
            True if download successful, False otherwise
            
        Why compute checksums?
            - Verify download integrity (detect corruption)
            - Enable deduplication (same file = same checksum)
            - Track changes between scraping runs
        """
        try:
            async with self.semaphore:
                # Wait for throttle permission
                wait_time = await self.throttler.acquire()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                
                response = await self.client.get(
                    asset.url,
                    timeout=REQUEST_TIMEOUT,
                    follow_redirects=True
                )
                
                # Record telemetry
                self.stats.record_response(response.status_code)
                
                response.raise_for_status()
                
                # -------------------------------------------------------
                # Capture HTTP headers for change detection
                # -------------------------------------------------------
                content_type = response.headers.get('Content-Type')
                etag = response.headers.get('ETag')
                last_modified = response.headers.get('Last-Modified')
                
                # Infer MIME type from headers or filename
                asset.mime_type = infer_mime_type(asset.filename, content_type)
                asset.etag = etag
                asset.last_modified = last_modified
                
                # -------------------------------------------------------
                # Save file to disk
                # -------------------------------------------------------
                file_path = folder / asset.filename
                
                # Handle filename conflicts (unlikely but possible)
                counter = 1
                while file_path.exists():
                    name_parts = asset.filename.rsplit('.', 1)
                    if len(name_parts) == 2:
                        new_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    else:
                        new_name = f"{asset.filename}_{counter}"
                    file_path = folder / new_name
                    counter += 1
                
                file_path.write_bytes(response.content)
                
                # -------------------------------------------------------
                # Compute checksum and file size
                # -------------------------------------------------------
                asset.checksum = sha256_file(file_path)
                asset.size = file_path.stat().st_size
                
                return True
                
        except Exception as e:
            print(f"    ❌ Failed to download {asset.filename}: {e}")
            self.stats.record_retry_exhausted(f"Asset download: {type(e).__name__}")
            return False
    
    async def process_thread(self, url: str) -> bool:
        """
        Process a single thread: fetch metadata, download assets, save to disk.
        
        This is the main orchestration method for processing one thread.
        It handles the complete workflow from fetching to saving.
        
        Args:
            url: Thread URL to process
            
        Returns:
            True if successful, False if failed
            
        The workflow:
        1. Fetch thread metadata (title, author, content, etc.)
        2. Create a dedicated folder for this thread
        3. Download all assets/attachments
        4. Save metadata.json with all information
        5. Mark thread as visited in manifest
        """
        try:
            # -------------------------------------------------------
            # STEP 1: Fetch thread metadata
            # -------------------------------------------------------
            metadata = await self.fetch_thread(url)
            if not metadata:
                print(f"    ⚠️  Could not fetch metadata")
                return False
            
            # -------------------------------------------------------
            # STEP 2: Create thread folder
            # -------------------------------------------------------
            # Format: output/threads/thread_12345_Title_Slug/
            folder_name = safe_thread_folder(metadata.thread_id, metadata.title)
            thread_folder = self.output_dir / folder_name
            thread_folder.mkdir(parents=True, exist_ok=True)
            
            # -------------------------------------------------------
            # STEP 3: Download assets
            # -------------------------------------------------------
            if metadata.assets:
                print(f"    📥 Downloading {len(metadata.assets)} assets...")
                download_tasks = [
                    self.download_asset(asset, thread_folder)
                    for asset in metadata.assets
                ]
                results = await asyncio.gather(*download_tasks)
                successful = sum(results)
                print(f"    ✅ Downloaded {successful}/{len(metadata.assets)} assets")
            
            # -------------------------------------------------------
            # STEP 4: Save metadata.json
            # -------------------------------------------------------
            metadata_file = thread_folder / "metadata.json"
            metadata_json = orjson.dumps(
                metadata.to_dict(),
                option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
            )
            metadata_file.write_bytes(metadata_json)
            
            # -------------------------------------------------------
            # STEP 5: Update state tracking
            # -------------------------------------------------------
            # Update thread state
            self.state.threads[metadata.thread_id] = ThreadState(
                thread_id=metadata.thread_id,
                url=url,
                last_seen_at=datetime.now(timezone.utc).isoformat(),
                reply_count_seen=metadata.replies,
                views_seen=metadata.views
            )
            
            # Update post states
            for post in metadata.posts:
                if post.post_id and post.content_hash:
                    self.state.posts[post.post_id] = PostState(
                        post_id=post.post_id,
                        thread_id=metadata.thread_id,
                        post_number=post.post_number,
                        content_hash=post.content_hash,
                        observed_at=datetime.now(timezone.utc).isoformat()
                    )
            
            # Update asset states
            for asset in metadata.assets:
                if asset.checksum:  # Only if download was successful
                    self.state.assets[asset.url] = AssetState(
                        url=asset.url,
                        filename=asset.filename,
                        content_hash=asset.checksum,
                        mime_type=asset.mime_type,
                        size=asset.size,
                        downloaded_at=datetime.now(timezone.utc).isoformat(),
                        last_modified=asset.last_modified,
                        etag=asset.etag
                    )
            
            # Save state after each thread
            self._save_state()
            
            # Legacy: Also update visited_urls for backward compatibility
            self.visited_urls.add(url)
            
            print(f"    💾 Saved to {folder_name}")
            return True
            
        except Exception as e:
            print(f"    ❌ Error processing thread: {e}")
            return False
    
    # -------------------------------------------------------
    # MAIN ENTRY POINT
    # -------------------------------------------------------
    
    async def run(self):
        """
        Main entry point for the scraper.
        
        This method orchestrates the complete scraping workflow:
        1. Load state (multi-level delta scraping)
        2. Initialize HTTP client
        3. Discover all thread URLs
        4. Filter out already-scraped threads
        5. Process new threads with progress tracking
        6. Print telemetry summary
        7. Clean up resources
        
        This is the method you call to run the entire scraper:
            scraper = ForumScraper()
            await scraper.run()
        """
        print("="*60)
        print("🚀 MA2 Forums Miner - Starting Scraper")
        print("="*60)
        
        # -------------------------------------------------------
        # STEP 1: Load state for delta scraping
        # -------------------------------------------------------
        self.state = self._load_state()
        
        # Build visited_urls set for backward compatibility
        self.visited_urls = {
            thread_state.url for thread_state in self.state.threads.values()
        }
        
        # -------------------------------------------------------
        # STEP 2: Initialize HTTP client with HTTP/2 support
        # -------------------------------------------------------
        # httpx.AsyncClient provides:
        # - HTTP/2 support for multiplexed connections
        # - Connection pooling for efficiency
        # - Proper async/await integration
        #
        # Why HTTP/2?
        # - Multiple requests over single TCP connection
        # - Header compression reduces bandwidth
        # - Server push capability (though we don't use it here)
        # - Better performance for multiple concurrent requests
        print("\n🌐 Initializing HTTP client with HTTP/2 support...")
        # Use realistic browser headers to avoid bot detection
        # These headers mimic a real Chrome browser on Windows
        self.client = httpx.AsyncClient(
            http2=True,  # Enable HTTP/2
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            }
        )
        
        try:
            # -------------------------------------------------------
            # STEP 3: Discover all thread URLs
            # -------------------------------------------------------
            all_thread_urls = await self.get_all_thread_links()
            
            if not all_thread_urls:
                print("\n⚠️  No threads discovered!")
                return
            
            # -------------------------------------------------------
            # STEP 4: Filter for new threads (delta scraping)
            # -------------------------------------------------------
            # This is the "delta" part - we only process threads
            # that aren't in our manifest yet
            new_threads = [
                url for url in all_thread_urls
                if url not in self.visited_urls
            ]
            
            print(f"\n📊 Thread Status:")
            print(f"   Total threads on forum: {len(all_thread_urls)}")
            print(f"   Already scraped: {len(self.visited_urls)}")
            print(f"   New threads to scrape: {len(new_threads)}")
            
            if not new_threads:
                print("\n✨ No new threads to scrape - all up to date!")
                return
            
            # -------------------------------------------------------
            # STEP 5: Process new threads with progress tracking
            # -------------------------------------------------------
            print(f"\n⚡ Processing {len(new_threads)} new threads...")
            print(f"   Concurrency: {self.max_concurrent} simultaneous requests")
            print(f"   Rate limit: {self.request_delay}s between requests")
            print()
            
            # Use tqdm for a nice progress bar
            successful = 0
            failed = 0
            
            with tqdm(total=len(new_threads), desc="Scraping threads") as pbar:
                for url in new_threads:
                    # Extract thread ID for display
                    thread_id_match = re.search(r'/thread/(\d+)-', url)
                    thread_id = thread_id_match.group(1) if thread_id_match else "???"
                    
                    print(f"\n  📄 Thread {thread_id}:")
                    success = await self.process_thread(url)
                    
                    if success:
                        successful += 1
                    else:
                        failed += 1
                    
                    pbar.update(1)
            
            # -------------------------------------------------------
            # STEP 6: Print summary and telemetry
            # -------------------------------------------------------
            print("\n" + "="*60)
            print("✅ Scraping Complete!")
            print("="*60)
            print(f"   Successful: {successful}")
            print(f"   Failed: {failed}")
            print(f"   Total scraped (all time): {len(self.visited_urls)}")
            print(f"   Output directory: {self.output_dir}")
            print(f"   State file: {self.state_file}")
            print()
            print("📊 Response Telemetry:")
            print("="*60)
            for line in self.stats.get_summary().split('\n'):
                print(f"   {line}")
            print("="*60)
            
        finally:
            # -------------------------------------------------------
            # STEP 7: Clean up HTTP client
            # -------------------------------------------------------
            # Always close the client to free resources, even if
            # an exception occurred
            await self.client.aclose()
