"""
Look Out - Headless Extraction Engine
Uses Playwright to render JavaScript and pull raw DOM content.
"""
from playwright.sync_api import sync_playwright
import time

def fetch_html(url: str, max_retries: int = 2) -> str:
    """
    Fetches the HTML of a page using a headless browser.
    Includes built-in retries and strict HTTP status validation to prevent error-page scraping.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Spoofing a standard Windows Chrome user
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        raw_html = ""
        
        for attempt in range(max_retries + 1):
            try:
                # domcontentloaded is safer and faster.
                response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # --- WEAK LINK FIXED: THE HTTP ERROR TRAP ---
                # Playwright doesn't throw an error for 404s/503s. We must check manually.
                if response and response.status >= 400:
                    print(f"  -> Scraper Warning: Target returned HTTP {response.status} (Attempt {attempt + 1})")
                    if attempt < max_retries:
                        time.sleep(3) # Wait and try again (fixes temporary 503 outages)
                        continue
                    else:
                        print("  -> Scraper Error: Max retries reached on HTTP error.")
                        raw_html = "" # Return empty string so main.py skips it safely
                        break
                
                # Force a hard 3-second wait to let React/Next.js paint the text on the screen
                page.wait_for_timeout(3000)
                raw_html = page.content()
                
                break # Success! Break out of the retry loop.
                
            except Exception as e:
                print(f"  -> Engine Exception: Failed to fetch {url}. Reason: {e} (Attempt {attempt + 1})")
                if attempt < max_retries:
                    time.sleep(3)
                else:
                    raw_html = ""
                    break
                    
        browser.close()
        return raw_html