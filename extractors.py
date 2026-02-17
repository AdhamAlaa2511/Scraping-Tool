"""
Structured extraction functions for competitor tracking.
Extracts clean, structured data from pricing and feature pages.
"""

import re
from bs4 import BeautifulSoup, Tag

# UPDATED: Added fuzzy matching keywords
PRICING_KEYWORDS = ['price', 'cost', 'amount', 'fee', 'billed', 'mo', 'yr']
PLAN_KEYWORDS = ['plan', 'tier', 'package', 'bundle', 'name', 'title']
FEATURE_KEYWORDS = ['feature', 'include', 'benefit', 'capability']

def _fuzzy_match(text: str, keywords: list[str]) -> bool:
    """
    UPDATED: Helper for fuzzy matching text against keywords.
    Returns True if any keyword is found in the text (case-insensitive).
    """
    if not text:
        return False
    text_lower = text.lower()
    return any(k in text_lower for k in keywords)

def _clean_text(text: str) -> str:
    """Helper to clean and normalize text."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def _is_valid_price(text: str) -> bool:
    """
    FIXED: Validation rule to check if text looks like a price.
    Must contain a digit and generic currency symbol or keyword, OR be "free".
    """
    if not text:
        return False
    # Allow "free" without digits
    if re.search(r'\bfree\b', text, re.IGNORECASE):
        return True
    # Otherwise require digit + currency
    if not re.search(r'\d', text):
        return False
    return bool(re.search(r'[\$€£¥]|usd|eur', text, re.IGNORECASE))

def extract_pricing(html: str) -> dict:
    """
    Extract structured pricing data from an HTML page.
    UPDATED: Now includes table detection and robust fallback logic.
    """
    soup = BeautifulSoup(html, "html.parser")
    plans = []
    detected_currency = None
    billing_note = None

    # 1. Try to extract from HTML Tables (Best for structured data)
    # UPDATED: Added specific table extraction logic
    plans = _extract_from_table(soup)

    # 2. If no table data, try Card/Container based extraction (Modern layouts)
    if not plans:
        plans = _extract_from_cards(soup)

    # 3. Fallback: Visual Column Detection (Repeated structures)
    # UPDATED: Added fallback for when explicit classes fail
    if not plans:
        plans = _extract_from_visual_columns(soup)

    # Extract global currency and billing note
    for plan in plans:
        if not detected_currency and plan.get("price"):
            curr = re.search(r"([\$€£¥])", plan["price"])
            if curr:
                detected_currency = curr.group(1)
    
    # Find billing note globally if not found in plans
    if not billing_note:
        billing_pattern = re.compile(r"billed?\s*(annually|monthly|yearly)", re.IGNORECASE)
        note_el = soup.find(string=billing_pattern)
        if note_el:
            billing_note = note_el.strip()

    # Deduplicate plans (based on name and price)
    unique_plans = []
    seen = set()
    for p in plans:
        key = (p['name'], p['price'])
        if key not in seen:
            seen.add(key)
            unique_plans.append(p)

    return {
        "plans": unique_plans,
        "currency": detected_currency,
        "billing_note": billing_note,
    }

def _extract_from_table(soup: BeautifulSoup) -> list[dict]:
    """
    FIXED: Detailed extraction from <table> elements.
    Looks for headers to identify 'Plan' and 'Price' columns.
    """
    tables = soup.find_all("table")
    extracted_plans = []

    for table in tables:
        # Check headers
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        
        # Identify columns by index
        plan_idx, price_idx = -1, -1
        
        for i, h in enumerate(headers):
            if _fuzzy_match(h, PLAN_KEYWORDS) and plan_idx == -1:
                plan_idx = i
            elif _fuzzy_match(h, PRICING_KEYWORDS) and price_idx == -1:
                price_idx = i

        rows = table.find_all("tr")
        
        # If headers not in <th>, check first <tr>
        header_row_idx = -1
        if plan_idx == -1 and rows:
            first_row_cells = [td.get_text(strip=True).lower() for td in rows[0].find_all(["td", "th"])]
            for i, h in enumerate(first_row_cells):
                 if _fuzzy_match(h, PLAN_KEYWORDS): 
                     plan_idx = i
                     header_row_idx = 0
                 if _fuzzy_match(h, PRICING_KEYWORDS): 
                     price_idx = i
                     header_row_idx = 0

        # Extract data from rows
        for row_num, row in enumerate(rows):
            # FIXED: Skip the actual header row if we identified it
            if header_row_idx != -1 and row_num == header_row_idx:
                continue
            
            # Also skip if this row only contains header elements
            if row.find_all('th') and not row.find_all('td'):
                continue
            
            cells = row.find_all(["td", "th"])
            if not cells: 
                continue

            name, price = None, None
            
            # If we identified columns, use them
            if plan_idx != -1 and len(cells) > plan_idx:
                name = _clean_text(cells[plan_idx].get_text())
            if price_idx != -1 and len(cells) > price_idx:
                price = _clean_text(cells[price_idx].get_text())
            
            # Fallback: heuristics for cells
            if not name or not price:
                for cell in cells:
                    text = _clean_text(cell.get_text())
                    if not price and _is_valid_price(text):
                        price = text
                    elif not name and len(text) > 2 and len(text) < 50:
                         # Assume strictly non-price short text is name
                         if not _is_valid_price(text):
                             name = text

            if name and price:
                extracted_plans.append({
                    "name": name, 
                    "price": price, 
                    "features": [] # Tables rarely have deep features list in same row
                })

    return extracted_plans

def _extract_from_cards(soup: BeautifulSoup) -> list[dict]:
    """
    Extract from pricing cards using flexible CSS selectors.
    """
    # UPDATED: broader, regex-based class matching
    plan_selectors = [
        re.compile(r'pricing.*card', re.I),
        re.compile(r'plan.*card', re.I),
        re.compile(r'pricing.*container', re.I),
        re.compile(r'pricing.*item', re.I),
        re.compile(r'package', re.I),
        re.compile(r'tier', re.I),
    ]

    candidates = []
    for tag in soup.find_all(['div', 'article', 'section']):
        c = tag.get('class')
        if c:
             # handle list or string class
            c_str = " ".join(c) if isinstance(c, list) else c
            if any(sel.search(c_str) for sel in plan_selectors):
                candidates.append(tag)

    plans = []
    for card in candidates:
        plan = _extract_single_plan_content(card)
        if plan['name'] and (plan['price'] or plan['features']):
            plans.append(plan)
    
    return plans

def _extract_from_visual_columns(soup: BeautifulSoup) -> list[dict]:
    """
    FIXED: Fallback logic. Content grouping by parent.
    Looks for siblings with 'price' patterns.
    """
    price_pattern = re.compile(r"[\$€£¥]\s*\d+|free", re.IGNORECASE)
    
    # Find all elements looking like a price
    price_elements = soup.find_all(string=price_pattern)
    
    # Group by parent to find the "pricing container"
    parents = {}
    for p in price_elements:
        parent = p.find_parent(['div', 'section', 'li'])
        if parent:
            pid = id(parent)
            if pid not in parents: 
                parents[pid] = []
            parents[pid].append(parent)

    # If we find a parent with multiple price-containing children, likely a grid
    plans = []
    if parents:
        # Get the parent with the most price children (likely the grid wrapper)
        best_parent_id = max(parents, key=lambda k: len(parents[k]))
        # FIXED: The parent itself is the wrapper we want, not its parent
        wrapper = parents[best_parent_id][0]
        
        if wrapper:
            # First, try to find a common parent that contains all pricing cards
            # Look for the wrapper's children that are likely individual cards
            potential_cards = []
            
            # Check if the wrapper has children that look like pricing cards
            for child in wrapper.find_all(['div', 'article', 'section'], recursive=False):
                if isinstance(child, Tag):
                    child_text = child.get_text()
                    if price_pattern.search(child_text):
                        potential_cards.append(child)
            
            # If we found multiple cards at this level, use them
            if len(potential_cards) > 1:
                for card in potential_cards:
                    plan = _extract_single_plan_content(card)
                    if plan['name'] and _is_valid_price(plan['price']):
                        plans.append(plan)
            else:
                # Otherwise, go one level up and try again
                wrapper_parent = wrapper.parent
                if wrapper_parent:
                    for child in wrapper_parent.find_all(['div', 'article', 'section'], recursive=False):
                        if isinstance(child, Tag):
                            child_text = child.get_text()
                            if price_pattern.search(child_text):
                                plan = _extract_single_plan_content(child)
                                if plan['name'] and _is_valid_price(plan['price']):
                                    plans.append(plan)
                                    
    return plans

def _extract_single_plan_content(container: Tag) -> dict:
    """
    UPDATED: Improved content extraction from a specific container/card.
    """
    text = container.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    name = None
    price = None
    features = []

    # 1. Price Detection (Strict)
    price_pattern = re.compile(r"([\$€£¥]\s*[\d,]+(\.\d{2})?\s*(\/[a-z]+)?|free)", re.IGNORECASE)
    
    # Try to find price in specific class
    price_el = container.find(class_=re.compile(r'price|amount|cost', re.I))
    if price_el:
        price = _clean_text(price_el.get_text())
    
    # Fallback: Search in text lines
    if not price:
        for line in lines:
            if price_pattern.search(line):  # Use search instead of match for flexibility
                price = line
                break
    
    # 2. Name Detection
    # Try headers
    header = container.find(['h1', 'h2', 'h3', 'h4', 'strong'])
    if header:
        name = _clean_text(header.get_text())
    
    # Fallback: First line that isn't the price
    if not name and lines:
        for line in lines:
            if line != price and len(line) < 40:
                name = line
                break

    # 3. Features Detection (Lists)
    ul = container.find('ul')
    if ul:
        features = [_clean_text(li.get_text()) for li in ul.find_all('li')]
    else:
        # Fallback: Look for lines with checkmarks or specific keywords
        for line in lines:
            if re.match(r'^[✓✔\+•]|include', line, re.I):
                features.append(line)

    return {
        "name": name,
        "price": price,
        "features": features
    }

def extract_features(html: str) -> dict:
    """
    Extract structured feature data.
    UPDATED: Relaxed selectors for feature blocks.
    """
    soup = BeautifulSoup(html, "html.parser")
    features = []

    # Selectors for feature blocks
    feature_selectors = [
        re.compile(r'feature.*item', re.I),
        re.compile(r'feature.*card', re.I),
        re.compile(r'benefit.*item', re.I),
        re.compile(r'benefit.*card', re.I), # Added benefit-card
        re.compile(r'service.*item', re.I),
        re.compile(r'service.*card', re.I)
    ]

    candidates = []
    for tag in soup.find_all(['div', 'li']):
        c = tag.get('class')
        class_str = " ".join(c) if c and isinstance(c, list) else (c or "")
        if any(sel.search(class_str) for sel in feature_selectors):
            candidates.append(tag)

    for item in candidates:
        # Extract title (h3, h4, or strong)
        title_el = item.find(['h3', 'h4', 'strong', 'b'])
        desc_el = item.find('p')
        
        if title_el:
            features.append({
                "name": _clean_text(title_el.get_text()),
                "description": _clean_text(desc_el.get_text()) if desc_el else ""
            })

    # Deduplicate
    unique = {f['name']: f for f in features}.values()
    
    return {
        "features": list(unique),
        "categories": [] # Keep structure consistent
    }
