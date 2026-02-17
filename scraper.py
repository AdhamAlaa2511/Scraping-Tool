"""
SaaS Competitor Scraper
Tracks: Pricing & Plans, Features & Product Updates, Blog & Content
Output: Plain English change descriptions
"""

import re
import json
import hashlib
import yaml
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import CompetitorDB


class CompetitorScraper:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.db = CompetitorDB()
        self.timeout = self.config['scraping'].get('timeout', 30)

        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=1,
                      status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["GET"])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            'User-Agent': self.config['scraping'].get(
                'user_agent',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
        })

    # ─────────────────────────────────────────
    # FETCH
    # ─────────────────────────────────────────
    def fetch_page(self, url):
        try:
            r = self.session.get(url, timeout=self.timeout)
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Failed to fetch {url}: {e}")
            return None

    # ─────────────────────────────────────────
    # CLEAN HTML
    # ─────────────────────────────────────────
    def clean_soup(self, soup):
        """Remove noise tags that never contain useful competitor data."""
        for tag in soup.find_all(['script', 'style', 'nav', 'footer',
                                   'header', 'noscript', 'svg', 'iframe',
                                   'form', 'cookie-banner', 'aside']):
            tag.decompose()
        return soup

    # ─────────────────────────────────────────
    # PRICING EXTRACTOR
    # ─────────────────────────────────────────
    def extract_pricing_data(self, soup):
        """
        Extract structured pricing plans from a SaaS pricing page.
        Returns list of: {name, price, billing, features[]}
        """
        plans = []

        # Common pricing card patterns
        card_patterns = [
            re.compile(r'pric', re.I),
            re.compile(r'plan', re.I),
            re.compile(r'tier', re.I),
            re.compile(r'package', re.I),
        ]

        candidates = []
        for tag in soup.find_all(['div', 'section', 'article', 'li']):
            classes = ' '.join(tag.get('class', []))
            if any(p.search(classes) for p in card_patterns):
                # Skip if it's a wrapper containing many children that also match
                child_matches = sum(
                    1 for c in tag.find_all(['div', 'section'], recursive=False)
                    if any(p.search(' '.join(c.get('class', []))) for p in card_patterns)
                )
                if child_matches < 2:
                    candidates.append(tag)

        for card in candidates:
            plan = self._parse_plan_card(card)
            if plan.get('name') or plan.get('price'):
                plans.append(plan)

        # Deduplicate by (name, price)
        seen = set()
        unique = []
        for p in plans:
            key = (p.get('name', ''), p.get('price', ''))
            if key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    def _parse_plan_card(self, card):
        """Parse a single pricing card into structured data."""
        plan = {'name': None, 'price': None, 'billing': None, 'features': []}

        # Plan name: look for headings first
        for tag in card.find_all(['h1', 'h2', 'h3', 'h4', 'strong']):
            text = tag.get_text(strip=True)
            if text and len(text) < 60 and not self._looks_like_price(text):
                plan['name'] = text
                break

        # Price: find currency+number pattern
        price_re = re.compile(r'[\$€£¥]\s*[\d,]+(\.\d{2})?', re.I)
        free_re = re.compile(r'\bfree\b', re.I)

        # Check dedicated price element
        for cls in ['price', 'amount', 'cost', 'pricing__price', 'plan-price']:
            el = card.find(class_=re.compile(cls, re.I))
            if el:
                text = el.get_text(strip=True)
                m = price_re.search(text)
                if m:
                    plan['price'] = m.group(0).strip()
                    break
                if free_re.search(text):
                    plan['price'] = 'Free'
                    break

        # Fallback: scan all text
        if not plan['price']:
            for text in card.stripped_strings:
                m = price_re.search(text)
                if m:
                    plan['price'] = m.group(0).strip()
                    break
                if free_re.search(text) and len(text) < 20:
                    plan['price'] = 'Free'
                    break

        # Billing period
        billing_m = re.search(r'per\s*(month|year|mo|yr|user|seat)',
                               card.get_text(), re.I)
        if billing_m:
            period = billing_m.group(1).lower()
            plan['billing'] = 'monthly' if period in ('month', 'mo') else \
                              'yearly' if period in ('year', 'yr') else period

        # Features: list items
        for ul in card.find_all('ul'):
            for li in ul.find_all('li'):
                text = li.get_text(strip=True)
                if text and len(text) < 150:
                    plan['features'].append(text)

        return plan

    def _looks_like_price(self, text):
        return bool(re.search(r'[\$€£¥]\d|\d+\/mo|\bfree\b', text, re.I))

    # ─────────────────────────────────────────
    # FEATURES EXTRACTOR
    # ─────────────────────────────────────────
    def extract_features_data(self, soup):
        """
        Extract product features from a SaaS features/product page.
        Returns list of: {name, description}
        """
        features = []

        feature_patterns = [
            re.compile(r'feature', re.I),
            re.compile(r'benefit', re.I),
            re.compile(r'capability', re.I),
            re.compile(r'product.*card', re.I),
        ]

        candidates = []
        for tag in soup.find_all(['div', 'li', 'article']):
            classes = ' '.join(tag.get('class', []))
            if any(p.search(classes) for p in feature_patterns):
                candidates.append(tag)

        for item in candidates:
            title_el = item.find(['h2', 'h3', 'h4', 'strong'])
            desc_el = item.find('p')
            if title_el:
                name = title_el.get_text(strip=True)
                desc = desc_el.get_text(strip=True) if desc_el else ''
                if name and len(name) < 100:
                    features.append({'name': name, 'description': desc[:300]})

        # Deduplicate
        seen = set()
        unique = []
        for f in features:
            if f['name'] not in seen:
                seen.add(f['name'])
                unique.append(f)

        return unique

    # ─────────────────────────────────────────
    # BLOG EXTRACTOR
    # ─────────────────────────────────────────
    def extract_blog_data(self, soup):
        """
        Extract blog post titles and dates from a SaaS blog page.
        Returns list of: {title, date, url}
        """
        posts = []

        # Look for article/post elements
        selectors = ['article', '.post', '.blog-post', '.blog-item',
                     '.entry', '[class*="post"]', '[class*="article"]']

        found = set()
        for sel in selectors:
            for el in soup.select(sel)[:20]:
                title_el = el.find(['h1', 'h2', 'h3', 'h4'])
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or title in found or len(title) > 200:
                    continue
                found.add(title)

                link = title_el.find('a') or el.find('a')
                url = link.get('href', '') if link else ''

                date_el = el.find(['time', '[class*="date"]', '[class*="time"]'])
                date = ''
                if date_el:
                    date = (date_el.get('datetime') or
                            date_el.get_text(strip=True))[:20]

                posts.append({'title': title, 'date': date, 'url': url})

        # Fallback: any page heading list
        if not posts:
            for h in soup.find_all(['h2', 'h3'])[:15]:
                title = h.get_text(strip=True)
                if title and len(title) > 10 and len(title) < 200:
                    posts.append({'title': title, 'date': '', 'url': ''})

        return posts[:20]

    # ─────────────────────────────────────────
    # PLAIN ENGLISH CHANGE DESCRIPTIONS
    # ─────────────────────────────────────────
    def describe_pricing_changes(self, old_plans, new_plans):
        """Generate plain English descriptions of pricing changes."""
        messages = []

        old_by_name = {p['name']: p for p in old_plans if p.get('name')}
        new_by_name = {p['name']: p for p in new_plans if p.get('name')}

        # New plans added
        for name in new_by_name:
            if name not in old_by_name:
                p = new_by_name[name]
                price_str = p.get('price') or 'unknown price'
                messages.append(f'New plan added: "{name}" at {price_str}')

        # Plans removed
        for name in old_by_name:
            if name not in new_by_name:
                messages.append(f'Plan removed: "{name}"')

        # Price changes
        for name in new_by_name:
            if name in old_by_name:
                old_p = old_by_name[name].get('price')
                new_p = new_by_name[name].get('price')
                if old_p and new_p and old_p != new_p:
                    messages.append(
                        f'"{name}" price changed from {old_p} to {new_p}'
                    )

                # Feature changes inside plan
                old_feats = set(old_by_name[name].get('features', []))
                new_feats = set(new_by_name[name].get('features', []))
                added = new_feats - old_feats
                removed = old_feats - new_feats
                for f in list(added)[:3]:
                    messages.append(f'"{name}" plan: added feature "{f[:80]}"')
                for f in list(removed)[:3]:
                    messages.append(f'"{name}" plan: removed feature "{f[:80]}"')

        return messages

    def describe_feature_changes(self, old_features, new_features):
        """Generate plain English descriptions of feature page changes."""
        messages = []

        old_names = {f['name'] for f in old_features}
        new_names = {f['name'] for f in new_features}

        added = new_names - old_names
        removed = old_names - new_names

        for name in list(added)[:5]:
            messages.append(f'New feature announced: "{name}"')
        for name in list(removed)[:5]:
            messages.append(f'Feature removed from page: "{name}"')

        return messages

    def describe_blog_changes(self, old_posts, new_posts):
        """Generate plain English descriptions of new blog posts."""
        messages = []

        old_titles = {p['title'] for p in old_posts}
        new_titles = {p['title'] for p in new_posts}

        added = new_titles - old_titles
        for title in list(added)[:5]:
            messages.append(f'New blog post published: "{title}"')

        return messages

    # ─────────────────────────────────────────
    # SCRAPE ONE PAGE
    # ─────────────────────────────────────────
    def scrape_page(self, competitor_name, page_config):
        url = page_config['url']
        page_type = page_config.get('type', 'other')
        selector = page_config.get('selector', '')

        print(f"\n  Scraping [{page_type.upper()}] {competitor_name}")
        print(f"  URL: {url}")

        response = self.fetch_page(url)
        if not response:
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        soup = self.clean_soup(soup)

        # Apply CSS selector if provided
        if selector:
            selected = soup.select(selector)
            if selected:
                container = BeautifulSoup('<div></div>', 'html.parser')
                container.div.extend(selected)
                soup = container

        # ── Extract structured data based on page type ──
        if page_type == 'pricing':
            structured = self.extract_pricing_data(soup)
        elif page_type == 'features':
            structured = self.extract_features_data(soup)
        elif page_type == 'blog':
            structured = self.extract_blog_data(soup)
        else:
            # Generic: just grab cleaned text
            structured = {'text': soup.get_text(separator='\n', strip=True)[:5000]}

        structured_json = json.dumps(structured, sort_keys=True, ensure_ascii=False)
        content_hash = hashlib.sha256(structured_json.encode()).hexdigest()

        # ── Compare with previous snapshot ──
        previous = self.db.get_latest_snapshot(competitor_name, url)

        # Create metadata for snapshot
        metadata = {
            'status_code': response.status_code,
            'scraped_at': datetime.now().isoformat(),
        }

        if previous and previous['content_hash'] == content_hash:
            print(f"  → No changes")
            # FIXED: Still save a snapshot to update the timestamp
            self.db.save_snapshot(
                competitor_name=competitor_name,
                page_url=url,
                page_type=page_type,
                content_hash=content_hash,
                content=structured_json,
                metadata=metadata
            )
            return False

        # ── Generate plain English change descriptions ──
        change_messages = []

        if previous:
            try:
                old_data = json.loads(previous['content'])
            except Exception:
                old_data = {}

            if page_type == 'pricing':
                change_messages = self.describe_pricing_changes(
                    old_data if isinstance(old_data, list) else [],
                    structured if isinstance(structured, list) else []
                )
            elif page_type == 'features':
                change_messages = self.describe_feature_changes(
                    old_data if isinstance(old_data, list) else [],
                    structured if isinstance(structured, list) else []
                )
            elif page_type == 'blog':
                change_messages = self.describe_blog_changes(
                    old_data if isinstance(old_data, list) else [],
                    structured if isinstance(structured, list) else []
                )

            if not change_messages:
                change_messages = ['Content updated on this page']

            description = ' | '.join(change_messages)
            if len(description) > 500:
                description = description[:497] + '...'

            print(f"  ✓ CHANGE: {description}")

            self.db.record_change(
                competitor_name=competitor_name,
                page_url=url,
                page_type=page_type,
                change_description=description,
                old_content=previous['content'][:1000],
                new_content=structured_json[:1000],
            )
        else:
            print(f"  → First snapshot saved")

        # Save new snapshot
        self.db.save_snapshot(
            competitor_name=competitor_name,
            page_url=url,
            page_type=page_type,
            content_hash=content_hash,
            content=structured_json,
            metadata=metadata
        )

        return bool(previous)  # Only count as "change" if not first scrape

    # ─────────────────────────────────────────
    # SCRAPE ALL
    # ─────────────────────────────────────────
    def scrape_all_competitors(self):
        print(f"\n{'='*60}")
        print(f"Scraping started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        # FIXED: Read competitors from database, not config
        competitors = self.db.get_all_competitors_from_db()
        
        if not competitors:
            print("No competitors configured in the database.")
            print("Please add competitors via the web dashboard.")
            return 0

        tasks = []
        for competitor in competitors:
            for page in competitor.get('pages', []):
                tasks.append((competitor['name'], page))

        if not tasks:
            print("No pages configured for tracking.")
            return 0

        total_changes = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.scrape_page, name, page): (name, page)
                for name, page in tasks
            }
            for future in as_completed(futures):
                name, page = futures[future]
                try:
                    if future.result():
                        total_changes += 1
                except Exception as e:
                    print(f"  ✗ Error scraping {name}: {e}")

        print(f"\n{'='*60}")
        print(f"Done. {total_changes} changes detected.")
        print(f"{'='*60}\n")
        return total_changes

    # ─────────────────────────────────────────
    # REPORT
    # ─────────────────────────────────────────
    def generate_report(self, days=7):
        changes = self.db.get_recent_changes(days=days)

        if not changes:
            return f"No changes detected in the last {days} days."

        lines = [
            "COMPETITOR INTELLIGENCE REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Period: Last {days} days",
            "=" * 60, "",
        ]

        by_competitor = {}
        for c in changes:
            by_competitor.setdefault(c['competitor_name'], []).append(c)

        for name, comps in by_competitor.items():
            lines.append(name)
            lines.append("-" * len(name))
            for c in comps:
                lines.append(f"  [{c['page_type'].upper()}] {c['change_description']}")
                lines.append(f"  URL: {c['page_url']}")
                lines.append(f"  When: {c['detected_at']}")
                lines.append("")
            lines.append("")

        lines += ["=" * 60, f"Total: {len(changes)} changes"]
        return "\n".join(lines)


if __name__ == "__main__":
    scraper = CompetitorScraper()
    scraper.scrape_all_competitors()
