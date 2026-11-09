"""
========================================================================================
FLIPKART FASHION DARK-PATTERN RESEARCH SCRAPER
========================================================================================
Module: flipkart_fashion_dark_pattern_scraper.py
Purpose: Dynamic web scraper and evidence collector designed to detect and audit
         dark patterns (deceptive choice architecture, artificial scarcity, inflated
         discounts, misleading badges, and hidden conditions) in Flipkart fashion listings.

ETHICAL, COMPLIANCE & LEGAL NOTICE:
----------------------------------------------------------------------------------------
1. ACADEMIC & AUDITING PURPOSE:
   This tool is developed strictly for empirical research, algorithmic auditing,
   consumer advocacy, and digital rights studies (e.g., aligning with the Central Consumer
   Protection Authority (CCPA) 'Guidelines for Prevention and Regulation of Dark Patterns,
   2023' and FTC digital choice architecture guidelines).

2. COMPLIANCE WITH TERMS & ROBOTS.TXT:
   Automated data collection must comply with the target platform's Terms of Use and
   applicable legal statutes. Users must avoid scraping restricted portals, bypassing
   authentication/CAPTCHA mechanisms, or violating access controls.

3. RESPONSIBLE RATE LIMITING & SERVER CARE:
   A mandatory polite delay (randomized between 2.5 and 5.0 seconds) is enforced between
   consecutive HTTP requests. Do NOT lower delays to abusive rates or launch concurrent
   DDoS-like request bursts.

4. PRIVACY SAFEGUARD (ZERO PII):
   This scraper extracts only public catalog data (product titles, prices, promotional
   badges). It does NOT collect, scrape, or store any Personal Identifiable Information
   (PII), buyer identities, delivery addresses, reviews, or payment details.

5. NON-MALICIOUS USE ONLY:
   Do NOT use this tool for commercial data resale, price undercutting bots, inventory
   hoarding, spam, or hostile competitive intelligence.

DEPENDENCIES:
----------------------------------------------------------------------------------------
Python 3.9+ required.
Install required packages via pip:
    pip install requests beautifulsoup4 pandas
========================================================================================
"""

import os
import sys
import time
import random
import re
import logging
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import requests
from bs4 import BeautifulSoup, Tag

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    import csv
    HAS_PANDAS = False


# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("FlipkartDarkPatternScraper")


# ==============================================================================
# USER INPUT: PRODUCT URLS TO SCRAPE
# ==============================================================================
# Paste your target Flipkart fashion listing URLs below.
# Both category listing URLs (with /pr?sid=) and search queries (/search?q=) are supported.
# Examples:
#   - Men's T-Shirts: "https://www.flipkart.com/clothing-and-accessories/topwear/tshirts/mens-tshirts/pr?sid=clo,ash,ank,edy"
#   - Women's Dresses: "https://www.flipkart.com/clothing-and-accessories/dresses-and-gown/dress/womens-dress/pr?sid=clo,odx,maj,jhy"
#   - Men's Footwear: "https://www.flipkart.com/footwear/mens-footwear/sports-shoes/pr?sid=osp,cil,1cu"
PRODUCT_URLS = [
    "https://www.flipkart.com/clothing-and-accessories/topwear/tshirts/mens-tshirts/pr?sid=clo,ash,ank,edy",
    "https://www.flipkart.com/clothing-and-accessories/dresses-and-gown/dress/womens-dress/pr?sid=clo,odx,maj,jhy",
    # Add more Flipkart fashion listing URLs here
]

# ==============================================================================
# SCRAPER CONFIGURATION
# ==============================================================================
CONFIG = {
    # Number of pages to paginate through for each category URL
    "MAX_PAGES_PER_URL": 2,
    # Respectful politeness delays (in seconds) between requests to protect server health
    "MIN_DELAY_SECONDS": 2.5,
    "MAX_DELAY_SECONDS": 4.5,
    # Output file name (must be saved in the same directory)
    "OUTPUT_CSV_FILE": "products.csv",
    # Network request timeout in seconds
    "TIMEOUT_SECONDS": 15,
    # Maximum retries on network failures or temporary blips
    "MAX_RETRIES": 3,
}

# Real-world desktop browser headers to prevent automated request rejection
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


# ==============================================================================
# CSS SELECTORS REPOSITORY (RESILIENT & ADAPTIVE)
# ==============================================================================
# Flipkart dynamically updates its CSS class hashes during frontend releases.
# To ensure long-term resilience, multiple candidate CSS selectors are defined
# for each component alongside DOM structure and regex fallbacks.
#
# If Flipkart changes their layout in the future:
# 1. Inspect a product card on Flipkart in Chrome DevTools (Right click -> Inspect).
# 2. Add the newly observed class name to the front of the candidate lists below.
SELECTORS = {
    # Product card container (Flipkart fashion grid items consistently use data-id)
    "card_containers": [
        "div[data-id]",          # Standard persistent container attribute
        "div._1sdMkc",          # Historical fashion grid cell
        "div._2B_pmu",          # Grid unit wrapper
        "div._1AtVbE",          # Generic search result row
        "div.slAVV4",           # 4-column fashion grid item
    ],
    # Brand label (displayed above the title on fashion cards)
    "brand": [
        "div.Fo1I0b",           # Current 2024-2026 fashion brand class
        "div._2WkVRV",          # Standard fashion brand class
        "div.WKTcLC",           # Brand/Title hybrid container
        "div.syl9yP",           # Alternative fashion brand text
    ],
    # Product title / item description
    "title": [
        "a.atJtCj",             # Current fashion product title anchor
        "a.IRpwTa",             # Standard fashion title link
        "a.WKTcLC",             # Secondary title link class
        "a.CIaYa1",             # Image wrapper anchor carrying product title attribute
        "a[title]",             # Any anchor with an explicit title attribute
    ],
    # Product link anchor
    "link": [
        "a.CIaYa1",             # Primary card link wrapper
        "a.atJtCj",             # Direct title link
        "a.k7mUBC",             # Price container link
        "a[href*='/p/']",       # Canonical product detail page pattern
        "a[href*='pid=']",      # Product ID parameter anchor
    ],
    # Final discounted selling price (currently payable)
    "discounted_price": [
        "div.hZ3P6w",           # Current fashion discounted price class
        "div.Nx9bqj",           # General Flipkart 2023-2026 price class
        "div._30jeq3",          # Historical standard price class
        "div._16J7Pf",          # Alternative special price class
    ],
    # Original MRP / Strikethrough "Was" price
    "original_price": [
        "div.kRYCnD",           # Current fashion strikethrough MRP class
        "div.yRaY8j",           # General Flipkart 2023-2026 strikethrough class
        "div._3I9_wc",          # Historical strike-through MRP class
        "div._27AhL0",          # Secondary strikethrough price class
    ],
    # Explicit percentage discount tag
    "discount_percentage": [
        "div.HQe8jr",           # Current fashion discount percentage class
        "div.UkUFwK",           # General 2024-2026 discount tag
        "div._3Ay6Sb",          # Historical discount tag
        "span",                 # Will check text matching r'\\d+% off'
    ],
    # Promotional, Urgency, and Scarcity badges
    "badge_elements": [
        "div.MaiFhH",           # Primary urgency/event badge ('Only few left', 'Big Billion Days Price')
        "div.hx1EGN",           # Promotional banner container
        "div.HZ0E6r",           # Secondary badge highlight
        "div._3G62Om",          # Historical 'Trending', 'Hot Deal' badge
        "div._2Tpdn3",          # Special label badge
        "div._1dB2fu",          # Assurance & scarcity badge
        "span._192laR",         # Small urgency pill
    ],
}


# ==============================================================================
# CORE SCRAPER FUNCTIONS
# ==============================================================================

def clean_price_text(raw_text: Optional[str]) -> Optional[float]:
    """
    Cleans raw price strings by stripping currency symbols (₹, Rs), commas, and spaces.
    
    Args:
        raw_text: Raw price string (e.g., "₹1,499", "Rs. 668", "₹ 2,299").
        
    Returns:
        Cleaned numeric price as float or int, or None if no valid price exists.
    """
    if not raw_text:
        return None
    # Strip any characters that are not digits or decimal points
    cleaned = re.sub(r"[^\d.]", "", raw_text)
    if not cleaned:
        return None
    try:
        val = float(cleaned)
        return int(val) if val.is_integer() else val
    except ValueError:
        return None


def fetch_page(url: str, session: Optional[requests.Session] = None, retries: int = CONFIG["MAX_RETRIES"]) -> Optional[str]:
    """
    Fetches raw HTML for a Flipkart listing page with robust browser headers,
    exponential retry backoff, and graceful error handling.
    
    Args:
        url: The Flipkart listing or search page URL.
        session: An active requests.Session instance (or None to create temporary).
        retries: Number of retries on transient network failures.
        
    Returns:
        HTML string if successful, or None on fatal failure.
    """
    client = session or requests.Session()
    attempt = 0

    while attempt < retries:
        attempt += 1
        try:
            logger.info(f"Fetching [Attempt {attempt}/{retries}]: {url}")
            response = client.get(
                url,
                headers=DEFAULT_HEADERS,
                timeout=CONFIG["TIMEOUT_SECONDS"],
            )

            if response.status_code == 200:
                html = response.text
                if len(html) < 5000:
                    logger.warning(f"Response suspiciously short ({len(html)} bytes). May be a bot check.")
                return html

            elif response.status_code == 429:
                backoff = (2 ** attempt) * 3
                logger.warning(f"Rate limited (HTTP 429). Backing off for {backoff:.1f}s...")
                time.sleep(backoff)
            elif response.status_code in (403, 401):
                logger.error(f"Access forbidden (HTTP {response.status_code}). Check User-Agent or IP block.")
                return None
            else:
                logger.warning(f"Unexpected HTTP status {response.status_code} for URL: {url}")
                time.sleep(2.0)

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.warning(f"Network error on attempt {attempt}: {str(e)}")
            time.sleep(2.0 * attempt)
        except Exception as e:
            logger.error(f"Unexpected exception while fetching {url}: {str(e)}")
            return None

    logger.error(f"Failed to fetch {url} after {retries} attempts.")
    return None


def parse_product_cards(html: str) -> List[Tag]:
    """
    Extracts individual product card elements from page HTML using candidate selectors.
    
    Args:
        html: Raw HTML string of the listing page.
        
    Returns:
        List of BeautifulSoup Tag elements, each representing a single product card.
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    cards: List[Tag] = []

    # Priority 1: Check standard data-id containers (Flipkart's primary card identifier)
    cards = soup.find_all("div", attrs={"data-id": True})
    if cards:
        logger.debug(f"Identified {len(cards)} product cards using 'div[data-id]' selector.")
        return cards

    # Priority 2: Fallback to candidate class selectors
    for selector in SELECTORS["card_containers"]:
        if selector == "div[data-id]":
            continue
        found = soup.select(selector)
        if found:
            logger.debug(f"Identified {len(found)} product cards using fallback selector: '{selector}'")
            return found

    logger.warning("No product cards could be identified on the page with standard selectors.")
    return []


def collect_evidence_text(card_element: Tag) -> Tuple[str, List[str]]:
    """
    Gathers and categorizes all visible UI text cues related to dark patterns:
    - Artificial scarcity / false urgency ('Only few left', 'Selling fast', 'Almost gone')
    - Promotional and manipulative badges ('Big Billion Days Price', 'Value 365', 'Bestseller', 'Lowest price since launch')
    - Financial offers and discount claims ('80% off', 'Bank offer', 'Flat extra ₹50 off')
    - Hidden conditions and small print ('T&C apply', minimum order criteria)
    
    Args:
        card_element: BeautifulSoup Tag of a single product card.
        
    Returns:
        A tuple of:
          1. Normalized evidence string (e.g. "Badges: [...]; Offers: [...]; Scarcity: '...'")
          2. List of detected dark pattern taxonomy labels for downstream analysis.
    """
    badges: List[str] = []
    scarcity_cues: List[str] = []
    offers: List[str] = []
    conditions: List[str] = []
    detected_patterns: List[str] = []

    # 1. Target known badge elements by class
    for sel in SELECTORS["badge_elements"]:
        for el in card_element.select(sel):
            txt = el.get_text(separator=" ", strip=True)
            if txt and txt not in badges:
                badges.append(txt)

    # 2. Extract discount percentage tag
    for sel in SELECTORS["discount_percentage"]:
        found_pct = card_element.select_one(sel)
        if found_pct:
            pct_text = found_pct.get_text(strip=True)
            if "% off" in pct_text.lower() and pct_text not in offers:
                offers.append(pct_text)
                break

    # 3. Comprehensive text scan across all child elements for dark pattern language
    # Checks for urgency, scarcity, conditions, and unverified authority badges
    for el in card_element.find_all(["div", "span", "p", "a"]):
        # Inspect only leaf or near-leaf elements to avoid grabbing outer container text
        if len(el.find_all()) > 2:
            continue

        raw_txt = el.get_text(strip=True)
        if not raw_txt or len(raw_txt) > 90:
            continue

        txt_lower = raw_txt.lower()

        # Scarcity / False Urgency cues
        if re.search(r"\b(only\s+\d+\s+left|only\s+few\s+left|almost\s+gone|selling\s+fast|hurry|in\s+high\s+demand)\b", txt_lower):
            if raw_txt not in scarcity_cues:
                scarcity_cues.append(raw_txt)
            if "False Urgency / Artificial Scarcity" not in detected_patterns:
                detected_patterns.append("False Urgency / Artificial Scarcity")

        # Promotional & Manipulative Badges
        elif re.search(r"\b(bestseller|top\s+rated|trending|hot\s+deal|deal\s+of\s+the\s+day|lowest\s+price\s+since\s+launch|big\s+billion|value\s+\d+|special\s+price)\b", txt_lower):
            if raw_txt not in badges:
                badges.append(raw_txt)
            if "Manipulative Promotional Badge" not in detected_patterns:
                detected_patterns.append("Manipulative Promotional Badge")

        # Offers and financial claims
        elif re.search(r"\b(bank\s+offer|cashback|extra\s+\d+%\s+off|flat\s+₹?\d+\s+off|combo\s+offer|save\s+₹?\d+)\b", txt_lower):
            if raw_txt not in offers:
                offers.append(raw_txt)

        # Hidden conditions & small print
        elif re.search(r"\b(t&c|t\s*&\s*c\s+apply|terms\s+apply|conditions\s+apply|min\.?\s*order|on\s+orders\s+above)\b", txt_lower):
            if raw_txt not in conditions:
                conditions.append(raw_txt)
            if "Hidden Conditions / Fine Print" not in detected_patterns:
                detected_patterns.append("Hidden Conditions / Fine Print")

    # Format the structured evidence string
    parts: List[str] = []
    if badges:
        parts.append(f"Badges: {badges}")
    if offers:
        parts.append(f"Offers: {offers}")
    if scarcity_cues:
        # If single cue, render as string; if multiple, list
        scarcity_repr = f"'{scarcity_cues[0]}'" if len(scarcity_cues) == 1 else str(scarcity_cues)
        parts.append(f"Scarcity: {scarcity_repr}")
    if conditions:
        parts.append(f"Conditions: {conditions}")

    evidence_text = "; ".join(parts) if parts else "No explicit urgency or promotional badge cues observed"
    return evidence_text, detected_patterns


def extract_product_info(card_element: Tag, base_url: str = "https://www.flipkart.com") -> Optional[Dict[str, Any]]:
    """
    Extracts required product attributes and dark-pattern evidence from a single card.
    
    Fields extracted:
    - product_name: Brand name combined with item title/description
    - product_link: Absolute canonical product link
    - discounted_price: Clean numeric current selling price
    - original_price: Clean numeric original MRP (if present)
    - discount_percentage: Explicit or computed discount percentage
    - evidence_text: Structured summary of dark pattern cues
    - detected_dark_patterns: List of classified dark pattern categories
    
    Args:
        card_element: BeautifulSoup Tag of the product card.
        base_url: Base domain for constructing absolute URLs.
        
    Returns:
        Dictionary containing extracted fields, or None if extraction fails.
    """
    try:
        # -------------------------------------------------------------
        # 1. Product Name (Brand + Title)
        # -------------------------------------------------------------
        brand_text = ""
        for sel in SELECTORS["brand"]:
            brand_el = card_element.select_one(sel)
            if brand_el and brand_el.get_text(strip=True):
                brand_text = brand_el.get_text(strip=True)
                break

        title_text = ""
        for sel in SELECTORS["title"]:
            title_el = card_element.select_one(sel)
            if title_el:
                title_text = title_el.get_text(strip=True) or title_el.get("title", "")
                if title_text:
                    break

        if brand_text and title_text:
            product_name = f"{brand_text} - {title_text}"
        elif title_text:
            product_name = title_text
        elif brand_text:
            product_name = brand_text
        else:
            # Fallback: inspect any anchor title attribute or first text node
            first_anchor = card_element.find("a", title=True)
            product_name = first_anchor.get("title") if first_anchor else "Unknown Product Name"

        # Clean excess whitespaces
        product_name = re.sub(r"\s+", " ", product_name).strip()

        # -------------------------------------------------------------
        # 2. Product Absolute Link
        # -------------------------------------------------------------
        raw_href = None
        for sel in SELECTORS["link"]:
            link_el = card_element.select_one(sel)
            if link_el and link_el.get("href"):
                raw_href = link_el["href"]
                break

        if not raw_href:
            # Fallback: search any anchor with an href attribute
            any_a = card_element.find("a", href=True)
            raw_href = any_a["href"] if any_a else ""

        if raw_href:
            full_link = urllib.parse.urljoin(base_url, raw_href)
            # Normalize and clean tracking query parameters (keep pid identifier if present)
            parsed_url = urllib.parse.urlparse(full_link)
            qs = urllib.parse.parse_qs(parsed_url.query)
            clean_query = f"pid={qs['pid'][0]}" if "pid" in qs else ""
            product_link = urllib.parse.urlunparse(
                (parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", clean_query, "")
            )
        else:
            product_link = ""

        # -------------------------------------------------------------
        # 3. Prices & Discounts
        # -------------------------------------------------------------
        discounted_price_raw = None
        for sel in SELECTORS["discounted_price"]:
            price_el = card_element.select_one(sel)
            if price_el and price_el.get_text(strip=True):
                discounted_price_raw = price_el.get_text(strip=True)
                break

        # Regex fallback for discounted price if selector missed
        if not discounted_price_raw:
            price_match = re.search(r"₹\s*([\d,]+)", card_element.get_text())
            if price_match:
                discounted_price_raw = price_match.group(1)

        discounted_price = clean_price_text(discounted_price_raw)

        # Original / MRP Price
        original_price_raw = None
        for sel in SELECTORS["original_price"]:
            orig_el = card_element.select_one(sel)
            if orig_el and orig_el.get_text(strip=True):
                original_price_raw = orig_el.get_text(strip=True)
                break

        original_price = clean_price_text(original_price_raw)

        # Discount Percentage
        discount_percentage = None
        for sel in SELECTORS["discount_percentage"]:
            pct_el = card_element.select_one(sel)
            if pct_el:
                m = re.search(r"(\d+)%\s*off", pct_el.get_text(), re.IGNORECASE)
                if m:
                    discount_percentage = int(m.group(1))
                    break

        # Compute discount percentage if missing but both prices are present
        if discount_percentage is None and original_price and discounted_price and original_price > discounted_price:
            computed_pct = round(((original_price - discounted_price) / original_price) * 100)
            discount_percentage = int(computed_pct)

        # -------------------------------------------------------------
        # 4. Evidence Text & Dark-Pattern Categorization
        # -------------------------------------------------------------
        evidence_text, detected_patterns = collect_evidence_text(card_element)

        # Flag Deceptive / Inflated Discounting if discount is excessively high (>70%)
        # In fashion e-commerce, fictitious anchor MRPs are frequently used to fabricate extreme discounts
        if discount_percentage and discount_percentage >= 70:
            if "Inflated Reference Pricing / Deceptive Strikethrough" not in detected_patterns:
                detected_patterns.append("Inflated Reference Pricing / Deceptive Strikethrough")

        # Flag Bundled / Quantity Push (e.g. "Pack of 2", "Pack of 4")
        if re.search(r"\bpack\s+of\s+\d+\b", product_name.lower()):
            if "Bundled Add-on / Deceptive Quantity Push" not in detected_patterns:
                detected_patterns.append("Bundled Add-on / Deceptive Quantity Push")

        patterns_summary = "; ".join(detected_patterns) if detected_patterns else "None"

        return {
            "product_name": product_name,
            "product_link": product_link,
            "discounted_price": discounted_price,
            "original_price": original_price,
            "discount_percentage": f"{discount_percentage}%" if discount_percentage is not None else None,
            "evidence_text": evidence_text,
            "detected_dark_patterns": patterns_summary,
        }

    except Exception as e:
        logger.error(f"Error parsing product card: {str(e)}", exc_info=False)
        return None


def get_next_page_url(soup: BeautifulSoup, current_url: str, current_page: int) -> Optional[str]:
    """
    Detects the Next Page URL either from the pagination DOM elements or by
    constructing the subsequent query parameter.
    
    Args:
        soup: BeautifulSoup parse tree of the current page.
        current_url: The current page URL.
        current_page: Current page integer index.
        
    Returns:
        Next absolute URL string, or None if no further page exists.
    """
    next_page_num = current_page + 1

    # Method 1: Look for explicit Next anchor link in pagination DOM
    next_anchor = soup.find(lambda tag: tag.name == "a" and "next" in tag.get_text().strip().lower() and tag.get("href"))
    if next_anchor and next_anchor.get("href"):
        next_href = next_anchor["href"]
        next_url = urllib.parse.urljoin("https://www.flipkart.com", next_href)
        logger.debug(f"Discovered Next page URL via pagination DOM: {next_url}")
        return next_url

    # Method 2: Construct URL by safely updating the 'page' parameter
    parsed = urllib.parse.urlparse(current_url)
    qs = urllib.parse.parse_qs(parsed.query)
    qs["page"] = [str(next_page_num)]
    new_query = urllib.parse.urlencode(qs, doseq=True)
    constructed_url = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )
    logger.debug(f"Constructed Next page URL: {constructed_url}")
    return constructed_url


def scrape_flipkart_listing(
    category_url: str,
    max_pages: int = CONFIG["MAX_PAGES_PER_URL"],
    session: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:
    """
    Orchestrates page fetching, card extraction, and pagination for a single Flipkart URL.
    
    Args:
        category_url: Target Flipkart listing URL.
        max_pages: Maximum pages to paginate through.
        session: Active requests.Session instance.
        
    Returns:
        List of product dictionaries scraped across all requested pages.
    """
    client = session or requests.Session()
    all_products: List[Dict[str, Any]] = []
    current_url = category_url
    page = 1

    logger.info(f"=== Starting scrape for listing: {category_url} (Max pages: {max_pages}) ===")

    while current_url and page <= max_pages:
        logger.info(f"Scraping Page {page}/{max_pages}...")
        html = fetch_page(current_url, session=client)
        if not html:
            logger.warning(f"Aborting pagination for {category_url} due to fetch error on page {page}.")
            break

        cards = parse_product_cards(html)
        logger.info(f"Found {len(cards)} product cards on Page {page}.")

        page_products = 0
        for card in cards:
            product_data = extract_product_info(card)
            if product_data and product_data.get("product_name"):
                # Append audit metadata
                product_data["page_number"] = page
                product_data["source_url"] = category_url
                product_data["scrape_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                all_products.append(product_data)
                page_products += 1

        logger.info(f"Successfully scraped {page_products} products from Page {page}.")

        # Check pagination if more pages are desired
        if page < max_pages:
            soup = BeautifulSoup(html, "html.parser")
            current_url = get_next_page_url(soup, current_url, current_page=page)
            page += 1

            # Enforce polite delay between pagination requests
            delay = random.uniform(CONFIG["MIN_DELAY_SECONDS"], CONFIG["MAX_DELAY_SECONDS"])
            logger.info(f"Polite delay: sleeping for {delay:.2f} seconds before next page...")
            time.sleep(delay)
        else:
            break

    return all_products


def save_to_csv(products: List[Dict[str, Any]], filepath: str = CONFIG["OUTPUT_CSV_FILE"]) -> None:
    """
    Saves extracted product records to a single CSV file with clean headers.
    
    Args:
        products: List of product dictionaries.
        filepath: Target CSV destination path.
    """
    if not products:
        logger.warning("No products to save. CSV file will not be created.")
        return

    # Standard column ordering
    columns = [
        "product_name",
        "product_link",
        "discounted_price",
        "original_price",
        "discount_percentage",
        "evidence_text",
        "detected_dark_patterns",
        "page_number",
        "source_url",
        "scrape_timestamp",
    ]

    try:
        if HAS_PANDAS:
            df = pd.DataFrame(products)
            # Reorder columns that exist
            ordered_cols = [c for c in columns if c in df.columns] + [c for c in df.columns if c not in columns]
            df = df[ordered_cols]
            df.to_csv(filepath, index=False, encoding="utf-8")
        else:
            # Fallback to standard library csv module
            with open(filepath, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                for prod in products:
                    row = {col: prod.get(col, "") for col in columns}
                    writer.writerow(row)

        logger.info(f"Successfully saved {len(products)} products to '{filepath}'.")
    except Exception as e:
        logger.error(f"Failed to save CSV file to '{filepath}': {str(e)}")


def print_dark_pattern_summary(products: List[Dict[str, Any]]) -> None:
    """
    Prints an analytical summary of detected dark patterns across scraped products.
    """
    if not products:
        return

    total = len(products)
    scarcity_count = sum(1 for p in products if "False Urgency" in p.get("detected_dark_patterns", ""))
    inflated_discount_count = sum(1 for p in products if "Inflated Reference Pricing" in p.get("detected_dark_patterns", ""))
    badge_count = sum(1 for p in products if "Manipulative Promotional Badge" in p.get("detected_dark_patterns", ""))
    bundle_count = sum(1 for p in products if "Bundled Add-on" in p.get("detected_dark_patterns", ""))

    print("\n" + "=" * 70)
    print("FLIPKART FASHION DARK-PATTERN AUDIT SUMMARY")
    print("=" * 70)
    print(f"Total Products Audited       : {total}")
    print(f"False Urgency / Scarcity Cues: {scarcity_count} ({scarcity_count / total * 100:.1f}%)")
    print(f"Inflated Discounts (>= 70%)  : {inflated_discount_count} ({inflated_discount_count / total * 100:.1f}%)")
    print(f"Manipulative Badges Observed : {badge_count} ({badge_count / total * 100:.1f}%)")
    print(f"Deceptive Bundles (Pack of X): {bundle_count} ({bundle_count / total * 100:.1f}%)")
    print("=" * 70 + "\n")


# ==============================================================================
# MAIN ORCHESTRATION PIPELINE
# ==============================================================================

def main():
    """
    Main execution pipeline:
    1. Validates user input URLs.
    2. Initializes HTTP session with polite configurations.
    3. Scrapes each category listing across requested pages.
    4. Aggregates data and exports to products.csv.
    5. Displays dark pattern analytical summary.
    """
    print("\n" + "#" * 70)
    print("# FLIPKART FASHION DARK-PATTERN DETECTOR & SCRAPER")
    print("# Responsible Research & Algorithmic Audit Pipeline")
    print("#" * 70 + "\n")

    if not PRODUCT_URLS:
        logger.error("No URLs specified in PRODUCT_URLS. Please add at least one Flipkart URL to scrape.")
        return

    logger.info(f"Loaded {len(PRODUCT_URLS)} category listing URL(s) for audit.")
    all_scraped_products: List[Dict[str, Any]] = []

    # Use a shared session to benefit from TCP connection reuse
    with requests.Session() as session:
        for idx, url in enumerate(PRODUCT_URLS, start=1):
            logger.info(f"Processing Category [{idx}/{len(PRODUCT_URLS)}]: {url}")
            category_products = scrape_flipkart_listing(
                category_url=url,
                max_pages=CONFIG["MAX_PAGES_PER_URL"],
                session=session,
            )
            all_scraped_products.extend(category_products)

            # Politeness delay between distinct category listings
            if idx < len(PRODUCT_URLS):
                category_delay = random.uniform(CONFIG["MIN_DELAY_SECONDS"] + 1.0, CONFIG["MAX_DELAY_SECONDS"] + 2.0)
                logger.info(f"Sleeping {category_delay:.2f}s before moving to the next category...")
                time.sleep(category_delay)

    # Export aggregated dataset
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG["OUTPUT_CSV_FILE"])
    save_to_csv(all_scraped_products, filepath=output_path)

    # Print executive summary
    print_dark_pattern_summary(all_scraped_products)


if __name__ == "__main__":
    main()
