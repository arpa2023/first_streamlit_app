# research/person_finder.py
"""
Personen-Finder: Sucht öffentlich zugängliche Personeninformationen.

Strategien (absteigend nach Qualität):
1. Firmen-Website: /team, /about, /management Seiten
2. Öffentliche Verzeichnisse (z.B. Impressum, Kontaktseiten)
3. Simulierte Personenprofile aus strukturierten Daten

HINWEIS: Nur öffentlich zugängliche Informationen.
Keine Login-Automatisierung, keine geschlossenen Plattformen.
"""
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

from ..models.company import Company
from ..utils.logger import get_logger
from ..utils.email_utils import validate_email_format
from .web_scraper import WebScraper

logger = get_logger("research.persons")


class RawPerson:
    """Rohdaten einer gefundenen Person vor dem Matching."""

    def __init__(
        self,
        name: str = "",
        jobtitel: str = "",
        email: str = "",
        linkedin_url: str = "",
        quelle: str = "",
        zusatzinfo: str = ""
    ):
        self.name = name.strip()
        self.jobtitel = jobtitel.strip()
        self.email = email.strip().lower()
        self.linkedin_url = linkedin_url.strip()
        self.quelle = quelle
        self.zusatzinfo = zusatzinfo

        # Namen aufteilen
        self.vorname, self.nachname = self._split_name(self.name)

    @staticmethod
    def _split_name(full_name: str) -> Tuple[str, str]:
        """Trennt Vor- und Nachname heuristisch."""
        parts = full_name.strip().split()
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
        elif len(parts) == 1:
            return parts[0], ""
        return "", ""

    def __repr__(self):
        return f"<RawPerson name='{self.name}' titel='{self.jobtitel}'>"


class PersonFinder:
    """Findet öffentliche Personeninformationen für Unternehmen."""

    # Seiten-Pfade die typischerweise Team-Info enthalten
    TEAM_PAGE_PATHS = [
        "/team", "/about", "/about-us", "/uber-uns", "/ueber-uns",
        "/management", "/leadership", "/board", "/founders", "/people",
        "/kontakt", "/contact", "/company", "/unternehmen",
        "/en/team", "/en/about", "/de/team", "/de/unternehmen"
    ]

    def __init__(self, scraper: Optional[WebScraper] = None, max_persons: int = 15):
        self.scraper = scraper or WebScraper()
        self.max_persons = max_persons

    def find_persons(self, company: Company) -> List[RawPerson]:
        """
        Sucht öffentlich zugängliche Personen für ein Unternehmen.

        Gibt eine Liste von RawPerson-Objekten zurück.
        """
        persons = []

        if not company.website:
            logger.warning(f"Keine Website für {company.name}")
            return []

        base_url = company.website.rstrip("/")

        # 1. Bekannte Team-Seiten direkt probieren
        for path in self.TEAM_PAGE_PATHS:
            if len(persons) >= self.max_persons:
                break
            url = f"{base_url}{path}"
            try:
                found = self._scrape_persons_from_page(url, company)
                if found:
                    logger.info(f"Gefunden auf {url}: {len(found)} Personen")
                    persons.extend(found)
            except Exception as e:
                logger.debug(f"Fehler bei {url}: {e}")

        # 2. Von der Homepage aus suchen
        if len(persons) < 3:
            try:
                soup = self.scraper.get_page(base_url)
                if soup:
                    team_links = self.scraper.extract_team_links(soup, base_url)
                    for link in team_links[:5]:
                        if len(persons) >= self.max_persons:
                            break
                        found = self._scrape_persons_from_page(link, company)
                        persons.extend(found)
            except Exception as e:
                logger.warning(f"Homepage-Scan für {company.name} fehlgeschlagen: {e}")

        # Emails von allen gefundenen Seiten sammeln
        domain_emails = self._collect_domain_emails(base_url, company.domain or "")

        # Emails den Personen zuweisen
        for person in persons:
            if not person.email and domain_emails:
                matched = self._match_email(person.vorname, person.nachname, domain_emails)
                if matched:
                    person.email = matched

        # Duplikate entfernen
        persons = self._deduplicate(persons)

        logger.info(f"{company.name}: {len(persons)} Personen gefunden")
        return persons[:self.max_persons]

    def _scrape_persons_from_page(self, url: str, company: Company) -> List[RawPerson]:
        """Extrahiert Personen von einer einzelnen Seite."""
        soup = self.scraper.get_page(url)
        if not soup:
            return []

        persons = []

        # Strategie 1: Schema.org Person-Markup
        import json
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict) and data.get("@type") == "Person":
                    p = self._from_schema_person(data, url)
                    if p:
                        persons.append(p)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") == "Person":
                            p = self._from_schema_person(item, url)
                            if p:
                                persons.append(p)
            except Exception:
                pass

        # Strategie 2: Heuristische HTML-Erkennung
        if not persons:
            persons = self._extract_persons_heuristic(soup, url)

        # Emails direkt auf der Seite suchen
        page_emails = self.scraper.extract_emails_from_page(url)
        domain = company.domain or ""
        domain_emails = [e for e in page_emails if domain and domain in e]

        return persons

    def _from_schema_person(self, data: dict, source_url: str) -> Optional[RawPerson]:
        """Erstellt RawPerson aus Schema.org Daten."""
        name = data.get("name", "")
        if not name:
            return None

        job = data.get("jobTitle", "")
        email = data.get("email", "").replace("mailto:", "")
        linkedin = ""
        same_as = data.get("sameAs", [])
        if isinstance(same_as, list):
            linkedin = next((u for u in same_as if "linkedin.com" in u), "")
        elif isinstance(same_as, str) and "linkedin.com" in same_as:
            linkedin = same_as

        return RawPerson(
            name=name,
            jobtitel=job,
            email=email if validate_email_format(email) else "",
            linkedin_url=linkedin,
            quelle=source_url
        )

    def _extract_persons_heuristic(self, soup, source_url: str) -> List[RawPerson]:
        """
        Heuristische Personen-Extraktion aus HTML.
        Sucht nach typischen Team-Card-Mustern.
        """
        persons = []

        # Typische Container für Personenkarten
        card_selectors = [
            {"class_": re.compile(r"team|person|member|employee|staff|card", re.I)},
            {"itemprop": "person"},
        ]

        candidate_containers = []
        for selector in card_selectors:
            containers = soup.find_all(["div", "article", "section", "li"], **selector)
            candidate_containers.extend(containers)

        for container in candidate_containers[:30]:
            person = self._extract_person_from_container(container, source_url)
            if person and len(person.name) > 2:
                persons.append(person)

        # Fallback: Alle h3/h4 als potenzielle Namen
        if not persons:
            persons = self._extract_from_headings(soup, source_url)

        return persons

    def _extract_person_from_container(self, container, source_url: str) -> Optional[RawPerson]:
        """Extrahiert Person aus einem HTML-Container."""
        # Name: erstes h2/h3/h4/strong
        name_tag = container.find(["h2", "h3", "h4", "h5", "strong"])
        if not name_tag:
            return None
        name = name_tag.get_text(strip=True)

        # Titel: p-Tag oder span nach dem Name-Tag
        title = ""
        for tag in container.find_all(["p", "span", "em"]):
            text = tag.get_text(strip=True)
            if text and text != name and len(text) < 100:
                if self._looks_like_job_title(text):
                    title = text
                    break

        # Email
        email = ""
        email_tag = container.find("a", href=re.compile(r"^mailto:"))
        if email_tag:
            email = email_tag.get("href", "").replace("mailto:", "")

        # LinkedIn
        linkedin = ""
        for a in container.find_all("a", href=True):
            if "linkedin.com" in a.get("href", ""):
                linkedin = a["href"]
                break

        if not name or len(name) < 3:
            return None

        return RawPerson(
            name=name,
            jobtitel=title,
            email=email if validate_email_format(email) else "",
            linkedin_url=linkedin,
            quelle=source_url
        )

    def _extract_from_headings(self, soup, source_url: str) -> List[RawPerson]:
        """Extrahiert Namen aus Überschriften als letzter Fallback."""
        persons = []
        for tag in soup.find_all(["h3", "h4"]):
            text = tag.get_text(strip=True)
            if self._looks_like_person_name(text):
                # Nächstes Element als möglicher Titel
                sibling = tag.find_next_sibling(["p", "span"])
                title = ""
                if sibling:
                    sibling_text = sibling.get_text(strip=True)
                    if self._looks_like_job_title(sibling_text):
                        title = sibling_text
                persons.append(RawPerson(name=text, jobtitel=title, quelle=source_url))
        return persons[:20]

    def _collect_domain_emails(self, base_url: str, domain: str) -> List[str]:
        """Sammelt alle Emails einer Domain von typischen Seiten."""
        emails = []
        contact_paths = ["/kontakt", "/contact", "/impressum", "/imprint"]
        for path in contact_paths:
            try:
                found = self.scraper.extract_emails_from_page(f"{base_url}{path}")
                if domain:
                    emails.extend(e for e in found if domain in e)
            except Exception:
                pass
        return list(set(emails))

    def _match_email(self, vorname: str, nachname: str, emails: List[str]) -> Optional[str]:
        """Versucht eine Email einer Person zuzuordnen."""
        v = vorname.lower() if vorname else ""
        n = nachname.lower() if nachname else ""
        for email in emails:
            local = email.split("@")[0].lower()
            if (v and v in local) or (n and n in local):
                return email
        return None

    def _deduplicate(self, persons: List[RawPerson]) -> List[RawPerson]:
        """Entfernt doppelte Personen nach Name."""
        seen_names = set()
        unique = []
        for p in persons:
            key = p.name.lower().strip()
            if key and key not in seen_names:
                seen_names.add(key)
                unique.append(p)
        return unique

    @staticmethod
    def _looks_like_person_name(text: str) -> bool:
        """Heuristik: Ist der Text ein Personenname?"""
        if not text or len(text) < 4 or len(text) > 60:
            return False
        parts = text.split()
        if len(parts) < 2 or len(parts) > 5:
            return False
        # Großbuchstaben am Anfang jedes Teils (Name-Pattern)
        return all(p[0].isupper() for p in parts if p)

    @staticmethod
    def _looks_like_job_title(text: str) -> bool:
        """Heuristik: Ist der Text ein Jobtitel?"""
        if not text or len(text) > 120:
            return False
        keywords = [
            "CEO", "CTO", "CFO", "CMO", "COO", "CSO", "CPO",
            "Director", "Head", "Manager", "Lead", "VP", "President",
            "Founder", "Partner", "Leiter", "Leitung", "Geschäftsführer",
            "Verantwortlich", "Chef", "Chief", "Officer", "Engineer",
            "Consultant", "Specialist", "Analyst", "Koordinator"
        ]
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)
