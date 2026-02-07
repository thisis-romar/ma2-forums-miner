# MA2 Forums Miner

An async Python CLI tool that crawls the MA Lighting grandMA2 Macro Share forum, downloads attachments, extracts metadata, and performs NLP clustering using sentence-transformers + HDBSCAN.

## Features

- **Async Scraping**: Fast, concurrent thread scraping with `aiohttp`
- **Pagination**: Automatically discovers and scrapes all pages
- **Attachment Downloading**: Downloads `.xml`, `.zip`, `.gz`, and `.show` files
- **Full Metadata Extraction**: Captures thread titles, authors, dates, replies, views, and post content
- **Organized Storage**: Each thread saved to its own folder with `metadata.json`
- **Delta Scraping**: Manifest-based tracking to only scrape new threads
- **NLP Clustering**: Semantic clustering using sentence-transformers and HDBSCAN
- **GitHub Actions**: Automated weekly scraping workflow
- **Modular Design**: Separate scraper, downloader, and clustering modules

## Installation

```bash
# Clone the repository
git clone https://github.com/thisis-romar/ma2-forums-miner.git
cd ma2-forums-miner

# Install dependencies
pip install -r requirements.txt

# Or install as package
pip install -e .
```

## Usage

### Scraping Threads

Scrape all threads from the forum:

```bash
python -m ma2_miner.cli scrape
```

Options:
- `--output-dir`: Output directory (default: `output`)
- `--manifest`: Manifest file path (default: `manifest.json`)
- `--full`: Force full scrape, ignoring manifest
- `--no-attachments`: Skip downloading attachments

### Delta Scraping

By default, the scraper uses a manifest file to track already-scraped threads:

```bash
# First run: scrapes all threads
python -m ma2_miner.cli scrape

# Second run: only scrapes new threads
python -m ma2_miner.cli scrape
```

To force a full re-scrape:

```bash
python -m ma2_miner.cli scrape --full
```

### NLP Clustering

Run clustering analysis on scraped threads:

```bash
python -m ma2_miner.cli cluster
```

Options:
- `--output-dir`: Directory with scraped data (default: `output`)
- `--model`: Sentence transformer model (default: `all-MiniLM-L6-v2`)
- `--min-cluster-size`: Minimum cluster size (default: `5`)
- `--result-file`: Output file for results (default: `clusters.json`)

### Statistics

View scraping statistics:

```bash
python -m ma2_miner.cli stats
```

## Project Structure

```
ma2-forums-miner/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions workflow
├── src/
│   └── ma2_miner/
│       ├── __init__.py         # Package initialization
│       ├── scraper.py          # Forum scraping logic
│       ├── downloader.py       # Attachment downloader
│       ├── manifest.py         # Delta scraping manifest
│       ├── clustering.py       # NLP clustering module
│       └── cli.py              # CLI interface
├── .gitignore
├── requirements.txt            # Python dependencies
├── setup.py                    # Package setup
└── README.md                   # This file
```

## Output Structure

Each scraped thread is saved to its own directory:

```
output/
├── {thread_id}_{thread_title}/
│   ├── metadata.json           # Thread metadata and posts
│   └── attachments/            # Downloaded attachments
│       ├── file1.xml
│       ├── file2.zip
│       └── ...
└── clusters.json               # Clustering results
```

### metadata.json Format

```json
{
  "thread_id": "12345",
  "title": "Thread Title",
  "url": "https://forum.malighting.com/...",
  "author": "Username",
  "date": "2024-01-01T00:00:00Z",
  "replies": 10,
  "views": 150,
  "posts": [
    {
      "post_id": "67890",
      "author": "Username",
      "date": "2024-01-01T00:00:00Z",
      "content": "Post content..."
    }
  ],
  "attachments": [
    {
      "url": "https://...",
      "filename": "file.xml",
      "post_id": "67890"
    }
  ],
  "downloaded_attachments": [
    "output/12345_Thread_Title/attachments/file.xml"
  ]
}
```

## Clustering Output

The clustering module generates a `clusters.json` file:

```json
{
  "num_threads": 150,
  "num_clusters": 8,
  "cluster_info": {
    "0": {
      "size": 25,
      "representative_title": "Most representative thread title",
      "thread_ids": ["123", "456", ...]
    }
  },
  "threads": [
    {
      "thread_id": "123",
      "title": "Thread Title",
      "cluster": 0
    }
  ]
}
```

## GitHub Actions Workflow

The included workflow automatically:
- Runs linting and import checks on push/PR
- Performs weekly scraping (Sunday 00:00 UTC)
- Runs clustering analysis
- Uploads artifacts
- Optionally commits results back to the repository

Trigger manually:
1. Go to Actions tab in GitHub
2. Select "MA2 Forums Miner CI"
3. Click "Run workflow"

## Architecture

### Modular Components

1. **Scraper** (`scraper.py`): Async forum scraping with BeautifulSoup
   - Thread list pagination
   - Thread detail extraction
   - Post and attachment parsing

2. **Downloader** (`downloader.py`): Async file downloading
   - Concurrent attachment downloads
   - Automatic filename conflict resolution
   - Organized folder structure

3. **Manifest** (`manifest.py`): Delta scraping support
   - JSON-based tracking
   - Thread metadata persistence
   - Incremental update support

4. **Clustering** (`clustering.py`): NLP analysis
   - Sentence embeddings with sentence-transformers
   - HDBSCAN clustering
   - Cluster analysis and reporting

5. **CLI** (`cli.py`): Command-line interface
   - Click-based commands
   - Async execution
   - Progress reporting

## Dependencies

- **aiohttp**: Async HTTP requests
- **aiofiles**: Async file I/O
- **beautifulsoup4**: HTML parsing
- **lxml**: Fast XML/HTML parser
- **sentence-transformers**: Semantic embeddings
- **hdbscan**: Density-based clustering
- **numpy**: Numerical operations
- **scikit-learn**: ML utilities
- **tqdm**: Progress bars
- **click**: CLI framework

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Target Forum

This tool scrapes: https://forum.malighting.com/forum/board/35-grandma2-macro-share/

## Notes

- The scraper includes delays between requests to be respectful to the server
- Large forums may take significant time to scrape fully
- Clustering requires sufficient memory for embedding generation
- The manifest enables efficient delta updates for scheduled scraping
