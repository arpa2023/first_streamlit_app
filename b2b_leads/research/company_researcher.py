# research/company_researcher.py
"""
Firmen-Researcher: Öffentliche Informationen zu Unternehmen sammeln.
Quellen: Firmenwebsite, öffentliche Verzeichnisse, Meta-Tags.
"""
from typing import Optional
from urllib.parse import urlparse

from ..models.company import Company
from ..utils.logger import get_logger
from .web_scraper import WebScraper

logger = get_logger("research.company")


class CompanyResearcher:
    """Recherchiert öffentlich zugängliche Firmeninformationen."""

    def __init__(self, scraper: Optional[WebScraper] = None):
        self.scraper = scraper or WebScraper()

    def enrich(self, company: Company) -> Company:
        """
        Reichert ein Company-Objekt mit öffentlichen Daten an.
        Verändert das übergebene Objekt und gibt es zurück.
        """
        logger.info(f"Recherchiere: {company.name} ({company.domain})")

        # Website aufbauen
        if not company.website and company.domain:
            company.website = f"https://{company.domain}"

        if not company.website:
            logger.warning(f"Keine Website für {company.name}, überspringe Web-Recherche")
            return company

        # Startseite scrapen
        try:
            soup = self.scraper.get_page(company.website)
            if soup:
                self._extract_from_homepage(company, soup)
        except Exception as e:
            logger.error(f"Fehler beim Scrapen von {company.website}: {e}")

        return company

    def _extract_from_homepage(self, company: Company, soup) -> None:
        """Extrahiert Metadaten von der Firmen-Homepage."""
        # Meta-Description als Beschreibung
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and not company.beschreibung:
            company.beschreibung = meta_desc.get("content", "")[:500]

        # OG-Tags
        og_desc = soup.find("meta", property="og:description")
        if og_desc and not company.beschreibung:
            company.beschreibung = og_desc.get("content", "")[:500]

        # Schema.org Daten
        structured = self.scraper.extract_structured_data(soup)
        if structured:
            self._apply_structured_data(company, structured)

        # Keywords aus Meta-Tags
        meta_kw = soup.find("meta", attrs={"name": "keywords"})
        if meta_kw:
            kw_str = meta_kw.get("content", "")
            keywords = [k.strip() for k in kw_str.split(",") if k.strip()]
            company.technologien.extend(keywords[:10])

        company.quelle = company.website

    def _apply_structured_data(self, company: Company, data: dict) -> None:
        """Übernimmt Schema.org-Daten."""
        if not company.beschreibung:
            company.beschreibung = data.get("description", "")[:500]
        if not company.standort:
            addr = data.get("address", {})
            if isinstance(addr, dict):
                parts = [
                    addr.get("addressLocality", ""),
                    addr.get("addressCountry", "")
                ]
                company.standort = ", ".join(p for p in parts if p)
        if not company.land:
            addr = data.get("address", {})
            if isinstance(addr, dict):
                company.land = addr.get("addressCountry", "")

    def build_website_url(self, domain: str) -> str:
        """Baut Website-URL aus Domain."""
        if not domain:
            return ""
        if "://" not in domain:
            return f"https://{domain}"
        return domain
