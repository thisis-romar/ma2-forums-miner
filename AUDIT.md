# Security & Code Audit Report

**Repository:** `thisis-romar/ma2-forums-miner`
**Date:** 2026-02-10
**Scope:** Full codebase audit covering security, code quality, dependencies, CI/CD, testing, and robustness.

---

## Executive Summary

MA2 Forums Miner is an async web scraper for the MA Lighting grandMA2 Macro Share forum. The codebase is well-structured with clean separation of concerns and good use of modern Python async patterns. However, the audit identified **3 critical**, **5 high**, **8 medium**, and **6 low** severity issues ranging from a path traversal vulnerability and SSRF potential to bloated dependencies, missing tests, and CI misconfigurations.

---

## Findings by Severity

### CRITICAL

#### C1. Path Traversal in Asset Downloads

**File:** `src/ma2_forums_miner/scraper.py:784`

```python
file_path = folder / asset.filename
```

The `asset.filename` is extracted directly from forum HTML (lines 712-717) and used to construct a file path without sanitization. A malicious or crafted attachment filename like `../../etc/cron.d/backdoor` or `../../../.bashrc` could write files outside the intended output directory.

**Impact:** Arbitrary file write on the host filesystem.

**Recommendation:** Sanitize filenames by stripping path separators and resolving to ensure the final path is within the target directory:
```python
from pathlib import PurePosixPath
safe_name = PurePosixPath(asset.filename).name  # strips all directory components
file_path = folder / safe_name
assert file_path.resolve().is_relative_to(folder.resolve())
```

---

#### C2. No Download Size Limit

**File:** `src/ma2_forums_miner/scraper.py:774-797`

Downloaded files are written entirely to disk with no size limit:
```python
response = await self.client.get(asset.url, ...)
file_path.write_bytes(response.content)
```

A crafted or compromised attachment could be arbitrarily large, causing disk exhaustion. This is especially dangerous in the GitHub Actions CI environment where disk is limited.

**Impact:** Denial of service via disk exhaustion.

**Recommendation:** Add a `MAX_DOWNLOAD_SIZE` constant (e.g., 50 MB) and stream the download with size checking:
```python
MAX_DOWNLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
# Use streaming to check size before writing
```

---

#### C3. Broken Test File

**File:** `test_thread_20248.py:32`

```python
metadata = await scraper.scrape_thread(thread_url)
```

`ForumScraper` has no method called `scrape_thread`. The correct method name is `fetch_thread`. Additionally, this test creates a `ForumScraper()` instance but never initializes `self.client` (which is set to `None` in `__init__` and only created in `run()`), so even with the correct method name, it would crash with `AttributeError: 'NoneType' object has no attribute 'get'`.

**Impact:** The test script is non-functional and provides no validation.

---

### HIGH

#### H1. SSRF Potential via Unvalidated URLs

**Files:** `src/ma2_forums_miner/scraper.py:396, 721, 774`

URLs extracted from forum HTML via `urljoin(BASE_URL, href)` are fetched without validating that they point to the expected domain. If the forum HTML contained a link like `href="http://169.254.169.254/latest/meta-data/"` (AWS metadata endpoint) or an internal network address, the scraper would follow it.

In `download_asset`, `asset.url` is fetched with `follow_redirects=True`, which means even a legitimate-looking URL could redirect to an internal resource.

**Impact:** Server-Side Request Forgery (SSRF), potential credential leakage in cloud environments.

**Recommendation:** Validate all URLs against an allowlist of expected domains before fetching:
```python
from urllib.parse import urlparse
ALLOWED_DOMAINS = {"forum.malighting.com"}

def _validate_url(self, url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname in ALLOWED_DOMAINS
```

---

#### H2. Bloated Dependencies

**File:** `requirements.txt:17-24`

The requirements file includes 7 unused dependencies:

| Package | Size Impact | Used? |
|---------|-------------|-------|
| `aiohttp>=3.13.3` | ~5 MB | No - legacy |
| `aiofiles>=23.2.1` | ~50 KB | No - not imported |
| `sentence-transformers>=2.2.0` | ~2 GB (pulls PyTorch) | No - Phase 2 |
| `hdbscan>=0.8.33` | ~20 MB | No - Phase 2 |
| `numpy>=1.24.0` | ~30 MB | No - not imported |
| `scikit-learn>=1.3.0` | ~30 MB | No - not imported |
| `click>=8.1.0` | ~200 KB | No - not imported |

**Impact:**
- CI install time increased by minutes due to PyTorch download
- Attack surface expanded by thousands of transitive dependencies
- `sentence-transformers` pulls in `torch`, `transformers`, `tokenizers`, etc.

**Recommendation:** Remove unused dependencies from `requirements.txt`. Create a separate `requirements-ml.txt` for Phase 2 if needed.

---

#### H3. No Automated Test Suite

The project has zero automated tests:
- `test_thread_20248.py` is broken (see C3)
- `test_pagination.py` is a manual diagnostic tool, not an automated test
- CI installs `pytest` but runs no tests
- No unit tests for `models.py`, `utils.py`, or scraper methods
- All "tests" require live network access to the forum

**Impact:** Regressions, broken code, and bugs (like C3) go undetected.

**Recommendation:** Add a proper test suite with:
- Unit tests for `safe_thread_folder()`, `sha256_file()`, data models
- Mocked HTTP tests for scraper methods using `respx` or `pytest-httpx`
- Place tests in a `tests/` directory and run in CI

---

#### H4. CI Lint Step Silenced

**File:** `.github/workflows/ci.yml:35`

```yaml
pylint src/ma2_forums_miner --disable=C0114,C0115,C0116 || true
```

The `|| true` means pylint errors are always ignored and the step always passes. The lint check provides zero enforcement value.

**Impact:** Code quality issues and potential bugs flagged by pylint are silently ignored.

**Recommendation:** Remove `|| true` and fix any pylint errors, or set a minimum score threshold:
```yaml
pylint src/ma2_forums_miner --disable=C0114,C0115,C0116 --fail-under=8.0
```

---

#### H5. Manifest Corruption Risk (Non-Atomic Writes)

**File:** `src/ma2_forums_miner/scraper.py:167-177`

```python
self.manifest_file.write_bytes(
    orjson.dumps(data, option=orjson.OPT_INDENT_2)
)
```

If the process is killed during `write_bytes()`, the manifest file could be truncated or corrupted. Since the manifest is the sole record of which threads have been scraped, corruption means either lost progress or duplicate work.

**Impact:** Data loss on interruption.

**Recommendation:** Use atomic write pattern (write to temp file, then rename):
```python
import tempfile
tmp = self.manifest_file.with_suffix('.tmp')
tmp.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
tmp.rename(self.manifest_file)
```

---

### MEDIUM

#### M1. Unused Import

**File:** `src/ma2_forums_miner/scraper.py:15`

```python
import json
```

The `json` module is imported but never used. All JSON operations use `orjson`.

---

#### M2. Rate Limit Sleep Holds Semaphore

**File:** `src/ma2_forums_miner/scraper.py:216-253`

The `await asyncio.sleep(self.request_delay)` on line 251 executes inside `async with self.semaphore`, holding a semaphore slot during the 1.5-second sleep. With 8 slots and 1.5s delay each, effective concurrency is significantly reduced.

**Recommendation:** Move the rate-limiting sleep outside the semaphore, or use a separate rate-limiting mechanism (e.g., a token bucket).

---

#### M3. Sequential Thread Processing

**File:** `src/ma2_forums_miner/scraper.py:991`

```python
for url in new_threads:
    success = await self.process_thread(url)
```

Despite having full async infrastructure with semaphores, threads are processed one at a time. Only page discovery uses `asyncio.gather()` for concurrency. Processing 600+ threads sequentially with a 1.5s delay per request means the scraper runs much slower than necessary.

**Recommendation:** Use `asyncio.gather()` or `asyncio.Semaphore`-controlled concurrent processing for threads as well, similar to how page fetching works.

---

#### M4. HTTP 5xx Errors Not Retried

**File:** `src/ma2_forums_miner/scraper.py:255-257`

```python
except httpx.HTTPStatusError as e:
    print(f"... HTTP error for {url}: {e}")
    return None
```

Only HTTP 429 (rate limit) and network-level `RequestError` trigger retries. Server errors (500, 502, 503, 504) immediately return `None` without retry. These transient errors are common and should be retried.

---

#### M5. Division by Zero in Statistics Generator

**File:** `generate_stats.py:154`

```python
stats['threads_with_attachments']/stats['total_threads']*100
```

If `total_threads` is 0 (e.g., empty output directory), this raises `ZeroDivisionError`.

---

#### M6. Python Version Mismatch

- `setup.py` declares `python_requires=">=3.8"`
- CI uses Python 3.10 and 3.11
- Python 3.8 reached End of Life in October 2024

**Recommendation:** Update to `python_requires=">=3.10"` to match actual CI usage and drop unsupported Python versions.

---

#### M7. No Dependency Pinning / Lock File

All dependencies use `>=` minimum bounds with no upper constraints. There is no `requirements.lock`, `pip freeze`, or equivalent for reproducible builds. A new release of any dependency could break the build at any time.

**Recommendation:** Pin exact versions in a lock file or use version ranges with upper bounds.

---

#### M8. Dangerous `git add -A` in CI

**File:** `.github/workflows/ci.yml:88`

```yaml
git add -A
```

This stages all untracked files, which could accidentally commit temporary files, debug artifacts, or sensitive data generated during the scrape run. The `scrape.yml` workflow correctly uses `git add output/ manifest.json` instead.

**Recommendation:** Replace with explicit file paths:
```yaml
git add output/ manifest.json
```

---

### LOW

#### L1. Debug Print Statements in Production Code

**File:** `src/ma2_forums_miner/scraper.py:614, 678-695, 747`

Multiple `[DEBUG]` print statements are left in production code:
```python
print(f"    [DEBUG] Found {len(post_elements)} posts in thread")
print(f"    [DEBUG] Found {len(attachment_links)} attachment links")
```

**Recommendation:** Replace with proper `logging` module usage so debug output can be controlled via log levels.

---

#### L2. `Post` Model Not Exported

**File:** `src/ma2_forums_miner/__init__.py`

`__all__` exports `ThreadMetadata` and `Asset` but not `Post`, even though `Post` objects are nested inside `ThreadMetadata.posts`. External consumers would need to import directly from `models`.

---

#### L3. Incomplete Return Type Annotation

**File:** `src/ma2_forums_miner/scraper.py:589`

```python
def extract_all_posts(self, soup: BeautifulSoup) -> List:
```

Should be `-> List[Post]` for proper type safety.

---

#### L4. Legacy `setup.py` Format

The project uses the legacy `setup.py` format. Modern Python packaging recommends `pyproject.toml` (PEP 621).

---

#### L5. `continue-on-error` Hides Push Failures

**File:** `.github/workflows/scrape.yml:86`

```yaml
continue-on-error: true
```

This silences any git push failures, including authentication errors or branch protection violations.

---

#### L6. Hardcoded Page Fallback

**File:** `src/ma2_forums_miner/scraper.py:483`

```python
max_page = 30  # Try up to page 30 (confirmed via web structure)
```

If pagination detection fails, the scraper blindly tries 30 pages. This is wasteful if the forum has fewer pages and insufficient if it has more.

---

## Summary Table

| Severity | ID | Title | File |
|----------|----|-------|------|
| CRITICAL | C1 | Path traversal in asset downloads | scraper.py:784 |
| CRITICAL | C2 | No download size limit | scraper.py:774 |
| CRITICAL | C3 | Broken test file | test_thread_20248.py:32 |
| HIGH | H1 | SSRF via unvalidated URLs | scraper.py:396,721 |
| HIGH | H2 | Bloated unused dependencies | requirements.txt:17-24 |
| HIGH | H3 | No automated test suite | (project-wide) |
| HIGH | H4 | CI lint step silenced | ci.yml:35 |
| HIGH | H5 | Manifest corruption risk | scraper.py:167 |
| MEDIUM | M1 | Unused `json` import | scraper.py:15 |
| MEDIUM | M2 | Rate limit sleep holds semaphore | scraper.py:251 |
| MEDIUM | M3 | Sequential thread processing | scraper.py:991 |
| MEDIUM | M4 | HTTP 5xx not retried | scraper.py:255 |
| MEDIUM | M5 | Division by zero in stats | generate_stats.py:154 |
| MEDIUM | M6 | Python version mismatch | setup.py:17 |
| MEDIUM | M7 | No dependency pinning | requirements.txt |
| MEDIUM | M8 | Dangerous `git add -A` in CI | ci.yml:88 |
| LOW | L1 | Debug prints in production | scraper.py:614 |
| LOW | L2 | `Post` not exported | __init__.py |
| LOW | L3 | Incomplete type annotation | scraper.py:589 |
| LOW | L4 | Legacy `setup.py` format | setup.py |
| LOW | L5 | `continue-on-error` hides failures | scrape.yml:86 |
| LOW | L6 | Hardcoded page fallback | scraper.py:483 |

---

## Positive Observations

- **Clean architecture:** Good separation into models, scraper, and utils modules
- **No hardcoded secrets:** No API keys, passwords, or credentials in code
- **Graceful interruption handling:** `KeyboardInterrupt` preserves progress via manifest
- **Delta scraping:** Efficient incremental updates avoid redundant work
- **Exponential backoff:** Industry-standard pattern for rate limit handling
- **SHA256 checksums:** Download integrity verification is a strong practice
- **HTTP/2 support:** Good use of modern protocol for performance
- **Well-documented:** Extensive docstrings and comments throughout

---

## Recommended Priority Actions

1. **Fix C1 immediately** - Sanitize asset filenames before writing to disk
2. **Fix C2** - Add download size limits
3. **Fix H1** - Validate URLs against allowed domains
4. **Fix H2** - Remove unused dependencies from requirements.txt
5. **Fix H5** - Implement atomic manifest writes
6. **Fix C3 + H3** - Fix broken test and add proper test suite
7. **Fix H4 + M8** - Make CI meaningful (enforce lint, fix dangerous git add)
