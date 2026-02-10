# Security & Code Audit Report

**Repository:** `thisis-romar/ma2-forums-miner`
**Date:** 2026-02-10
**Scope:** Full audit covering codebase security, code quality, dependencies, CI/CD, testing, open PRs, and repository governance.

---

## Executive Summary

MA2 Forums Miner is an async web scraper for the MA Lighting grandMA2 Macro Share forum. The codebase on `main` is well-structured with clean separation of concerns and good use of modern Python async patterns. Two open PRs propose significant architectural changes (SQLite state management, adaptive throttling).

This audit identified **3 critical**, **5 high**, **8 medium**, and **6 low** severity issues on `main`, plus **3 critical** and **4 high** issues in PR #22, and **2 medium** issues in PR #21. Repository governance has significant gaps including no branch protection and 6 stale branches.

---

## Part 1: Codebase Audit (`main` Branch)

### CRITICAL

#### C1. Path Traversal in Asset Downloads

**File:** `src/ma2_forums_miner/scraper.py:784`

```python
file_path = folder / asset.filename
```

The `asset.filename` is extracted directly from forum HTML (lines 712-717) and used to construct a file path without sanitization. A crafted attachment filename like `../../etc/cron.d/backdoor` could write files outside the intended output directory.

**Impact:** Arbitrary file write on the host filesystem.

**Recommendation:** Sanitize filenames by stripping path separators and resolving to ensure the final path is within the target directory:
```python
from pathlib import PurePosixPath
safe_name = PurePosixPath(asset.filename).name  # strips directory components
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

A crafted or compromised attachment could be arbitrarily large, causing disk exhaustion -- especially dangerous in the GitHub Actions CI environment.

**Impact:** Denial of service via disk exhaustion.

**Recommendation:** Add a `MAX_DOWNLOAD_SIZE` constant (e.g., 50 MB) and use streaming with size checking.

---

#### C3. Broken Test File

**File:** `test_thread_20248.py:32`

```python
metadata = await scraper.scrape_thread(thread_url)
```

`ForumScraper` has no method called `scrape_thread` -- the correct name is `fetch_thread`. Additionally, `self.client` is never initialized (set to `None` in `__init__`, only created in `run()`), so even with the correct method name it would crash with `AttributeError`.

**Impact:** The test script is non-functional and provides no validation.

---

### HIGH

#### H1. SSRF Potential via Unvalidated URLs

**Files:** `src/ma2_forums_miner/scraper.py:396, 721, 774`

URLs extracted from forum HTML via `urljoin(BASE_URL, href)` are fetched without validating they point to the expected domain. If the forum HTML contained `href="http://169.254.169.254/latest/meta-data/"` (AWS metadata endpoint) or an internal address, the scraper would follow it. `follow_redirects=True` on downloads compounds the risk.

**Impact:** Server-Side Request Forgery (SSRF), potential credential leakage in cloud environments.

**Recommendation:** Validate all URLs against an allowlist before fetching:
```python
ALLOWED_DOMAINS = {"forum.malighting.com"}
```

---

#### H2. Bloated Dependencies

**File:** `requirements.txt:17-24`

7 unused dependencies are installed, including `sentence-transformers` which pulls in PyTorch (~2 GB):

| Package | Used? | Impact |
|---------|-------|--------|
| `aiohttp>=3.13.3` | No (legacy) | ~5 MB |
| `aiofiles>=23.2.1` | No | ~50 KB |
| `sentence-transformers>=2.2.0` | No (Phase 2) | ~2 GB |
| `hdbscan>=0.8.33` | No (Phase 2) | ~20 MB |
| `numpy>=1.24.0` | No | ~30 MB |
| `scikit-learn>=1.3.0` | No | ~30 MB |
| `click>=8.1.0` | No | ~200 KB |

**Impact:** Minutes added to CI installs, thousands of transitive dependencies expanding the attack surface.

**Recommendation:** Remove unused deps. Create a separate `requirements-ml.txt` for Phase 2.

---

#### H3. No Automated Test Suite

- `test_thread_20248.py` is broken (see C3)
- `test_pagination.py` is a manual diagnostic tool
- CI installs `pytest` but runs zero tests
- No unit tests for `models.py`, `utils.py`, or scraper methods
- All "tests" require live network access

**Impact:** Regressions and bugs (like C3) go undetected.

---

#### H4. CI Lint Step Silenced

**File:** `.github/workflows/ci.yml:35`

```yaml
pylint src/ma2_forums_miner --disable=C0114,C0115,C0116 || true
```

The `|| true` means pylint always passes. Zero enforcement value.

**Recommendation:** Remove `|| true` or set `--fail-under=8.0`.

---

#### H5. Manifest Corruption Risk (Non-Atomic Writes)

**File:** `src/ma2_forums_miner/scraper.py:167-177`

`write_bytes()` is not atomic. A process kill mid-write can truncate/corrupt the manifest -- the sole record of scraping progress.

**Recommendation:** Write-to-temp-then-rename pattern:
```python
tmp = self.manifest_file.with_suffix('.tmp')
tmp.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
tmp.rename(self.manifest_file)
```

---

### MEDIUM

| ID | Title | File | Details |
|----|-------|------|---------|
| M1 | Unused `json` import | `scraper.py:15` | `import json` never used; orjson handles all JSON |
| M2 | Rate limit sleep holds semaphore | `scraper.py:251` | `asyncio.sleep(1.5s)` inside semaphore reduces concurrency |
| M3 | Sequential thread processing | `scraper.py:991` | Threads processed one at a time despite async infrastructure |
| M4 | HTTP 5xx errors not retried | `scraper.py:255` | Only 429 and network errors trigger retry; 500/502/503 return None |
| M5 | Division by zero in stats | `generate_stats.py:154` | Crashes if output directory is empty |
| M6 | Python version mismatch | `setup.py:17` | Declares `>=3.8` (EOL Oct 2024); CI uses 3.10/3.11 |
| M7 | No dependency pinning | `requirements.txt` | All `>=` bounds, no lock file for reproducibility |
| M8 | Dangerous `git add -A` in CI | `ci.yml:88` | Stages all files; could commit debug artifacts or secrets |

### LOW

| ID | Title | File | Details |
|----|-------|------|---------|
| L1 | Debug prints in production | `scraper.py:614,688` | `[DEBUG]` print statements left in |
| L2 | `Post` model not exported | `__init__.py` | Missing from `__all__` despite being in public data |
| L3 | Incomplete return type | `scraper.py:589` | `-> List` should be `-> List[Post]` |
| L4 | Legacy `setup.py` format | `setup.py` | Modern Python uses `pyproject.toml` (PEP 621) |
| L5 | `continue-on-error` hides failures | `scrape.yml:86` | Silences git push errors |
| L6 | Hardcoded page fallback | `scraper.py:483` | Falls back to 30 pages if detection fails |

---

## Part 2: Open Pull Request Reviews

### PR #22 -- SQLite State Management (`copilot/implement-sqlalchemy-state-management`)

Proposes replacing `manifest.json` with SQLAlchemy-managed SQLite. Adds `StateManager` class, `ThreadState` ORM model, migration docs, and tests.

#### Findings

| Severity | ID | Title | Location |
|----------|-----|-------|----------|
| CRITICAL | PR22-C1 | SQLite + async thread safety | `state_manager.py:99-116` |
| CRITICAL | PR22-C2 | Missing field validation in `update_thread_state()` | `state_manager.py:171` |
| CRITICAL | PR22-C3 | Type annotation error (`any` vs `Any`) | `state_manager.py:142` |
| HIGH | PR22-H1 | DB path parent directories not created | `state_manager.py:97-104` |
| HIGH | PR22-H2 | Broad exception handling suppresses root cause | `state_manager.py:194-197` |
| HIGH | PR22-H3 | Detached SQLAlchemy instance returned from session | `state_manager.py:237-240` |
| HIGH | PR22-H4 | Process failure can diverge DB state from disk | `scraper.py:816-822` |
| MEDIUM | PR22-M1 | Sync DB calls block async event loop | `state_manager.py` (entire class) |
| MEDIUM | PR22-M2 | No input validation for `db_path` | `state_manager.py:87` |
| LOW | PR22-L1 | No string length constraints on columns | `state_manager.py:47-52` |
| LOW | PR22-L2 | Tests don't cover async/concurrent scenarios | test files |

**Key Concern -- SQLite + Async Concurrency (PR22-C1):**

The `StateManager` makes synchronous SQLite calls from async code without proper synchronization. No `check_same_thread=False`, no WAL mode, no connection pooling, no async-aware locking. Under concurrent scraping, this risks database corruption, lost updates, and intermittent crashes.

**Recommendation:** Either use `aiosqlite`/async DB driver, wrap calls in `asyncio.to_thread()`, or add explicit `asyncio.Lock` around all DB operations.

**Verdict:** Not ready to merge. The concurrency issue (PR22-C1) and missing validation (PR22-C2) must be resolved first.

---

### PR #21 -- Adaptive Throttling & Parser Resilience (`copilot/audit-data-pipeline-improvements`)

Proposes multi-level state tracking (ThreadState/PostState/AssetState), adaptive throttling via token bucket, and resilient CSS selector fallback chains. Adds telemetry, tests, and documentation.

#### Findings

| Severity | ID | Title | Location |
|----------|-----|-------|----------|
| MEDIUM | PR21-M1 | Data race in `ResponseStats` telemetry | `telemetry.py:ResponseStats` |
| MEDIUM | PR21-M2 | `ThreadState.needs_update()` ignores view changes silently | `models.py` |
| LOW | PR21-L1 | Print statements instead of logging module | Multiple files |
| LOW | PR21-L2 | Missing type hints on some internal methods | `scraper.py` |
| LOW | PR21-L3 | No error-path test coverage | test files |

**Strengths:**
- Excellent multi-level state tracking with SHA256 content hashing for edit detection
- Sophisticated token bucket + cool-off throttling with jitter
- Well-designed CSS selector fallback chains with optimization caching
- Clean migration path from legacy `manifest.json`
- Comprehensive telemetry (response stats, retry reasons, category breakdowns)
- Good test coverage for happy paths
- No security vulnerabilities identified

**Verdict:** Approved for merge with minor items. The `ResponseStats` data race (PR21-M1) should ideally use `asyncio.Lock` but impact is limited to telemetry accuracy, not data integrity.

---

## Part 3: Repository Governance

### Branch Hygiene

The repository has **11 branches** (including `main`), none of which are protected:

| Branch | Status | Commits Ahead | Action |
|--------|--------|---------------|--------|
| `main` | Default | -- | **Protect this branch** |
| `claude/fix-commit-push-error-s9dCP` | Merged | 0 | Delete |
| `claude/fix-deprecated-actions-s9dCP` | Merged | 0 | Delete |
| `claude/setup-github-actions-s9dCP` | Merged | 0 | Delete |
| `copilot/consolidate-to-ma2-forums-miner` | Merged | 0 | Delete |
| `copilot/complete-scraper-engine` | Merged | 0 | Delete |
| `copilot/build-async-cli-tool` | Merged | 0 | Delete |
| `fix/audit-align-architecture` | Merged | 0 | Delete |
| `copilot/audit-data-pipeline-improvements` | **Open (PR #21)** | 7 | Review & merge |
| `copilot/implement-sqlalchemy-state-management` | **Open (PR #22)** | 5 | Fix issues, then merge |
| `claude/audit-ma2-forums-miner-n2Chz` | **Open (this audit)** | 1 | Merge after review |

**6 stale merged branches** should be deleted immediately to reduce clutter.

### Branch Protection

**No branch protection rules** are configured on `main`. This means:
- Anyone with write access can push directly to `main`
- No required status checks (lint, test) before merging
- No required reviews for PRs
- Force pushes are not blocked

**Recommendation:** Enable branch protection on `main`:
- Require PR reviews (at least 1)
- Require status checks to pass (lint, test)
- Block force pushes
- Block direct pushes

### PR-to-Issue Alignment

PRs #21 and #22 are well-aligned with their corresponding issues. However:
- PRs #21 and #22 modify overlapping files (`scraper.py`, `.gitignore`) and cannot both merge cleanly -- merge order matters
- PR #21 is the stronger implementation; consider merging it first, then rebasing PR #22

### CI/CD Gaps

- `actions/setup-python@v4` is used in `ci.yml` (v5 is current)
- `ci.yml` import check (line 39) references `ma2_forums_miner` but the package path requires `PYTHONPATH=src` or `pip install -e .` -- likely fails silently
- No automated test execution in any workflow
- Scrape workflow has no failure alerting

---

## Summary Table (All Findings)

### Main Branch

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 3 | C1 (path traversal), C2 (no size limit), C3 (broken test) |
| HIGH | 5 | H1-H5 |
| MEDIUM | 8 | M1-M8 |
| LOW | 6 | L1-L6 |
| **Total** | **22** | |

### PR #22 (SQLite State Management)

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 3 | PR22-C1 (async safety), PR22-C2 (validation), PR22-C3 (type hint) |
| HIGH | 4 | PR22-H1 to PR22-H4 |
| MEDIUM | 2 | PR22-M1, PR22-M2 |
| LOW | 2 | PR22-L1, PR22-L2 |
| **Total** | **11** | |

### PR #21 (Adaptive Throttling & Resilience)

| Severity | Count | IDs |
|----------|-------|-----|
| MEDIUM | 2 | PR21-M1 (data race), PR21-M2 (logic clarity) |
| LOW | 3 | PR21-L1 to PR21-L3 |
| **Total** | **5** | |

### Repository Governance

| Issue | Severity |
|-------|----------|
| No branch protection on `main` | HIGH |
| 6 stale merged branches | MEDIUM |
| Outdated GitHub Actions versions | LOW |
| CI import check likely fails silently | MEDIUM |

---

## Positive Observations

- **Clean architecture:** Good separation into models, scraper, and utils modules
- **No hardcoded secrets:** No API keys, passwords, or credentials anywhere in the codebase
- **Graceful interruption handling:** `KeyboardInterrupt` preserves progress via manifest
- **Delta scraping:** Efficient incremental updates avoid redundant work
- **Exponential backoff:** Industry-standard pattern for rate limit handling
- **SHA256 checksums:** Download integrity verification is a strong practice
- **HTTP/2 support:** Good use of modern protocol for performance
- **Well-documented:** Extensive docstrings and inline comments throughout
- **PR #21 quality:** Multi-level state, token bucket throttling, and parser resilience are production-grade
- **Good PR-to-issue alignment:** Clear traceability between issues and proposed changes

---

## Recommended Priority Actions

### Immediate (Blocking)
1. **Fix C1** -- Sanitize asset filenames before writing to disk
2. **Fix C2** -- Add download size limits
3. **Fix H1** -- Validate URLs against allowed domains
4. **Protect `main` branch** -- Require PRs, status checks, and reviews

### Before Next Merge
5. **Fix H2** -- Remove unused dependencies from `requirements.txt`
6. **Fix H5** -- Implement atomic manifest writes
7. **Delete 6 stale branches** -- Clean up merged branches
8. **Fix PR22-C1** -- Resolve SQLite async concurrency before merging PR #22

### Short-Term
9. **Fix C3 + H3** -- Fix broken test and add real pytest suite
10. **Fix H4 + M8** -- Enforce lint, replace `git add -A` in CI
11. **Merge PR #21** -- Strong implementation, ready after minor fixes
12. **Update CI actions** -- `setup-python@v4` -> `v5`, fix import check path
