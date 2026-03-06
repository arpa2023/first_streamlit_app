# research/web_scraper.py
"""
Web-Scraper: requests + BeautifulSoup als primäre Methode.
Playwright als Fallback nur für JS-Heavy Pages.
Alle Methoden arbeiten nur mit öffentlich zugänglichen Informationen.
"""
import re
import time
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ..utils.logger import get_logger
from ..utils.retry import safe_get

logger = get_logger("research.scraper")


class WebScraper:
    """Basis-Scraper mit requests + BeautifulSoup."""

    def __init__(self, timeout: int = 10, delay: float = 1.5):
        self.timeout = timeout
        self.delay = delay  # Höfliche Pause zwischen Requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        })

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Holt eine Seite und gibt BeautifulSoup zurück."""
        if not url:
            return None

        response = safe_get(url, session=self.session, timeout=self.timeout)
        if not response:
            return None

        time.sleep(self.delay)  # Rate-limiting respektieren

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            return soup
        except Exception as e:
            logger.warning(f"HTML-Parsing fehlgeschlagen für {url}: {e}")
            return None

    def get_text(self, url: str) -> str:
        """Gibt bereinigten Text einer Seite zurück."""
        soup = self.get_page(url)
        if not soup:
            return ""
        # Skripte und Styles entfernen
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return " ".join(soup.get_text(separator=" ").split())

    def extract_emails_from_page(self, url: str) -> List[str]:
        """Extrahiert öffentlich sichtbare Emails aus einer Seite."""
        text = self.get_text(url)
        pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
        emails = list(set(re.findall(pattern, text)))
        # Spam-Adressen und Platzhalter filtern
        filtered = [
            e for e in emails
            if not any(x in e.lower() for x in [
                "example", "domain.com", "youremail", "email@email",
                "placeholder", "test@test", "noreply", "no-reply"
            ])
        ]
        return filtered

    def extract_team_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Findet Links zu Team/About/Kontakt-Seiten."""
        keywords = ["team", "about", "uber-uns", "ueber-uns", "kontakt", "contact",
                    "leadership", "management", "founders", "people", "staff"]
        links = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").lower()
            text = a.get_text(strip=True).lower()
            if any(kw in href or kw in text for kw in keywords):
                full_url = urljoin(base_url, a["href"])
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    links.append(full_url)
        return list(set(links))

    def extract_structured_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extrahiert Schema.org JSON-LD Daten falls vorhanden."""
        import json
        data = {}
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                content = json.loads(script.string or "")
                if isinstance(content, dict):
                    data.update(content)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            data.update(item)
            except (json.JSONDecodeError, TypeError):
                pass
        return data
