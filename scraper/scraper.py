"""
Async forum scraper for MA Lighting grandMA2 Macro Share forum.

This module implements a production-grade, educational scraper that demonstrates:
- Async/await patterns for efficient I/O
- Concurrency control with semaphores
- Rate limiting and exponential backoff
- Delta scraping for incremental updates
- Organized output structure for ML pipelines

Target: https://forum.malighting.com/forum/board/35-grandma2-macro-share/
"""

import asyncio
import json
import re
import time
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urljoin

import httpx
import orjson
from bs4 import BeautifulSoup
from tqdm import tqdm

from .models import Asset, ThreadMetadata
from .utils import sha256_file, safe_thread_folder


# -------------------------------------------------------
# CONSTANTS
# -------------------------------------------------------
# Using constants makes the code more maintainable and documents
# important configuration values in one place

# Base directory for all output
OUTPUT_DIR = Path("output/threads")

# Manifest file tracks which threads we've already scraped
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


class ForumScraper:
    """
    Async scraper for MA Lighting grandMA2 Macro Share forum.
    
    This scraper demonstrates production-grade async Python patterns:
    
    1. **Async/Await**: All I/O operations use async to avoid blocking
    2. **Concurrency Control**: Semaphore limits simultaneous requests
    3. **Rate Limiting**: Built-in delays between requests
    4. **Error Handling**: Exponential backoff for transient failures
    5. **Delta Scraping**: Only scrapes new threads via manifest tracking
    6. **Organized Output**: Per-thread folders with metadata and assets
    
    Usage:
        scraper = ForumScraper()
        await scraper.run()
    """
    
    def __init__(
        self,
        output_dir: Path = OUTPUT_DIR,
        manifest_file: Path = MANIFEST_FILE,
        max_concurrent: int = MAX_CONCURRENT_REQUESTS,
        request_delay: float = REQUEST_DELAY
    ):
        """
        Initialize the forum scraper.
        
        Args:
            output_dir: Base directory for scraped data
            manifest_file: Path to manifest JSON file
            max_concurrent: Maximum concurrent HTTP requests
            request_delay: Delay between requests in seconds
        """
        self.output_dir = output_dir
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
        
        # Visited threads tracking (loaded from manifest)
        self.visited_urls: Set[str] = set()
        
        # HTTP client (initialized in run())
        self.client: Optional[httpx.AsyncClient] = None
    
    # -------------------------------------------------------
    # MANIFEST MANAGEMENT
    # -------------------------------------------------------
    # The manifest tracks which threads we've already scraped.
    # This enables "delta scraping" - on subsequent runs, we only
    # process NEW threads, making the scraper efficient and safe
    # to run repeatedly without duplicating work.
    # -------------------------------------------------------
    
    def _load_manifest(self) -> Set[str]:
        """
        Load the set of previously visited thread URLs from manifest.json.
        
        The manifest is a simple JSON array of URL strings. Using a set
        provides O(1) lookup performance when checking if a thread was
        already scraped.
        
        Returns:
            Set of URL strings that have already been processed.
            Returns an empty set if no manifest exists yet.
            
        Why orjson?
            orjson is significantly faster than the standard library's json
            module, especially for large files. Since the manifest grows
            over time, this optimization matters for long-running projects.
        """
        if self.manifest_file.exists():
            try:
                # orjson.loads() requires bytes, not str
                data = orjson.loads(self.manifest_file.read_bytes())
                print(f"📖 Loaded manifest: {len(data)} threads already scraped")
                return set(data)
            except Exception as e:
                print(f"⚠️  Warning: Could not load manifest: {e}")
                print("   Starting fresh...")
                return set()
        else:
            print("📄 No manifest found - starting fresh scrape")
            return set()
    
    def _save_manifest(self):
        """
        Save the current set of visited URLs to manifest.json.
        
        This is called after each thread is successfully scraped to ensure
        we don't lose progress if the script is interrupted.
        
        Why save after each thread?
            If the script crashes or is interrupted, we want to preserve
            as much progress as possible. Saving incrementally means we
            never have to re-scrape threads we've already completed.
        """
        try:
            # Convert set to sorted list for consistent output
            data = sorted(list(self.visited_urls))
            
            # orjson.dumps() produces bytes, write directly
            # option=orjson.OPT_INDENT_2 makes the file human-readable
            self.manifest_file.write_bytes(
                orjson.dumps(data, option=orjson.OPT_INDENT_2)
            )
        except Exception as e:
            print(f"⚠️  Warning: Could not save manifest: {e}")
    
    # -------------------------------------------------------
    # HTTP REQUEST HANDLING
    # -------------------------------------------------------
    # These methods handle fetching pages with proper error handling,
    # rate limiting, and exponential backoff for transient failures.
    # -------------------------------------------------------
    
    async def _fetch_with_retry(self, url: str) -> Optional[str]:
        """
        Fetch a URL with exponential backoff retry logic.
        
        This method implements a robust retry strategy for handling
        transient network errors and rate limiting (HTTP 429).
        
        Args:
            url: URL to fetch
            
        Returns:
            Response text if successful, None if all retries failed
            
        How exponential backoff works:
            1. Try the request
            2. If it fails with 429 (rate limit), wait and retry
            3. Each retry waits TWICE as long as the previous attempt
            4. Example: 2s, 4s, 8s, 16s, 32s
            5. This gives the server time to recover from load
            
        Why use exponential backoff?
            - Linear delays (2s, 2s, 2s...) can keep hammering a struggling server
            - Exponential delays give increasing time for recovery
            - Industry standard pattern (used by AWS, Google APIs, etc.)
        """
        # -------------------------------------------------------
        # Use semaphore to limit concurrent requests
        # -------------------------------------------------------
        # The 'async with' pattern automatically acquires a semaphore
        # ticket at entry and releases it at exit (even if an exception occurs)
        async with self.semaphore:
            retries = 0
            backoff = INITIAL_BACKOFF
            
            while retries < MAX_RETRIES:
                try:
                    # -------------------------------------------------------
                    # Make the HTTP request
                    # -------------------------------------------------------
                    response = await self.client.get(
                        url,
                        timeout=REQUEST_TIMEOUT,
                        follow_redirects=True
                    )
                    
                    # -------------------------------------------------------
                    # Handle rate limiting (HTTP 429)
                    # -------------------------------------------------------
                    if response.status_code == 429:
                        print(f"⏱️  Rate limited! Waiting {backoff}s before retry...")
                        await asyncio.sleep(backoff)
                        backoff *= 2  # Double the backoff for next attempt
                        retries += 1
                        continue
                    
                    # -------------------------------------------------------
                    # Handle other HTTP errors
                    # -------------------------------------------------------
                    response.raise_for_status()
                    
                    # -------------------------------------------------------
                    # Rate limiting: delay before next request
                    # -------------------------------------------------------
                    # Even successful requests should be spaced out to be
                    # respectful to the server
                    await asyncio.sleep(self.request_delay)
                    
                    return response.text
                    
                except httpx.HTTPStatusError as e:
                    print(f"❌ HTTP error for {url}: {e}")
                    return None
                except httpx.RequestError as e:
                    print(f"⚠️  Request error for {url}: {e}")
                    if retries < MAX_RETRIES - 1:
                        print(f"   Retrying in {backoff}s...")
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        retries += 1
                    else:
                        return None
            
            # All retries exhausted
            print(f"❌ Failed to fetch {url} after {MAX_RETRIES} attempts")
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
        
        # -------------------------------------------------------
        # STEP 2: Fetch remaining pages concurrently
        # -------------------------------------------------------
        if max_page > 1:
            # Create list of page URLs to fetch
            page_urls = [
                f"{BOARD_URL}page/{page}/"
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
            for html in page_htmls:
                if html:
                    soup = BeautifulSoup(html, "lxml")
                    links = self._extract_thread_links_from_page(soup)
                    thread_links.extend(links)
        
        # -------------------------------------------------------
        # STEP 3: Deduplicate and return
        # -------------------------------------------------------
        # Using set() removes duplicates, then convert back to list
        unique_links = list(set(thread_links))
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
            
            We extract all these numbers and return the maximum.
        """
        max_page = 1
        
        # Find pagination links
        pagination_links = soup.select('.pageNavigation a')
        
        for link in pagination_links:
            href = link.get('href', '')
            # Look for pattern like "/page/123/"
            match = re.search(r'/page/(\d+)/', href)
            if match:
                page_num = int(match.group(1))
                max_page = max(max_page, page_num)
        
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
        # Extract thread title
        # -------------------------------------------------------
        title_elem = soup.select_one('h1.topic-title, .contentTitle')
        title = title_elem.text.strip() if title_elem else "Unknown Title"
        
        # -------------------------------------------------------
        # Extract first post (the main thread content)
        # -------------------------------------------------------
        # The first post contains the primary content we'll use for
        # clustering and analysis
        first_post = soup.select_one('article.message')
        
        author = "Unknown"
        post_date = None
        post_text = ""
        
        if first_post:
            # Extract author
            author_elem = first_post.select_one('.username')
            if author_elem:
                author = author_elem.text.strip()
            
            # Extract post date
            time_elem = first_post.select_one('time')
            if time_elem and time_elem.get('datetime'):
                post_date = time_elem['datetime']
            
            # Extract post text content
            content_elem = first_post.select_one('.messageContent, .messageText')
            if content_elem:
                post_text = content_elem.get_text(strip=True)
        
        # -------------------------------------------------------
        # Extract thread statistics (replies, views)
        # -------------------------------------------------------
        replies = 0
        views = 0
        
        # These might be in various places depending on forum layout
        stats_elem = soup.select_one('.stats')
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
        # Build and return ThreadMetadata object
        # -------------------------------------------------------
        return ThreadMetadata(
            thread_id=thread_id,
            title=title,
            url=url,
            author=author,
            post_date=post_date,
            post_text=post_text,
            replies=replies,
            views=views,
            assets=assets
        )
    
    def extract_assets(self, soup: BeautifulSoup) -> List[Asset]:
        """
        Extract downloadable attachments from a thread page.

        This looks for file attachments with extensions we care about:
        .xml, .zip, .gz, .show

        Args:
            soup: BeautifulSoup object of the thread page

        Returns:
            List of Asset objects for downloadable files

        Why these file types?
            - .xml: Macro XML files (the primary resource we want)
            - .zip: Compressed macro packages
            - .gz: Compressed show files
            - .show: GrandMA2 show files
        """
        assets = []

        # Find all attachment links using the actual WoltLab forum structure
        # Attachments use class "messageAttachment" with filename in child span
        attachment_links = soup.select('a.messageAttachment')

        for link in attachment_links:
            href = link.get('href')
            if not href:
                continue

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
                    checksum=None  # Will be computed after download
                )
                assets.append(asset)

        return assets
    
    async def download_asset(self, asset: Asset, folder: Path) -> bool:
        """
        Download an asset file and compute its checksum.
        
        This method:
        1. Downloads the file to the thread's folder
        2. Computes SHA256 checksum for integrity
        3. Updates the asset object with size and checksum
        
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
                response = await self.client.get(
                    asset.url,
                    timeout=REQUEST_TIMEOUT,
                    follow_redirects=True
                )
                response.raise_for_status()
                
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
            # STEP 5: Update manifest
            # -------------------------------------------------------
            self.visited_urls.add(url)
            self._save_manifest()
            
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
        1. Load manifest (delta scraping)
        2. Initialize HTTP client
        3. Discover all thread URLs
        4. Filter out already-scraped threads
        5. Process new threads with progress tracking
        6. Clean up resources
        
        This is the method you call to run the entire scraper:
            scraper = ForumScraper()
            await scraper.run()
        """
        print("="*60)
        print("🚀 MA2 Forums Miner - Starting Scraper")
        print("="*60)
        
        # -------------------------------------------------------
        # STEP 1: Load manifest for delta scraping
        # -------------------------------------------------------
        self.visited_urls = self._load_manifest()
        
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
        self.client = httpx.AsyncClient(
            http2=True,  # Enable HTTP/2
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={
                'User-Agent': 'MA2-Forums-Miner/1.0 (Educational Project)'
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
            # STEP 6: Print summary
            # -------------------------------------------------------
            print("\n" + "="*60)
            print("✅ Scraping Complete!")
            print("="*60)
            print(f"   Successful: {successful}")
            print(f"   Failed: {failed}")
            print(f"   Total scraped (all time): {len(self.visited_urls)}")
            print(f"   Output directory: {self.output_dir}")
            print(f"   Manifest file: {self.manifest_file}")
            print("="*60)
            
        finally:
            # -------------------------------------------------------
            # STEP 7: Clean up HTTP client
            # -------------------------------------------------------
            # Always close the client to free resources, even if
            # an exception occurred
            await self.client.aclose()
