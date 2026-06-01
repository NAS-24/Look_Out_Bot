"""
Look Out - DOM Sanitization
Strips noisy HTML tags to prevent false-positive diffs.
"""
from bs4 import BeautifulSoup

def sanitize_html(raw_html: str) -> str:
    """
    Takes raw HTML, rips out irrelevant structural tags, 
    and returns a clean, space-separated text string.
    """
    if not raw_html:
        return ""

    soup = BeautifulSoup(raw_html, "html.parser")

    # These tags change frequently but have zero meaning to our prompt
    noisy_tags = [
        "script", "style", "noscript", "nav", "footer", "aside", 
        "header", "svg", "button", "form", "meta", "link", "iframe", "path"
    ]

    # Decompose completely destroys the tag and its contents from the DOM
    for tag in soup(noisy_tags):
        tag.decompose()

    # Extract whatever text is left, joining it with a single space.
    # strip=True removes leading/trailing whitespace.
    clean_text = soup.get_text(separator=" ", strip=True)

    return clean_text