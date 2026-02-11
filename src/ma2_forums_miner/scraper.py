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
import logging
import re
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx
import orjson
from bs4 import BeautifulSoup
from tqdm import tqdm

from .models import Asset, Post, ThreadMetadata
from .utils import sha256_file, safe_thread_folder, date_folder

logger = logging.getLogger(__name__)

# Base directory for all output
OUTPUT_DIR = Path("output/threads")

# Manifest file tracks which threads we've already scraped
MANIFEST_FILE = Path("manifest.json")

# Forum URLs
BASE_URL = "https://forum.malighting.com"
BOARD_URL = f"{BASE_URL}/forum/board/35-grandma2-macro-share/"

# Allowed domains for URL validation (SSRF prevention)
ALLOWED_DOMAINS = {"forum.malighting.com"}

# Concurrency and rate limiting settings
MAX_CONCURRENT_REQUESTS = 8
REQUEST_DELAY = 1.5
REQUEST_TIMEOUT = 30.0

# Exponential backoff settings for rate limit handling
MAX_RETRIES = 5
INITIAL_BACKOFF = 2

# Maximum download size for assets (50 MB)
MAX_DOWNLOAD_SIZE = 50 * 1024 * 1024

# HTTP status codes that are safe to retry
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


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
        self.output_dir = output_dir
        self.manifest_file = manifest_file
        self.max_concurrent = max_concurrent
        self.request_delay = request_delay
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.visited_urls: Set[str] = set()
        self.client: Optional[httpx.AsyncClient] = None
        # Tracks thread metadata keyed by URL for post-run index generation
        self._thread_metadata: Dict[str, ThreadMetadata] = {}
    
    def _load_manifest(self) -> Set[str]:
        """Load previously visited thread URLs from manifest.json."""
        if self.manifest_file.exists():
            try:
                data = orjson.loads(self.manifest_file.read_bytes())
                logger.info("Loaded manifest: %d threads already scraped", len(data))
                return set(data)
            except Exception as e:
                logger.warning("Could not load manifest: %s. Starting fresh.", e)
                return set()
        else:
            logger.info("No manifest found - starting fresh scrape")
            return set()

    def _save_manifest(self):
        """Save visited URLs to manifest.json using atomic write."""
        try:
            data = sorted(list(self.visited_urls))
            tmp = self.manifest_file.with_suffix('.tmp')
            tmp.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
            tmp.rename(self.manifest_file)
        except Exception as e:
            logger.warning("Could not save manifest: %s", e)
    
    def _validate_url(self, url: str) -> bool:
        """Validate that a URL points to an allowed domain (SSRF prevention)."""
        parsed = urlparse(url)
        return parsed.hostname in ALLOWED_DOMAINS

    async def _fetch_with_retry(self, url: str) -> Optional[str]:
        """Fetch a URL with exponential backoff retry logic.

        Retries on rate limiting (429), server errors (5xx), and network errors.
        Rate-limit sleep is applied outside the semaphore to avoid holding slots.
        """
        if not self._validate_url(url):
            logger.warning("Blocked fetch to non-allowed domain: %s", url)
            return None

        retries = 0
        backoff = INITIAL_BACKOFF

        while retries < MAX_RETRIES:
            try:
                async with self.semaphore:
                    response = await self.client.get(
                        url,
                        timeout=REQUEST_TIMEOUT,
                        follow_redirects=True
                    )

                # Retryable status codes (429, 5xx)
                if response.status_code in RETRYABLE_STATUS_CODES:
                    logger.warning("HTTP %d for %s, retrying in %ds...",
                                   response.status_code, url, backoff)
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    retries += 1
                    continue

                response.raise_for_status()

                # Rate limiting delay outside semaphore
                await asyncio.sleep(self.request_delay)
                return response.text

            except httpx.HTTPStatusError as e:
                logger.error("HTTP error for %s: %s", url, e)
                return None
            except httpx.RequestError as e:
                logger.warning("Request error for %s: %s", url, e)
                if retries < MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    retries += 1
                else:
                    return None

        logger.error("Failed to fetch %s after %d attempts", url, MAX_RETRIES)
        return None
    
    async def get_all_thread_links(self) -> List[str]:
        """Discover all thread URLs from the forum board (all pages)."""
        logger.info("Discovering thread URLs...")

        first_page_html = await self._fetch_with_retry(BOARD_URL)
        if not first_page_html:
            logger.error("Could not fetch board page")
            return []

        soup = BeautifulSoup(first_page_html, "lxml")
        thread_links = self._extract_thread_links_from_page(soup)

        max_page = self._get_max_page_number(soup)
        logger.info("Found %d pages, first page has %d threads", max_page, len(thread_links))

        if max_page > 1:
            page_urls = [
                f"{BOARD_URL}?pageNo={page}"
                for page in range(2, max_page + 1)
            ]
            page_htmls = await asyncio.gather(
                *[self._fetch_with_retry(url) for url in page_urls]
            )
            for page_num, html in enumerate(page_htmls, start=2):
                if html:
                    page_soup = BeautifulSoup(html, "lxml")
                    links = self._extract_thread_links_from_page(page_soup)
                    thread_links.extend(links)
                else:
                    logger.warning("Page %d: Failed to fetch", page_num)

        unique_links = list(set(thread_links))

        # Include known test thread with attachments for verification
        test_thread = "https://forum.malighting.com/forum/thread/20248-abort-out-of-macro/"
        if test_thread not in unique_links:
            unique_links.append(test_thread)

        logger.info("Discovered %d unique threads", len(unique_links))
        return unique_links
    
    def _extract_thread_links_from_page(self, soup: BeautifulSoup) -> List[str]:
        """Extract thread URLs from a forum board page."""
        links = []
        thread_elements = soup.select('a.wbbTopicLink')

        for element in thread_elements:
            href = element.get('href')
            if href:
                full_url = urljoin(BASE_URL, href)
                if self._validate_url(full_url):
                    links.append(full_url)

        return links
    
    def _get_max_page_number(self, soup: BeautifulSoup) -> int:
        """Extract the maximum page number from pagination controls.

        Tries multiple detection methods: .pageNavigation links, any /page/ or
        pageNo= links, and "Page X of Y" text. Falls back to probing pages
        incrementally if detection fails.
        """
        max_page = 1

        # Method 1: Standard pagination navigation
        for link in soup.select('.pageNavigation a'):
            href = link.get('href', '')
            match = re.search(r'/page/(\d+)/', href) or re.search(r'[?&]pageNo=(\d+)', href)
            if match:
                max_page = max(max_page, int(match.group(1)))

        # Method 2: Any link with /page/ or pageNo= pattern
        if max_page == 1:
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if '/page/' in href or 'pageNo=' in href:
                    match = re.search(r'/page/(\d+)/', href) or re.search(r'[?&]pageNo=(\d+)', href)
                    if match:
                        max_page = max(max_page, int(match.group(1)))

        # Method 3: "Page X of Y" text
        if max_page == 1:
            page_info = soup.find(string=re.compile(r'Page \d+ of \d+', re.IGNORECASE))
            if page_info:
                match = re.search(r'of (\d+)', page_info, re.IGNORECASE)
                if match:
                    max_page = max(max_page, int(match.group(1)))

        # Method 4: If detection failed, probe incrementally.
        # Pages that return no threads will be harmlessly skipped.
        if max_page == 1:
            logger.info("Pagination detection failed, probing pages 2-30")
            max_page = 30

        return max_page
    
    def _get_thread_max_page(self, soup: BeautifulSoup) -> int:
        """Detect how many pages a thread has (reply pagination)."""
        max_page = 1
        for link in soup.select('.pageNavigation a, .pagination a'):
            href = link.get('href', '')
            match = re.search(r'/page/(\d+)/', href) or re.search(r'[?&]pageNo=(\d+)', href)
            if match:
                max_page = max(max_page, int(match.group(1)))
        if max_page == 1:
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if '/page/' in href or 'pageNo=' in href:
                    match = re.search(r'/page/(\d+)/', href) or re.search(r'[?&]pageNo=(\d+)', href)
                    if match:
                        max_page = max(max_page, int(match.group(1)))
        if max_page == 1:
            page_info = soup.find(string=re.compile(r'Page \d+ of \d+', re.IGNORECASE))
            if page_info:
                match = re.search(r'of (\d+)', page_info, re.IGNORECASE)
                if match:
                    max_page = max(max_page, int(match.group(1)))
        return max_page

    async def fetch_thread(self, url: str) -> Optional[ThreadMetadata]:
        """Fetch and parse a single thread including ALL pages of replies and assets."""
        html = await self._fetch_with_retry(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")

        thread_id_match = re.search(r'/thread/(\d+)-', url)
        if not thread_id_match:
            logger.warning("Could not extract thread ID from %s", url)
            return None
        thread_id = thread_id_match.group(1)

        title_elem = soup.select_one('h1.topic-title, .contentTitle')
        title = title_elem.text.strip() if title_elem else "Unknown Title"

        # Extract posts and assets from first page
        posts = self.extract_all_posts(soup)
        assets = self.extract_assets(soup)

        # Fetch remaining pages if the thread has multiple pages of replies
        max_page = self._get_thread_max_page(soup)
        if max_page > 1:
            logger.info("Thread %s has %d pages, fetching all...", thread_id, max_page)
            # Build page URLs — strip any existing pageNo from the base URL
            base_thread_url = re.sub(r'[?&]pageNo=\d+', '', url).rstrip('/')
            page_urls = [
                f"{base_thread_url}?pageNo={page}"
                for page in range(2, max_page + 1)
            ]
            page_htmls = await asyncio.gather(
                *[self._fetch_with_retry(pu) for pu in page_urls]
            )
            for page_num, page_html in enumerate(page_htmls, start=2):
                if not page_html:
                    logger.warning("Thread %s page %d: failed to fetch", thread_id, page_num)
                    continue
                page_soup = BeautifulSoup(page_html, "lxml")
                page_posts = self.extract_all_posts(page_soup)
                # Renumber posts to continue from the previous page
                offset = len(posts)
                for p in page_posts:
                    p.post_number = offset + p.post_number
                posts.extend(page_posts)
                assets.extend(self.extract_assets(page_soup))

        author = "Unknown"
        post_date = None
        post_text = ""
        if posts:
            author = posts[0].author
            post_date = posts[0].post_date
            post_text = posts[0].post_text

        replies = 0
        views = 0
        stats_elem = soup.select_one('.stats')
        if stats_elem:
            stats_text = stats_elem.text
            replies_match = re.search(r'(\d+)\s*(?:replies|antworten)', stats_text, re.I)
            if replies_match:
                replies = int(replies_match.group(1))
            views_match = re.search(r'(\d+)\s*(?:views|ansichten)', stats_text, re.I)
            if views_match:
                views = int(views_match.group(1))

        return ThreadMetadata(
            thread_id=thread_id,
            title=title,
            url=url,
            author=author,
            post_date=post_date,
            post_text=post_text,
            posts=posts,
            replies=replies,
            views=views,
            assets=assets
        )

    def extract_all_posts(self, soup: BeautifulSoup) -> List[Post]:
        """Extract ALL posts from a thread (original post + all replies)."""
        posts = []
        post_elements = soup.select('article.message')

        for idx, post_elem in enumerate(post_elements, start=1):
            author_elem = post_elem.select_one('.username')
            author = author_elem.text.strip() if author_elem else "Unknown"

            post_date = None
            time_elem = post_elem.select_one('time')
            if time_elem and time_elem.get('datetime'):
                post_date = time_elem['datetime']

            post_text = ""
            content_elem = post_elem.select_one('.messageContent, .messageText')
            if content_elem:
                post_text = content_elem.get_text(strip=True)

            posts.append(Post(
                author=author,
                post_date=post_date,
                post_text=post_text,
                post_number=idx
            ))

        return posts

    def extract_assets(self, soup: BeautifulSoup) -> List[Asset]:
        """Extract downloadable attachments (.xml, .zip, .gz, .show) from all posts."""
        assets = []
        post_elements = soup.select('article.message')
        attachment_links = soup.select(
            'a.messageAttachment, a.attachment, '
            'a[class*="attachment"], a[href*="file-download"]'
        )

        for link in attachment_links:
            href = link.get('href')
            if not href:
                continue

            full_url = urljoin(BASE_URL, href)
            if not self._validate_url(full_url):
                continue

            # Determine which post this attachment belongs to
            post_number = None
            for idx, post_elem in enumerate(post_elements, start=1):
                if link in post_elem.find_all('a', recursive=True):
                    post_number = idx
                    break

            # Extract filename
            filename_elem = link.select_one('span.messageAttachmentFilename')
            if filename_elem:
                filename = filename_elem.text.strip()
            else:
                filename = link.text.strip()
                if not filename:
                    filename = href.split('/')[-1]

            # Extract download count from metadata
            download_count = None
            meta_elem = link.select_one('span.messageAttachmentMeta')
            if meta_elem:
                meta_text = meta_elem.text.strip()
                if '\u2013' in meta_text and 'Downloads' in meta_text:
                    try:
                        downloads_str = meta_text.split('\u2013')[1].strip().split()[0]
                        download_count = int(downloads_str)
                    except (IndexError, ValueError):
                        pass

            assets.append(Asset(
                filename=filename,
                url=full_url,
                download_count=download_count,
                post_number=post_number
            ))

        return assets
    
    async def download_asset(self, asset: Asset, folder: Path) -> bool:
        """Download an asset file, verify size limits, and compute checksum."""
        if not self._validate_url(asset.url):
            logger.warning("Blocked download from non-allowed domain: %s", asset.url)
            return False

        try:
            async with self.semaphore:
                response = await self.client.get(
                    asset.url,
                    timeout=REQUEST_TIMEOUT,
                    follow_redirects=True
                )
                response.raise_for_status()

                # Enforce download size limit
                if len(response.content) > MAX_DOWNLOAD_SIZE:
                    logger.warning("Asset %s exceeds size limit (%d bytes), skipping",
                                   asset.filename, len(response.content))
                    return False

                # Sanitize filename to prevent path traversal
                safe_name = PurePosixPath(asset.filename).name
                if not safe_name:
                    safe_name = "unnamed_asset"
                file_path = folder / safe_name

                # Verify the resolved path is within the target folder
                if not file_path.resolve().is_relative_to(folder.resolve()):
                    logger.warning("Path traversal detected in filename: %s", asset.filename)
                    return False

                # Handle filename conflicts
                counter = 1
                while file_path.exists():
                    name_parts = safe_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        new_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    else:
                        new_name = f"{safe_name}_{counter}"
                    file_path = folder / new_name
                    counter += 1

                file_path.write_bytes(response.content)

                asset.checksum = sha256_file(file_path)
                asset.size = file_path.stat().st_size
                return True

        except Exception as e:
            logger.error("Failed to download %s: %s", asset.filename, e)
            return False
    
    async def process_thread(self, url: str) -> bool:
        """Process a single thread: fetch metadata, download assets, save to disk.

        Output is organized by date posted:
            output/threads/{YYYY}/{YYYY-MM-DD}/thread_{id}_{title}/
        """
        try:
            metadata = await self.fetch_thread(url)
            if not metadata:
                return False

            year, date_str = date_folder(metadata.post_date)
            folder_name = safe_thread_folder(metadata.thread_id, metadata.title)
            thread_folder = self.output_dir / year / date_str / folder_name
            thread_folder.mkdir(parents=True, exist_ok=True)

            if metadata.assets:
                results = await asyncio.gather(
                    *[self.download_asset(asset, thread_folder) for asset in metadata.assets]
                )
                logger.info("Downloaded %d/%d assets", sum(results), len(metadata.assets))

            metadata_file = thread_folder / "metadata.json"
            metadata_json = orjson.dumps(
                metadata.to_dict(),
                option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
            )
            metadata_file.write_bytes(metadata_json)

            self.visited_urls.add(url)
            self._thread_metadata[url] = metadata
            self._save_manifest()
            return True

        except Exception as e:
            logger.error("Error processing thread %s: %s", url, e)
            return False

    def _write_asset_type_index(self):
        """Write asset_type_index.json grouping threads by file extension.

        Output structure:
            {
              "by_type": { ".xml": [ {thread_id, title, url, files: [...]}, ... ] },
              "multi_type_threads": [ {thread_id, title, url, asset_types: [...]} ]
            }
        """
        by_type: Dict[str, list] = {}
        multi_type: list = []

        for url, meta in self._thread_metadata.items():
            types = meta.asset_types
            if not types:
                continue

            entry = {
                "thread_id": meta.thread_id,
                "title": meta.title,
                "url": meta.url,
            }

            for ft in types:
                by_type.setdefault(ft, [])
                files = [a.filename for a in meta.assets if a.file_type == ft]
                by_type[ft].append({**entry, "files": files})

            if len(types) > 1:
                multi_type.append({**entry, "asset_types": types})

        index = {
            "by_type": dict(sorted(by_type.items())),
            "multi_type_threads": multi_type,
        }
        index_path = self.output_dir / "asset_type_index.json"
        try:
            tmp = index_path.with_suffix('.tmp')
            tmp.write_bytes(orjson.dumps(index, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS))
            tmp.rename(index_path)
            logger.info("Wrote asset type index: %d types, %d multi-type threads",
                        len(by_type), len(multi_type))
        except Exception as e:
            logger.warning("Could not write asset type index: %s", e)

    async def run(self):
        """Main entry point: discover threads, scrape new ones, save results."""
        logger.info("MA2 Forums Miner - Starting Scraper")

        self.visited_urls = self._load_manifest()

        self.client = httpx.AsyncClient(
            http2=True,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
            }
        )

        try:
            all_thread_urls = await self.get_all_thread_links()
            if not all_thread_urls:
                logger.warning("No threads discovered!")
                return

            new_threads = [
                url for url in all_thread_urls
                if url not in self.visited_urls
            ]

            logger.info("Threads: %d total, %d already scraped, %d new",
                        len(all_thread_urls), len(self.visited_urls), len(new_threads))

            if not new_threads:
                logger.info("No new threads to scrape - all up to date!")
                return

            successful = 0
            failed = 0
            with tqdm(total=len(new_threads), desc="Scraping threads") as pbar:
                for url in new_threads:
                    if await self.process_thread(url):
                        successful += 1
                    else:
                        failed += 1
                    pbar.update(1)

            logger.info("Scraping complete: %d successful, %d failed, %d total",
                        successful, failed, len(self.visited_urls))

            self._write_asset_type_index()

        finally:
            await self.client.aclose()
