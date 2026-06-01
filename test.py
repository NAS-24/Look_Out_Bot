"""
Look Out - Extraction & Cleaning Test
Proves that Playwright and BeautifulSoup can fetch and sanitize a webpage.
"""
from scraper.engine import fetch_html
from scraper.cleaner import sanitize_html
from utils.hasher import generate_hash

# Using Wikipedia's main page as a reliable, fast test target
target_url = "https://en.wikipedia.org/wiki/Main_Page"

print(f"1. Spinning up Playwright to fetch: {target_url}")
raw_html = fetch_html(target_url)
print(f"   -> Success! Fetched {len(raw_html)} characters of raw HTML.\n")

print("2. Passing to BeautifulSoup for sanitization...")
clean_text = sanitize_html(raw_html)
print(f"   -> Success! Stripped down to {len(clean_text)} characters of pure text.\n")

print("3. Generating SHA-256 Digital Fingerprint...")
text_hash = generate_hash(clean_text)
print(f"   -> Fingerprint: {text_hash}\n")

print("Test complete. If you run this again and the Wikipedia homepage hasn't changed, the fingerprint will be identical.")