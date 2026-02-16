"""
Web scraper module for competitor tracking
Handles fetching and parsing competitor websites

Improvements:
- DOM cleaning: removes non-content tags before extraction
- Text normalization: consistent text for reliable hashing
- Stable hashing: uses structured data for pricing/features pages
- Better change detection: unified diff summaries
- Duplicate avoidance: skips saving unchanged snapshots
- Robust requests: retries with exponential backoff
- Multithreading: parallel page scraping with ThreadPoolExecutor
"""

import re
import json
import hashlib
import time
import yaml
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from difflib import unified_diff
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import CompetitorDB
from extractors import extract_pricing, extract_features


class CompetitorScraper:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.db = CompetitorDB()
        self.timeout = self.config['scraping']['timeout']

        # ── Robust requests session with retry logic ──
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            'User-Agent': self.config['scraping']['user_agent']
        })

    # ── DOM Cleaning ─────────────────────────────────────────────
    def clean_dom(self, soup):
        """
        Remove non-content tags from the DOM tree so they don't
        pollute the extracted text or hashing.
        Removes: script, style, nav, footer, header, noscript, svg
        """
        tags_to_remove = ["script", "style", "nav", "footer", "header", "noscript", "svg"]
        for tag_name in tags_to_remove:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        return soup

    # ── Text Normalization ───────────────────────────────────────
    def normalize_text(self, text):
        """
        Normalize text for consistent comparison and hashing:
        - lowercase
        - strip leading/trailing whitespace
        - collapse multiple spaces into one
        - remove blank lines
        """
        text = text.lower().strip()
        text = re.sub(r'[ \t]+', ' ', text)            # collapse spaces/tabs
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]         # drop empty lines
        return '\n'.join(lines)

    # ── Fetch a page ─────────────────────────────────────────────
    def fetch_page(self, url):
        """Fetch a web page using the retry-enabled session."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {str(e)}")
            return None

    # ── Extract content with DOM cleaning ────────────────────────
    def extract_content(self, html, selector):
        """
        Extract text content from HTML.
        Cleans the DOM first, then applies the optional CSS selector.
        """
        soup = BeautifulSoup(html, 'html.parser')
        soup = self.clean_dom(soup)

        if selector:
            elements = soup.select(selector)
            if elements:
                content = '\n\n'.join(
                    [elem.get_text(strip=True, separator='\n') for elem in elements]
                )
            else:
                content = soup.get_text(strip=True, separator='\n')
        else:
            content = soup.get_text(strip=True, separator='\n')

        return content.strip()

    # ── Stable Hashing ───────────────────────────────────────────
    def calculate_hash(self, content, page_type=None, raw_html=None):
        """
        Calculate a stable hash of the page content.

        For pricing/features pages:
            Extract structured data → JSON serialize (sorted keys) → hash.
            This makes the hash immune to cosmetic HTML changes.

        For other pages:
            Normalize the text → hash.
        """
        if page_type in ("pricing", "features") and raw_html:
            try:
                if page_type == "pricing":
                    structured = extract_pricing(raw_html)
                else:
                    structured = extract_features(raw_html)

                canonical = json.dumps(structured, sort_keys=True, ensure_ascii=False)
                return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
            except Exception:
                pass  # fall through to plain-text hash

        normalized = self.normalize_text(content)
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    @staticmethod
    def _build_change_summary(diff: list[str], added: int, removed: int) -> str:  # noqa
        """Build a compact change summary string from diff data."""
        summary_parts: list[str] = []
        if added:
            summary_parts.append("+" + str(added) + " lines")
        if removed:
            summary_parts.append("-" + str(removed) + " lines")

        result: str = ""
        if summary_parts:
            result = ", ".join(summary_parts)
        else:
            result = "Content modified"

        detail_lines: list[str] = []
        for _ln in diff:
            if len(detail_lines) >= 5:
                break
            is_change: bool = _ln.startswith('+') or _ln.startswith('-')
            is_header: bool = _ln.startswith('+++') or _ln.startswith('---')
            if is_change and not is_header:
                detail_lines.append(_ln.strip())

        if detail_lines:
            result = str(result) + " | " + " ".join(detail_lines)

        if len(result) > 500:
            result = str(result[:497]) + "..."  # type: ignore[index]

        return result

    # ── Better Change Detection (unified diff) ───────────────────
    def detect_changes(self, competitor_name, page_url, page_type, new_content, new_hash):
        """
        Compare new content with the previous snapshot.
        Uses unified_diff to produce a concise change summary.
        """
        previous = self.db.get_latest_snapshot(competitor_name, page_url)

        if previous is None:
            print(f"  → First snapshot for {competitor_name} - {page_type}")
            return False, None

        if previous['content_hash'] == new_hash:
            print(f"  → No changes for {competitor_name} - {page_type}")
            return False, None

        # ── Changes detected — build a unified diff summary ──
        print(f"  ✓ CHANGE DETECTED for {competitor_name} - {page_type}")

        old_lines = previous['content'].splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = list(unified_diff(
            old_lines, new_lines,
            fromfile="previous", tofile="current",
            lineterm="",
            n=1,  # 1 line of context for brevity
        ))

        # Count additions and removals
        added   = sum(1 for ln in diff if ln.startswith('+') and not ln.startswith('+++'))
        removed = sum(1 for ln in diff if ln.startswith('-') and not ln.startswith('---'))

        summary: str = self._build_change_summary(diff, added, removed)

        old_content_snippet: str = str(previous['content'][:1000])  # type: ignore[index]
        new_content_snippet: str = str(new_content[:1000])  # type: ignore[index]

        change_id = self.db.record_change(
            competitor_name=competitor_name,
            page_url=page_url,
            page_type=page_type,
            change_description=summary,
            old_content=old_content_snippet,
            new_content=new_content_snippet,
        )

        return True, change_id

    # ── Scrape a single page ─────────────────────────────────────
    def scrape_page(self, competitor_name, page_config):
        """Scrape one page: fetch → clean → normalize → hash → detect → save."""
        url = page_config['url']
        page_type = page_config['type']
        selector = page_config.get('selector')

        print(f"\nScraping {competitor_name} - {page_type}")
        print(f"  URL: {url}")

        response = self.fetch_page(url)
        if not response:
            return False

        raw_html = response.text

        # Extract and normalize content
        content = self.extract_content(raw_html, selector)
        content = self.normalize_text(content)

        # Stable hash (uses structured data for pricing/features)
        content_hash = self.calculate_hash(content, page_type=page_type, raw_html=raw_html)

        # Check for changes
        changed, change_id = self.detect_changes(
            competitor_name, url, page_type, content, content_hash
        )

        # ── Avoid duplicates: skip saving if hash matches last snapshot ──
        previous = self.db.get_latest_snapshot(competitor_name, url)
        if previous and previous['content_hash'] == content_hash:
            print(f"  → Skipping duplicate snapshot for {competitor_name} - {page_type}")
            return changed

        # Save new snapshot
        metadata = {
            'status_code': response.status_code,
            'content_length': len(content),
            'selector': selector,
        }

        self.db.save_snapshot(
            competitor_name=competitor_name,
            page_url=url,
            page_type=page_type,
            content_hash=content_hash,
            content=content,
            metadata=metadata,
        )

        return changed

    # ── Scrape all competitors (multithreaded) ───────────────────
    def scrape_all_competitors(self):
        """
        Scrape all configured competitors using a thread pool.
        Pages are scraped in parallel (max 5 threads).
        """
        print(f"\n{'='*60}")
        print(f"Starting competitor scraping at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        # Build a flat list of (competitor_name, page_config) tasks
        tasks = []
        for competitor in self.config['competitors']:
            competitor_name = competitor['name']
            for page in competitor['pages']:
                tasks.append((competitor_name, page))

        total_changes = 0

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.scrape_page, name, page): (name, page)  # type: ignore[arg-type]
                for name, page in tasks
            }

            for future in as_completed(futures):
                name, page = futures[future]
                try:
                    changed = future.result()
                    if changed:
                        total_changes += 1
                except Exception as e:
                    print(f"  ✗ Error scraping {name} - {page.get('type', '?')}: {e}")

        print(f"\n{'='*60}")
        print(f"Scraping completed. {total_changes} changes detected.")
        print(f"{'='*60}\n")

        return total_changes

    # ── Generate report ──────────────────────────────────────────
    def generate_report(self, days: int = 7) -> str:
        """Generate a text report of recent changes."""
        changes = self.db.get_recent_changes(days=days)

        if not changes:
            return f"No changes detected in the last {days} days."

        lines: list[str] = [
            "COMPETITOR INTELLIGENCE REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Period: Last {days} days",
            "=" * 60,
            "",
        ]

        by_competitor: dict[str, list[dict[str, str]]] = {}
        for change in changes:
            comp_name: str = change['competitor_name']
            if comp_name not in by_competitor:
                by_competitor[comp_name] = []
            by_competitor[comp_name].append(change)

        for competitor, comp_changes in by_competitor.items():
            lines.append(competitor)
            lines.append("-" * len(competitor))

            for change in comp_changes:
                lines.append(f"  {change['page_type'].upper()}: {change['change_description']}")
                lines.append(f"  URL: {change['page_url']}")
                lines.append(f"  Detected: {change['detected_at']}")
                lines.append("")

            lines.append("")

        lines.append("=" * 60)
        lines.append(f"Total changes: {len(changes)}")

        return "\n".join(lines)


if __name__ == "__main__":
    scraper = CompetitorScraper()
    scraper.scrape_all_competitors()
