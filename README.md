# MA2 Forums Miner

A production-grade, educational async web scraper for the [MA Lighting grandMA2 Macro Share forum](https://forum.malighting.com/forum/board/35-grandma2-macro-share/). This tool demonstrates modern Python async patterns, implements advanced delta scraping with multi-level state tracking, adaptive throttling, and prepares data for downstream ML clustering pipelines.

## 📊 Current Statistics

**Last Updated**: See latest commit in `scraper_state.json`

| Metric | Count |
|--------|-------|
| **Threads Scraped** | 21 |
| **Threads with Attachments** | 1 (4.8%) |
| **Attachment Files Downloaded** | 1 |
| **XML Files** | 1 (CopyIfoutput.xml) |
| **ZIP Files** | 0 |
| **Thread ID Range** | 20248 - 69661 |
| **Oldest Thread** | 2010 (thread 20248) |
| **Newest Thread** | 2019+ (thread 69661) |

### Attachment Success Rate
- ✅ **1 thread with attachments** (thread_20248: CopyIfoutput.xml)
- ⚠️ **20 threads without attachments** (recent threads likely have no files)

**Note**: Most recent threads (2017-2019) appear to have no attachments. Older threads (2010-2015) are more likely to have downloadable macro files. See [SCOPE_ANALYSIS.md](SCOPE_ANALYSIS.md) for detailed breakdown.

## 🎯 Project Goals

1. **Educational**: Learn async/await, concurrency control, and web scraping best practices
2. **Production-Ready**: Implements adaptive throttling, exponential backoff, and robust error handling
3. **ML-Friendly**: Structured output format with schema versioning optimized for NLP clustering and analysis
4. **Efficient**: Multi-level delta scraping ensures you only process changed content on subsequent runs

## ✨ Features

### Core Scraping Engine
- **🚀 Async + HTTP/2**: Built with `httpx.AsyncClient` for efficient concurrent requests
- **⚡ Concurrency Control**: `asyncio.Semaphore` limits simultaneous connections (default: 8)
- **🎯 Adaptive Throttling**: Token bucket algorithm with jitter prevents server overload
- **🛡️ Smart Rate Limiting**: Automatic cool-off for HTTP 429/503 with exponential backoff
- **📊 Multi-Level Delta Scraping**: `scraper_state.json` tracks threads, posts, and assets individually
- **🔄 Content Change Detection**: SHA256 hashing detects edited posts and updated files
- **💾 Per-Thread Storage**: Self-contained folders with schema-versioned metadata and assets
- **🔐 Checksums**: SHA256 hashing for download integrity and deduplication
- **🌐 Parser Resilience**: CSS selector fallback chains adapt to forum template changes

### Data Collection
- **Thread Metadata**: Thread ID, title, author, date, complete post history, reply count, views
- **Complete Post History**: Captures ALL posts (original + replies) with stable IDs and content hashes
- **Asset Downloads**: Automatic download of `.xml`, `.zip`, `.gz`, `.show` files from all posts
- **HTTP Header Tracking**: Captures Content-Type, ETag, Last-Modified for efficient re-downloads
- **MIME Type Detection**: Smart detection from headers and file extensions
- **Schema Versioning**: All metadata includes schema_version and scraped_at timestamps
- **Type Safety**: Dataclass models with full docstrings for all data structures

### Telemetry & Monitoring
- **📈 Response Classification**: Tracks 2xx/3xx/4xx/5xx response counts
- **⚠️ Retry Tracking**: Records retry exhaustion reasons for diagnostics
- **📊 Telemetry Summary**: Detailed statistics displayed after each run

### Automation
- **GitHub Actions**: Automated weekly scraping with data commits
- **Idempotent**: Safe to run multiple times without duplicating work
- **Progress Tracking**: Real-time progress bars and detailed status messages

## 📋 Prerequisites

- **Python 3.10+** (required for modern async syntax)
- **pip** (Python package installer)
- **Git** (for cloning the repository)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/thisis-romar/ma2-forums-miner.git
cd ma2-forums-miner
```

### 2. Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Key dependencies:**
- `httpx[http2]` - Async HTTP client with HTTP/2 support
- `beautifulsoup4` + `lxml` - HTML parsing
- `orjson` - Fast JSON serialization
- `tqdm` - Progress bars

## 📖 Usage

### Manual Scraping

Run the scraper from the command line:

```bash
python run_scrape.py
```

**What happens:**
1. Loads `manifest.json` to check previously scraped threads
2. Discovers all threads from the forum (handles pagination automatically)
3. Downloads metadata and attachments for **new threads only**
4. Saves each thread to `output/threads/thread_{id}_{title}/`
5. Updates `manifest.json` after each successful thread

**First run:**
- Scrapes all threads (may take 30-60 minutes depending on forum size)

**Subsequent runs:**
- Only scrapes NEW threads posted since last run (much faster!)
- Idempotent - safe to run as often as you want

### GitHub Actions (Automated)

The included workflow (`.github/workflows/scrape.yml`) automatically scrapes weekly.

**Automatic Schedule:**
- Runs every Sunday at 3:00 AM UTC
- Commits new data back to the repository

**Manual Trigger:**
1. Go to your repository on GitHub
2. Click the **Actions** tab
3. Select **"Scrape MA2 Forums"**
4. Click **"Run workflow"**
5. Wait for completion (check logs for progress)

The workflow will:
- Run the scraper
- Commit new threads to `output/`
- Update `manifest.json`
- Push changes back to the repo

## 📁 Output Structure

Each scraped thread is saved to its own self-contained folder:

```
output/
└── threads/
    └── thread_30890_Moving_Fixtures_Between_Layers/
        ├── metadata.json          # Complete thread metadata
        ├── macro_example.xml      # Downloaded attachments
        └── showfile.zip
```

### metadata.json Format

The metadata now includes schema versioning and complete post history:

```json
{
  "schema_version": "1.0",
  "scraped_at": "2024-01-15T10:30:00Z",
  "thread_id": "30890",
  "title": "Moving Fixtures Between Layers",
  "url": "https://forum.malighting.com/thread/30890-...",
  "author": "johndoe",
  "post_date": "2024-01-15T10:30:00Z",
  "post_text": "Full text content (deprecated - use posts[0].post_text)",
  "posts": [
    {
      "post_id": "30890-1",
      "post_number": 1,
      "author": "johndoe",
      "post_date": "2024-01-15T10:30:00Z",
      "post_text": "Full text of original post...",
      "content_hash": "sha256:abc123..."
    },
    {
      "post_id": "30890-2",
      "post_number": 2,
      "author": "helper",
      "post_date": "2024-01-15T14:20:00Z",
      "post_text": "Here's how to solve that...",
      "content_hash": "sha256:def456..."
    }
  ],
  "replies": 1,
  "views": 1234,
  "assets": [
    {
      "filename": "macro.xml",
      "url": "https://forum.malighting.com/attachment/12345/",
      "size": 2048,
      "download_count": 15,
      "checksum": "sha256:abc123def456...",
      "post_number": 1,
      "mime_type": "application/xml",
      "etag": "\"abc123\"",
      "last_modified": "Mon, 14 Jan 2024 16:20:00 GMT"
    }
  ]
}
```

### scraper_state.json Format

The new state file tracks threads, posts, and assets individually for fine-grained delta scraping:

```json
{
  "schema_version": "1.0",
  "last_updated": "2024-01-15T10:30:00Z",
  "threads": {
    "30890": {
      "thread_id": "30890",
      "url": "https://forum.../thread/30890-...",
      "last_seen_at": "2024-01-15T10:30:00Z",
      "reply_count_seen": 1,
      "views_seen": 1234
    }
  },
  "posts": {
    "30890-1": {
      "post_id": "30890-1",
      "thread_id": "30890",
      "post_number": 1,
      "content_hash": "sha256:abc123...",
      "observed_at": "2024-01-15T10:30:00Z"
    }
  },
  "assets": {
    "https://forum.../attachment/12345/": {
      "url": "https://forum.../attachment/12345/",
      "filename": "macro.xml",
      "content_hash": "sha256:abc123...",
      "mime_type": "application/xml",
      "size": 2048,
      "downloaded_at": "2024-01-15T10:30:00Z",
      "etag": "\"abc123\"",
      "last_modified": "Mon, 14 Jan 2024 16:20:00 GMT"
    }
  }
}
```

## 📊 Data Scope & Coverage

### What's Captured
✅ **610 total threads** from grandMA2 Macro Share forum (100% coverage as of Feb 9, 2026)
✅ **Complete post history** - ALL posts including original and all replies
✅ **Content change detection** - SHA256 hashes detect edited posts
✅ **Thread metadata** - Author, title, date, reply count, view count with timestamps
✅ **All macro files** - .xml, .zip, .gz, .show files from entire thread
✅ **File metadata** - Checksums, sizes, MIME types, HTTP headers (ETag, Last-Modified)
✅ **Schema versioning** - All data includes schema_version for future migrations

### What's NOT Captured
❌ **Images/screenshots** - Only macro files are downloaded

### Statistics
- **610 threads total**
- **75 threads (12.3%)** contain downloadable macro files
- **535 threads (87.7%)** are discussion-only (but ALL posts are captured)
- **99 macro files** downloaded (78 XML, 21 ZIP/GZ/Show)

## 🔍 Finding Threads with Downloadable Files

### Quick Commands

**List all threads with XML files:**
```bash
find output/threads -name "*.xml" -exec dirname {} \; | sort -u
```

**List all threads with ZIP/GZ files:**
```bash
find output/threads -name "*.zip" -o -name "*.gz" | xargs -n1 dirname | sort -u
```

**Count files per thread:**
```bash
for dir in output/threads/*/; do
  count=$(find "$dir" -type f \( -name "*.xml" -o -name "*.zip" -o -name "*.gz" \) | wc -l)
  if [ $count -gt 0 ]; then
    echo "$count files: $(basename "$dir")"
  fi
done | sort -rn
```

**Search for specific macro types:**
```bash
# Find color-related macros
grep -l "color\|colour" output/threads/*/metadata.json

# Find effect macros
grep -l "effect" output/threads/*/metadata.json

# Find preset macros
grep -l "preset" output/threads/*/metadata.json
```

### Using Python to Find Files

```python
import json
from pathlib import Path

def find_threads_with_files():
    """Find all threads that have downloadable macro files."""
    threads_with_files = []

    for thread_dir in Path("output/threads").iterdir():
        if not thread_dir.is_dir():
            continue

        metadata_file = thread_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                data = json.load(f)

            # Check if thread has attachments
            if data.get("assets") and len(data["assets"]) > 0:
                # List actual files in directory
                files = list(thread_dir.glob("*.xml")) + \
                       list(thread_dir.glob("*.zip")) + \
                       list(thread_dir.glob("*.gz"))

                if files:
                    threads_with_files.append({
                        "thread_id": data["thread_id"],
                        "title": data["title"],
                        "url": data["url"],
                        "file_count": len(files),
                        "files": [f.name for f in files]
                    })

    return threads_with_files

# Run it
threads = find_threads_with_files()
print(f"Found {len(threads)} threads with downloadable files")

for t in threads[:10]:  # Show first 10
    print(f"\nThread {t['thread_id']}: {t['title']}")
    print(f"  Files: {', '.join(t['files'])}")
```

### Detailed Statistics

For a complete breakdown of all 75 threads with attachments, see **`STATISTICS.md`** which includes:
- Per-thread file listings
- File sizes and types
- Direct links to forum threads
- Attachment download counts

## 🏗️ Architecture

### High-Level Overview

```
┌─────────────────┐
│  run_scrape.py  │  Entry point - runs asyncio event loop
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              ForumScraper (scraper.py)                 │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 1. Load scraper_state.json (multi-level state)  │  │
│  │    - Thread states (reply counts, views)        │  │
│  │    - Post states (content hashes)               │  │
│  │    - Asset states (checksums, ETags)            │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 2. Initialize httpx.AsyncClient (HTTP/2)        │  │
│  │    - Adaptive throttler with token bucket       │  │
│  │    - Response telemetry                         │  │
│  │    - Parser resilience with fallback chains     │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 3. Discover thread URLs (async pagination)      │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 4. Filter new/updated threads (state checks)    │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 5. Process threads (concurrent with semaphore)  │  │
│  │    ├─ Fetch metadata with resilient parser      │  │
│  │    ├─ Hash all post content                     │  │
│  │    ├─ Download assets with HTTP header capture  │  │
│  │    ├─ Save metadata.json (schema v1.0)          │  │
│  │    └─ Update scraper_state.json                 │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              Output Structure                           │
│  scraper_state.json    (multi-level state tracking)    │
│  output/threads/       (per-thread folders)             │
└─────────────────────────────────────────────────────────┘
```

### Module Breakdown

**`scraper/scraper.py`** - Main scraper engine
- `ForumScraper` class with async/await throughout
- Thread discovery with automatic pagination
- Adaptive throttling with token bucket algorithm
- Exponential backoff for HTTP 429/503 errors
- Multi-level state tracking and delta scraping
- Response telemetry and retry tracking

**`scraper/models.py`** - Type-safe data models
- `ThreadMetadata` - Complete thread information with schema versioning
- `Post` - Individual post with stable ID and content hash
- `Asset` - Downloadable attachment with HTTP headers
- `ThreadState`, `PostState`, `AssetState` - State tracking models
- `ScraperState` - Complete scraper state container
- JSON serialization helpers

**`scraper/utils.py`** - Utility functions
- `sha256_file()` - Compute checksums for downloaded files
- `sha256_string()` - Compute checksums for text content
- `safe_thread_folder()` - Generate filesystem-safe folder names
- `infer_mime_type()` - MIME type detection from headers/extensions

**`scraper/telemetry.py`** - Monitoring and rate limiting
- `ResponseStats` - HTTP response classification and tracking
- `TokenBucket` - Token bucket rate limiter with jitter
- `AdaptiveThrottler` - Adaptive rate limiting with cool-off

**`scraper/parser.py`** - Resilient HTML parsing
- `SelectorChain` - CSS selector fallback chains
- `ResilientParser` - Forum-specific parsing with fallbacks

**`run_scrape.py`** - Entry point
- Simple wrapper that runs `asyncio.run(scraper.run())`
- Handles KeyboardInterrupt gracefully

## 🔄 How Multi-Level Delta Scraping Works

Multi-level delta scraping enables fine-grained change detection:

1. **First Run:**
   ```
   scraper_state.json: empty
   ↓
   Scrape ALL threads (e.g., 500 threads)
   ↓
   Track: threads, posts, assets with hashes
   ↓
   scraper_state.json: 500 threads tracked
   ```

2. **Second Run (1 week later):**
   ```
   scraper_state.json: 500 threads
   ↓
   Discover 505 threads on forum
   ↓
   Filter: 5 new threads
   Check: 500 existing threads for changes
   ↓
   Scrape: 5 new + threads with reply_count increases
   ↓
   scraper_state.json: 505 threads tracked
   ```

3. **Change Detection:**
   ```
   Thread changes: reply_count increased → re-scrape
   Post changes: content_hash differs → detect edit
   Asset changes: etag/last-modified differs → re-download
   ```

4. **Benefits:**
   - ✅ No duplicate downloads
   - ✅ Detect edited posts
   - ✅ Track asset updates
   - ✅ Fast incremental updates
   - ✅ Resume after interruption
   - ✅ Bandwidth efficient

**Legacy Support:**
```bash
# Old manifest.json is automatically migrated to scraper_state.json
# on first run with the new version
```

**Forcing a full re-scrape:**
```bash
# Delete the state and run again
rm scraper_state.json
   manifest.json: ["url1", "url2", ..., "url500"]
   ```

2. **Second Run (1 week later):**
   ```
   manifest.json: ["url1", ..., "url500"]
   ↓
   Discover 505 threads on forum
   ↓
   Filter: 505 - 500 = 5 new threads
   ↓
   Scrape ONLY 5 new threads
   ↓
python run_scrape.py
```

## 🧠 Code Style & Learning Focus

This project prioritizes **educational clarity** over brevity:

### ✅ What You'll Find
- **Verbose inline comments** explaining *why*, not just *what*
- **Detailed docstrings** on every class, method, and function
- **Step-by-step breakdowns** of complex async patterns
- **Explicit error handling** with clear try/except blocks
- **Descriptive variable names** (`thread_metadata` not `tm`)

### 📚 Learning Topics Covered
1. **Async/Await Fundamentals**
   - When to use `async def` vs regular `def`
   - How `await` yields control to the event loop
   - Why async improves I/O-bound performance

2. **Concurrency Control**
   - `asyncio.Semaphore` for limiting simultaneous requests
   - `asyncio.gather()` for waiting on multiple coroutines
   - Token bucket algorithm for rate limiting
   - Balancing speed vs server load

3. **HTTP Best Practices**
   - Adaptive rate limiting with jitter
   - Exponential backoff for transient failures (429/503)
   - HTTP header capture (ETag, Last-Modified)
   - Proper User-Agent headers

4. **Data Engineering**
   - Schema versioning for data migrations
   - Multi-level state tracking for change detection
   - Content fingerprinting with SHA256
   - Structured folder hierarchy for ML pipelines
   - Idempotent operations

5. **Parser Resilience**
   - CSS selector fallback chains
   - Graceful degradation when HTML changes
   - Defensive parsing strategies

## 🛠️ Configuration

All configuration is done via constants in `scraper/scraper.py`:

```python
# Concurrency and rate limiting
MAX_CONCURRENT_REQUESTS = 8      # Simultaneous HTTP requests
REQUEST_DELAY = 1.5              # Seconds between requests
REQUEST_TIMEOUT = 30.0           # Request timeout in seconds

# Exponential backoff
MAX_RETRIES = 5                  # Retry attempts for failed requests
INITIAL_BACKOFF = 2              # Initial backoff delay (doubles each retry)
```

**Tuning guidance:**
- **Increase `MAX_CONCURRENT_REQUESTS`** (e.g., 16) for faster scraping if your network supports it
- **Increase `REQUEST_DELAY`** (e.g., 3.0) if you encounter rate limiting
- **Decrease delays** only if you're scraping your own test server

## 🗺️ Roadmap

### ✅ Phase 1: Core Scraping (Current)
- [x] Async scraper with httpx
- [x] Delta scraping via manifest
- [x] Per-thread folder structure
- [x] Asset downloading with checksums
- [x] GitHub Actions workflow

### 🔜 Phase 2: NLP Clustering (Next)
- [ ] Sentence embeddings with `sentence-transformers`
- [ ] HDBSCAN clustering algorithm
- [ ] Cluster visualization and analysis
- [ ] Topic modeling for cluster interpretation

### 🔮 Phase 3: Advanced Features (Future)
- [ ] Web dashboard for browsing clusters
- [ ] Automated macro quality scoring
- [ ] Duplicate detection across versions
- [ ] API for accessing scraped data

## 🐛 Troubleshooting

**Problem: Rate limited (HTTP 429)**
```
Solution: Increase REQUEST_DELAY in scraper.py
Example: REQUEST_DELAY = 3.0  # Was 1.5
```

**Problem: Timeout errors**
```
Solution: Increase REQUEST_TIMEOUT in scraper.py
Example: REQUEST_TIMEOUT = 60.0  # Was 30.0
```

**Problem: Want to re-scrape everything**
```bash
# Delete manifest and run again
rm manifest.json
python run_scrape.py
```

**Problem: Script interrupted mid-run**
```
Solution: Just run it again! Progress is saved in manifest.json.
The scraper will pick up where it left off.
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 🎓 Educational Use

This project is designed as a learning resource for:
- Python async/await patterns
- Web scraping best practices
- Concurrent programming with semaphores
- Data pipeline design for ML

Feel free to use this as a reference for your own scraping projects!

## 🔗 Target Forum

This scraper targets: https://forum.malighting.com/forum/board/35-grandma2-macro-share/

**Please be respectful:**
- Default rate limiting is conservative (1.5s delays)
- Only scrape during off-peak hours if possible
- Consider contacting forum admins for large-scale scraping

## ⚠️ Disclaimer

This tool is for educational purposes. Always:
- Respect robots.txt and terms of service
- Implement rate limiting and backoff
- Be a good internet citizen
- Seek permission for large-scale scraping

---

**Built with ❤️ for the grandMA2 community**

