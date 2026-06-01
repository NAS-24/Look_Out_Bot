"""
Look Out - Headless Extraction Engine
Uses Playwright to render JavaScript and pull raw DOM content.
"""
from playwright.sync_api import sync_playwright

def fetch_html(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Spoofing a standard Windows Chrome user
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        page = context.new_page()

        try:
            # domcontentloaded is much safer. It doesn't wait for endless ad-trackers to finish.
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            
            # Force a hard 3-second wait to let React/Next.js paint the text on the screen
            page.wait_for_timeout(3000)
            
            raw_html = page.content()
        except Exception as e:
            print(f"Engine Error: Failed to fetch {url}. Reason: {e}")
            raw_html = ""
        finally:
            browser.close()

        return raw_html