# MA2 Forums Miner

A production-grade, educational async web scraper for the [MA Lighting grandMA2 Macro Share forum](https://forum.malighting.com/forum/board/35-grandma2-macro-share/). This tool demonstrates modern Python async patterns, implements delta scraping for efficient incremental updates, and prepares data for downstream ML clustering pipelines.

## 📊 Current Collection Statistics

| Metric | Count |
|--------|-------|
| **Total Threads Scraped** | 610 |
| **Threads with Downloadable Files** | 75 (12.3%) |
| **Total Macro Files** | 99 |
| **XML Files** | 78 |
| **ZIP/GZ/Show Files** | 21 |
| **Total Collection Size** | 14 MB |
| **Forum Coverage** | Complete (30 pages) |

### 🎯 Threads with Downloadable Files

Browse the complete collection in `output/threads/`. Here are some notable threads with macro files:

**Large Showfiles & Archives:**
- Thread 10646: `BuildSeq.xml` (1.5MB), `BuildSeq2.xml` (3.1MB), `Colour Create and Label.xml` (875KB)
- Thread 67220: `strange variable.show.gz` (1.29MB)
- Thread 66952: `shaper test.show.gz` (1006KB)
- Thread 66922: `worlds.show.gz` (350KB)
- Thread 66365: `dmx remotes.show.gz` (966KB)

**Macro Collections:**
- Thread 33854: `ScrollerWizard.xml` (414KB), `ScrollerWizardV3.xml` (190KB)
- Thread 38697: `Invert SelOrder.xml` (2.3MB)
- Thread 32922: LEE & ROSCO Filter macros (1.15MB, 1.06MB)

**See `STATISTICS.md` for complete per-thread breakdown of all 75 threads with attachments!**

### 📈 Growth Timeline

- **Feb 9, 2026**: Complete forum scrape - 610 threads, 99 files
- **Automated weekly updates** via GitHub Actions

## 🎯 Project Goals

1. **Educational**: Learn async/await, concurrency control, and web scraping best practices
2. **Production-Ready**: Implements rate limiting, exponential backoff, and robust error handling
3. **ML-Friendly**: Structured output format optimized for NLP clustering and analysis
4. **Efficient**: Delta scraping ensures you only process new content on subsequent runs

## ✨ Features

### Core Scraping Engine
- **🚀 Async + HTTP/2**: Built with `httpx.AsyncClient` for efficient concurrent requests
- **⚡ Concurrency Control**: `asyncio.Semaphore` limits simultaneous connections (default: 8)
- **🕐 Rate Limiting**: Configurable delays (1.5s default) between requests to respect servers
- **🔄 Exponential Backoff**: Automatic retry with backoff for HTTP 429 rate limit errors
- **📊 Delta Scraping**: `manifest.json` tracks visited threads for incremental updates
- **💾 Per-Thread Storage**: Self-contained folders with metadata and downloaded assets
- **🔐 Checksums**: SHA256 hashing for download integrity and deduplication

### Data Collection
- **Complete Metadata**: Thread ID, title, author, date, post text, replies, views
- **Asset Downloads**: Automatic download of `.xml`, `.zip`, `.gz`, `.show` files
- **Type Safety**: Dataclass models with full docstrings for all data structures

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

```json
{
  "thread_id": "30890",
  "title": "Moving Fixtures Between Layers",
  "url": "https://forum.malighting.com/thread/30890-...",
  "author": "johndoe",
  "post_date": "2024-01-15T10:30:00Z",
  "post_text": "Full text content of the first post...",
  "replies": 5,
  "views": 1234,
  "assets": [
    {
      "filename": "macro.xml",
      "url": "https://forum.malighting.com/attachment/12345/",
      "size": 2048,
      "download_count": null,
      "checksum": "sha256:abc123def456..."
    }
  ]
}
```

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
│  │ 1. Load manifest.json (delta tracking)          │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 2. Initialize httpx.AsyncClient (HTTP/2)        │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 3. Discover thread URLs (async pagination)      │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 4. Filter new threads (set difference)          │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 5. Process threads (concurrent with semaphore)  │  │
│  │    ├─ Fetch metadata                            │  │
│  │    ├─ Download assets (checksums)               │  │
│  │    ├─ Save metadata.json                        │  │
│  │    └─ Update manifest                           │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              Output Structure                           │
│  manifest.json         (visited thread URLs)            │
│  output/threads/       (per-thread folders)             │
└─────────────────────────────────────────────────────────┘
```

### Module Breakdown

**`scraper/scraper.py`** - Main scraper engine
- `ForumScraper` class with async/await throughout
- Thread discovery with automatic pagination
- Concurrent processing with semaphore-based rate limiting
- Exponential backoff for HTTP 429 errors
- Manifest-based delta scraping

**`scraper/models.py`** - Type-safe data models
- `ThreadMetadata` dataclass for thread information
- `Asset` dataclass for downloadable attachments
- JSON serialization helpers

**`scraper/utils.py`** - Utility functions
- `sha256_file()` - Compute checksums for downloaded files
- `safe_thread_folder()` - Generate filesystem-safe folder names

**`run_scrape.py`** - Entry point
- Simple wrapper that runs `asyncio.run(scraper.run())`
- Handles KeyboardInterrupt gracefully

## 🔄 How Delta Scraping Works

Delta scraping ensures efficient incremental updates:

1. **First Run:**
   ```
   manifest.json: []  (empty)
   ↓
   Scrape ALL threads (e.g., 500 threads)
   ↓
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
   manifest.json: ["url1", ..., "url505"]
   ```

3. **Benefits:**
   - ✅ No duplicate downloads
   - ✅ Fast incremental updates
   - ✅ Resume after interruption
   - ✅ Bandwidth efficient

**Forcing a full re-scrape:**
```bash
# Delete the manifest and run again
rm manifest.json
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
   - Balancing speed vs server load

3. **HTTP Best Practices**
   - Rate limiting with configurable delays
   - Exponential backoff for transient failures
   - Proper User-Agent headers

4. **Data Engineering**
   - Structured folder hierarchy for ML pipelines
   - SHA256 checksums for integrity verification
   - Idempotent operations

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

