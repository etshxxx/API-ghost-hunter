# API Ghost Hunter

<p align="center">
  <b>Discover, diff, and hunt ghost API endpoints for bug bounty hunting</b>
</p>

---

## Overview

**API Ghost Hunter** is a Python-based bug bounty tool that helps security researchers discover **ghost API endpoints** — old API endpoints that developers forgot to delete or forgot to protect with authorization when updating their API.

### The Problem

When developers update their API:

- They add **new** endpoints to the documentation
- They **remove** old endpoints from the documentation
- But they sometimes **forget to delete** the old endpoint code on the server
- Or they **forget to add authorization** to endpoints that need it

These forgotten endpoints are **ghost endpoints** — they still work but are no longer documented, making them prime targets for security vulnerabilities.

### How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  Scan Target │────▶│  Save Snapshot│────▶│  Compare    │────▶│  Probe Ghosts │
│  (OpenAPI)   │     │  (JSON file)  │     │  Snapshots  │     │  (HTTP probe) │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
                                                │                      │
                                                ▼                      ▼
                                         Added / Removed        Alive? Auth Bypass?
                                         Modified / Unchanged
```

1. **Scan** a target's API documentation (OpenAPI/Swagger spec) and save a snapshot
2. **Archive** — query the Wayback Machine for historical API specs and create snapshots from archived versions
3. **Compare** snapshots from different points in time (current vs. previous, or current vs. archived)
4. **Identify** endpoints that were removed from the docs
5. **Probe** those removed endpoints to see if they're still alive (ghosts!)
6. **Detect** authorization bypass on ghost endpoints

---

## Features

- **Auto-discovery** of OpenAPI/Swagger specs (tries 60+ common paths)
- **Wayback Machine integration** — fetch archived API specs from the Internet Archive to find old endpoints
- **Snapshot management** — save and compare API endpoint states over time
- **Deep diffing** — detects added, removed, modified, and unchanged endpoints
- **Ghost endpoint hunting** — probes removed endpoints to check if they still respond
- **Authorization bypass detection** — checks if auth-required endpoints respond without auth
- **Dual-probe authentication** — probe with and without auth headers to compare responses
- **Response snippet capture** — records first 500 characters of ghost endpoint responses
- **JavaScript scanning** — extracts API endpoints from JS files (fetch, axios, XMLHttpRequest)
- **Proxy support** — route all requests through HTTP/HTTPS proxies
- **Custom headers** — send custom headers via JSON string or file
- **Rate limiting** — configurable delay between requests to avoid overwhelming targets
- **Multiple report formats** — console (rich tables), JSON, HTML, and Markdown
- **Dark-themed HTML reports** with color-coded HTTP methods and response snippets

---

## Installation

### From Source

```bash
git clone https://github.com/yourusername/api-ghost-hunter.git
cd api-ghost-hunter
pip install -r requirements.txt
pip install -e .
```

### Direct Usage (without install)

```bash
git clone https://github.com/yourusername/api-ghost-hunter.git
cd api-ghost-hunter
pip install -r requirements.txt
python -m api_ghost_hunter --help
```

### Quick Alias

The tool installs two console commands:

- `api-ghost-hunter` — full name
- `agh` — short alias

---

## Quick Start

### Step 1: Scan a target (first snapshot)

```bash
# Auto-discover the API spec
api-ghost-hunter scan https://example.com

# Or specify the spec URL directly
api-ghost-hunter scan https://example.com --spec-url https://example.com/api/swagger.json

# Also scan JavaScript files for additional endpoints
api-ghost-hunter scan https://example.com --scan-js

# Use a proxy and custom headers
api-ghost-hunter scan https://example.com --proxy http://127.0.0.1:8080 --headers '{"X-Custom":"value"}'
```

### Step 2: Search the Wayback Machine for archived specs

```bash
# Find and save archived API specs from the Wayback Machine
api-ghost-hunter archive https://example.com

# Specify a known spec URL to search for in archives
api-ghost-hunter archive https://example.com --spec-url https://example.com/openapi.json

# Filter by date range
api-ghost-hunter archive https://example.com --from-date 20230101 --to-date 20251231
```

### Step 3: Wait for the API to change (or scan immediately if you have an old spec)

```bash
# Scan again later to create a second snapshot
api-ghost-hunter scan https://example.com
```

### Step 4: Hunt for ghosts

```bash
# Full hunt: scan + compare with previous + probe removed endpoints + check archives
api-ghost-hunter hunt https://example.com --probe --check-archives

# Just compare two specific snapshots
api-ghost-hunter diff snapshots/example.com_2026-01-01T10-00-00.json snapshots/example.com_2026-01-15T10-00-00.json --probe

# Find ghosts from existing snapshots
api-ghost-hunter ghosts https://example.com
```

### Step 5: Generate reports

```bash
# Generate all report formats
api-ghost-hunter hunt https://example.com --probe --report-format all

# Generate HTML report only
api-ghost-hunter diff old.json new.json --format html -o report.html

# Generate JSON report
api-ghost-hunter ghosts https://example.com --report-format json -o ghosts.json
```

---

## Commands Reference

### `scan` — Scan a target and create a snapshot

```bash
api-ghost-hunter scan TARGET [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-s, --spec-url URL` | Direct URL to OpenAPI/Swagger spec |
| `--scan-js` | Also scan JavaScript files for endpoints |
| `-o, --output-dir DIR` | Directory to save snapshots (default: `snapshots`) |
| `--headers HEADERS` | Custom headers as JSON string or file path |

**Example:**
```bash
api-ghost-hunter scan https://api.example.com --spec-url https://api.example.com/v3/openapi.json --scan-js
```

### `list` — List all saved snapshots

```bash
api-ghost-hunter list [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-d, --snapshot-dir DIR` | Snapshot directory (default: `snapshots`) |
| `-t, --target URL` | Filter by target URL |

**Example:**
```bash
api-ghost-hunter list --target example.com
```

### `diff` — Compare two snapshots

```bash
api-ghost-hunter diff OLD_SNAPSHOT NEW_SNAPSHOT [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-f, --format FORMAT` | Output format: `console`, `json`, `html`, `markdown`, `all` |
| `-o, --output FILE` | Output file path |
| `--probe` | Probe removed endpoints to find ghosts |
| `--auth-header HEADER` | Auth header for probing (e.g. `Authorization: Bearer token`) |
| `--delay SECONDS` | Delay between probes (default: 0.5) |

**Example:**
```bash
api-ghost-hunter diff snapshots/old.json snapshots/new.json --format html -o report.html --probe
```

### `hunt` — Full hunt (scan + diff + probe + optional archive check)

```bash
api-ghost-hunter hunt TARGET [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-s, --spec-url URL` | Direct URL to OpenAPI/Swagger spec |
| `--scan-js` | Also scan JavaScript files |
| `--probe` | Probe removed endpoints to find ghosts |
| `--check-archives` | Also check Wayback Machine for old API specs |
| `--auth-header HEADER` | Auth header for probing (e.g. `Authorization: Bearer token`) |
| `--headers HEADERS` | Custom headers as JSON string or file path |
| `-f, --report-format FORMAT` | Report format: `console`, `json`, `html`, `markdown`, `all` |
| `-o, --output FILE` | Output file path |
| `-d, --snapshot-dir DIR` | Snapshot directory |
| `--delay SECONDS` | Delay between probes (default: 0.5) |

**Example:**
```bash
api-ghost-hunter hunt https://example.com --probe --check-archives --scan-js --report-format all -o hunt_report
```

### `ghosts` — Find and probe ghost endpoints

```bash
api-ghost-hunter ghosts TARGET [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-f, --report-format FORMAT` | Report format: `console`, `json`, `html`, `markdown`, `all` |
| `-o, --output FILE` | Output file path |
| `-d, --snapshot-dir DIR` | Snapshot directory |
| `--auth-header HEADER` | Auth header for probing (e.g. `Authorization: Bearer token`) |
| `--delay SECONDS` | Delay between probes (default: 0.5) |

**Example:**
```bash
api-ghost-hunter ghosts https://example.com --report-format json -o ghost_report.json
```

### `archive` — Search the Wayback Machine for archived API specs

```bash
api-ghost-hunter archive TARGET [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-s, --spec-url URL` | Direct URL to spec (uses this URL for archive search) |
| `-o, --output-dir DIR` | Directory to save snapshots (default: `snapshots`) |
| `--from-date YYYYMMDD` | Start date for Wayback Machine search |
| `--to-date YYYYMMDD` | End date for Wayback Machine search |
| `--limit N` | Max archived versions to fetch per URL (default: 50) |

**Example:**
```bash
api-ghost-hunter archive https://example.com --from-date 20230101 --to-date 20251231 --limit 100
```

### Global Options

These options can be passed before any command:

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Enable verbose (debug) output |
| `-t, --timeout SECONDS` | Request timeout (default: 15) |
| `--no-verify-ssl` | Disable SSL certificate verification |
| `--proxy URL` | HTTP/HTTPS proxy URL (e.g. `http://127.0.0.1:8080`) |
| `-h, --help` | Show help |
| `--version` | Show version |

---

## Wayback Machine Integration

The `archive` command and `--check-archives` flag use the [Wayback Machine CDX API](https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server) to find historical snapshots of API specification files.

### How It Works

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Query CDX API   │────▶│  Fetch Archived  │────▶│  Parse & Save    │
│  for spec URLs   │     │  Spec Content    │     │  Snapshots       │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

1. The archiver queries the CDX API for all common spec paths (`/openapi.json`, `/swagger.json`, etc.)
2. For each archived version found, it fetches the actual content from `web.archive.org`
3. The content is parsed as JSON or YAML OpenAPI/Swagger spec
4. Valid specs are converted to snapshots with an `archive_timestamp`
5. These snapshots can be diffed against the current API to find removed endpoints

### Use Case: Finding Endpoints Removed Long Ago

```bash
# Step 1: Find archived specs from the past
api-ghost-hunter archive https://target.com --from-date 20220101 --to-date 20231231

# Step 2: Scan the current API
api-ghost-hunter scan https://target.com

# Step 3: Diff the oldest archive snapshot with the current one
api-ghost-hunter list --target target.com
api-ghost-hunter diff snapshots/old_archive.json snapshots/current.json --probe
```

### Use Case: All-in-One Hunt

```bash
# Scan + check archives + diff + probe in one command
api-ghost-hunter hunt https://target.com --probe --check-archives --report-format all -o full_report
```

---

## Use Cases

### Bug Bounty Hunting

1. **Baseline scan** — Scan the target's API when you start the bounty
2. **Archive search** — Use the Wayback Machine to find old API specs from months or years ago
3. **Monitor for changes** — Re-scan periodically (weekly/monthly)
4. **Hunt ghosts** — When endpoints disappear from the docs, probe them:
   - Still alive? -> Potential **IDOR** or **information disclosure**
   - Auth bypass? -> Potential **broken access control**
   - Deprecated but alive? -> Potential **unpatched vulnerabilities**

### API Security Auditing

1. **Track API changes** over time
2. **Identify deprecated endpoints** that should be removed
3. **Find authorization gaps** in the API
4. **Compare API versions** (v1 vs. v2) for leftover endpoints

### Development Teams

1. **Catch leftover endpoints** from old API versions
2. **Verify authorization** is properly applied
3. **Track API evolution** with snapshot history

---

## Report Formats

### Console Output

Rich, color-coded tables in your terminal with:
- Summary of changes (added/removed/modified/unchanged)
- Full endpoint details with auth status
- Ghost probing results with auth bypass detection
- Response snippets from alive ghost endpoints
- Archive timestamp display for Wayback Machine snapshots

### JSON Report

Machine-readable JSON with full endpoint details, diff results, and ghost probing data including response snippets and auth probe results.

### HTML Report

Dark-themed, standalone HTML file with:
- Summary cards (added/removed/modified/unchanged)
- Color-coded HTTP methods (GET=green, POST=orange, DELETE=red, etc.)
- Ghost endpoint highlighting (red for removed, green for alive)
- Response snippet column for ghost endpoints
- Archive timestamp info for Wayback Machine snapshots

### Markdown Report

GitHub-flavored Markdown for easy inclusion in issues, PRs, or documentation. Includes response snippets for alive ghost endpoints.

---

## How Ghost Endpoints Work

```
Time T1: API has endpoints A, B, C, D (all documented)
                    │
                    │  Developer updates API
                    │  Removes B and C from docs
                    │  But forgets to delete B and C on the server
                    ▼
Time T2: API has endpoints A, D, E (documented)
         Endpoints B, C still work but are NOT documented = GHOSTS!

API Ghost Hunter:
  1. Scans T1 snapshot -> [A, B, C, D]
  2. Scans T2 snapshot -> [A, D, E]
  3. Diffs them -> Removed: [B, C]  Added: [E]
  4. Probes B and C -> Still alive? Auth bypass?
  5. Reports ghosts!
```

### With Wayback Machine

```
Time T0 (archived): API had endpoints A, B, C, D, E, F (archived on Wayback Machine)
                              │
                              │  Developer removed B, C, E, F from docs over time
                              │  But forgot to delete server code
                              ▼
Time T1 (current): API has endpoints A, D (documented)
                   Endpoints B, C, E, F still work = GHOSTS!

API Ghost Hunter:
  1. Archives T0 from Wayback Machine -> [A, B, C, D, E, F]
  2. Scans T1 current -> [A, D]
  3. Diffs them -> Removed: [B, C, E, F]
  4. Probes B, C, E, F -> Still alive? Auth bypass?
  5. Reports ghosts!
```

---

## Project Structure

```
api-ghost-hunter/
├── README.md                  # This file
├── LICENSE                    # MIT License
├── requirements.txt           # Python dependencies
├── setup.py                   # Package setup
├── .gitignore                 # Git ignore rules
├── api_ghost_hunter/          # Main package
│   ├── __init__.py            # Package init
│   ├── __main__.py            # Entry point (python -m api_ghost_hunter)
│   ├── cli.py                 # Click-based CLI commands
│   ├── models.py              # Data models (Endpoint, Snapshot, DiffResult, GhostEndpoint)
│   ├── fetcher.py             # HTTP fetcher & spec discovery (60+ paths)
│   ├── parser.py              # OpenAPI/Swagger & JS endpoint parser
│   ├── snapshot.py            # Snapshot save/load/list management
│   ├── differ.py              # Snapshot comparison engine
│   ├── analyzer.py            # Ghost endpoint prober & auth bypass detector
│   ├── archiver.py            # Wayback Machine CDX API integration
│   ├── reporter.py            # Console/JSON/HTML/Markdown report generator
│   └── utils.py               # Utility functions (headers, timestamps, URLs)
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── test_models.py         # Data model tests
│   ├── test_differ.py         # Diff engine tests
│   ├── test_parser.py         # OpenAPI & JS parser tests
│   └── test_archiver.py       # Wayback Machine archiver tests (mocked)
└── examples/                  # Example files
    └── sample_openapi.json    # Sample OpenAPI spec for testing
```

---

## Examples

### Example 1: Monitoring a target over time

```bash
# Day 1: First scan
api-ghost-hunter scan https://target.com

# Day 30: Second scan
api-ghost-hunter scan https://target.com

# Day 30: Compare and hunt ghosts
api-ghost-hunter ghosts https://target.com --report-format all -o day30_report
```

### Example 2: Using Wayback Machine to find old endpoints

```bash
# Search for archived API specs from 2023
api-ghost-hunter archive https://target.com --from-date 20230101 --to-date 20231231

# Scan current API
api-ghost-hunter scan https://target.com

# List all snapshots (current + archived)
api-ghost-hunter list --target target.com

# Diff oldest archive with current and probe ghosts
api-ghost-hunter diff snapshots/target_com_archive.json snapshots/target_com_current.json --probe --auth-header "Authorization: Bearer <token>"
```

### Example 3: Comparing two specific spec URLs

```bash
# Scan old API version
api-ghost-hunter scan https://api.target.com --spec-url https://api.target.com/v1/swagger.json -o snapshots/v1

# Scan new API version
api-ghost-hunter scan https://api.target.com --spec-url https://api.target.com/v2/openapi.json -o snapshots/v2

# Compare
api-ghost-hunter diff snapshots/v1/old.json snapshots/v2/new.json --format html -o api_diff.html
```

### Example 4: Full hunt with JS scanning, probing, and archive checking

```bash
api-ghost-hunter hunt https://target.com \
  --scan-js \
  --probe \
  --check-archives \
  --report-format all \
  -o full_hunt_report \
  --no-verify-ssl \
  --timeout 30 \
  --proxy http://127.0.0.1:8080
```

### Example 5: Using custom headers from a file

```bash
# Create a headers file
echo '{"X-API-Key": "your-key", "X-Custom-Header": "value"}' > headers.json

# Scan with custom headers
api-ghost-hunter scan https://target.com --headers headers.json
```

---

## Running Tests

```bash
# Install test dependencies
pip install pytest

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_models.py -v

# Run with coverage (optional)
pip install pytest-cov
pytest tests/ --cov=api_ghost_hunter --cov-report=term-missing
```

---

## Disclaimer

This tool is designed for **authorized security testing and bug bounty hunting only**. Always ensure you have proper authorization before scanning any target. The authors are not responsible for any misuse of this tool.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

<p align="center">
  Made for the bug bounty community
</p>
