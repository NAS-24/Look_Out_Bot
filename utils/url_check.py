from urllib.parse import urlparse
import requests

def check_url(raw: str):
    """Returns (True, clean_url) or (False, message_for_user)."""
    url = raw.strip()
    if " " in url or "." not in url:
        return False, "That doesn't look like a web address."
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    if not urlparse(url).netloc:
        return False, "That doesn't look like a web address."
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    except requests.RequestException:
        return False, "I couldn't reach that address. Check it and send it again."
    if r.status_code in (404, 410):
        return False, f"That page doesn't exist (error {r.status_code}). Send a working link."
    return True, url