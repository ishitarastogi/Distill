"""Temporary diagnostic — run once, then delete. Not part of the pipeline."""
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DistillBot/1.0)"}

urls = [
    "https://clearpool.medium.com/clearpool-prime-institutional-credit-onchain-b86b443c5437",
    "https://clearpool.medium.com/here-is-a-problem-almost-every-business-runs-into-ae58961c4d4c",
]

for url in urls:
    print(f"\n{'='*60}\n{url}\n{'='*60}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Status code: {resp.status_code}")
        print(f"Raw HTML length: {len(resp.text)} chars")

        soup = BeautifulSoup(resp.text, "html.parser")
        for selector in ["article", "main", "[role=main]", ".post-content", ".article-content"]:
            found = soup.select_one(selector)
            print(f"  Selector '{selector}': {'FOUND' if found else 'not found'}"
                  + (f" ({len(found.get_text())} chars of text)" if found else ""))

        text_lower = resp.text.lower()
        print(f"  Contains 'captcha': {'captcha' in text_lower}")
        print(
            f"  Contains 'sign in': {'sign in' in text_lower or 'signin' in text_lower}")
        print(f"  Contains 'cloudflare': {'cloudflare' in text_lower}")
        print(
            f"  <body> tag text length: {len(soup.body.get_text()) if soup.body else 0}")
    except Exception as e:
        print(f"Request failed: {e}")
