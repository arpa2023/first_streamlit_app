# parser/csv_parser.py
"""
CSV-Parser für Unternehmensliste und Jobprofile.
Tolerant gegenüber fehlenden Feldern und Encoding-Problemen.
"""
import csv
from pathlib import Path
from typing import List, Optional
from ..models.company import Company
from ..models.job_profile import JobProfile
from ..utils.logger import get_logger

logger = get_logger("parser.csv")


def _read_csv(filepath: str) -> List[dict]:
    """Liest CSV mit Encoding-Fallback."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CSV nicht gefunden: {filepath}")

    for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            with open(path, newline="", encoding=encoding) as f:
                reader = csv.DictReader(f, delimiter=",")
                # Semikolon als Trennzeichen versuchen falls nötig
                rows = list(reader)
                if rows and len(next(iter(rows)).keys()) == 1:
                    # Wahrscheinlich Semikolon-separiert
                    f.seek(0)
                    reader = csv.DictReader(f, delimiter=";")
                    rows = list(reader)
                logger.info(f"CSV gelesen: {filepath} ({len(rows)} Zeilen, encoding={encoding})")
                return rows
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Konnte {filepath} mit keinem Encoding lesen")


def _col(row: dict, *keys: str, default: str = "") -> Optional[str]:
    """Sucht einen Wert unter mehreren möglichen Spaltennamen."""
    for key in keys:
        for k, v in row.items():
            if k.strip().lower() == key.lower():
                val = str(v).strip() if v else ""
                return val if val not in ("", "nan", "None") else None
    return default if default != "" else None


def parse_companies_csv(filepath: str) -> List[Company]:
    """
    Parst Unternehmensliste CSV.

    Erwartete Spalten (flexibel):
        name/firmenname/company, domain/website, linkedin, land/country,
        standort/city/location, branche/industry, mitarbeiterzahl/employees
    """
    rows = _read_csv(filepath)
    companies = []

    for i, row in enumerate(rows, 1):
        try:
            name = _col(row, "name", "firmenname", "company", "unternehmen")
            if not name:
                logger.warning(f"Zeile {i}: Kein Firmenname gefunden, überspringe")
                continue

            domain = _col(row, "domain", "website_domain")
            website = _col(row, "website", "url", "homepage")

            # Domain aus Website ableiten wenn nicht explizit angegeben
            if not domain and website:
                from urllib.parse import urlparse
                parsed = urlparse(website if "://" in website else f"https://{website}")
                domain = parsed.netloc.replace("www.", "") or None

            company = Company(
                name=name,
                domain=domain,
                website=website,
                linkedin_url=_col(row, "linkedin", "linkedin_url", "linkedin_company"),
                land=_col(row, "land", "country", "region"),
                standort=_col(row, "standort", "city", "location", "ort"),
                branche=_col(row, "branche", "industry", "sektor"),
                mitarbeiterzahl=_col(row, "mitarbeiterzahl", "employees", "size"),
                quelle="input_csv",
                rohdaten=dict(row)
            )
            companies.append(company)

        except Exception as e:
            logger.error(f"Fehler in Zeile {i} von {filepath}: {e}")

    logger.info(f"Firmen geladen: {len(companies)} von {len(rows)}")
    return companies


def parse_job_profiles_csv(filepath: str) -> List[JobProfile]:
    """
    Parst Jobprofil-CSV.

    Erwartete Spalten:
        id, bezeichnung, titel_synonyme (;-separiert),
        verantwortungs_keywords (;-separiert),
        senioritaet_min, entscheider (ja/nein), gewichtung
    """
    rows = _read_csv(filepath)
    profiles = []

    for i, row in enumerate(rows, 1):
        try:
            pid = _col(row, "id", "profile_id", "profil_id")
            bezeichnung = _col(row, "bezeichnung", "name", "label", "profil")

            if not (pid or bezeichnung):
                logger.warning(f"Zeile {i}: Kein ID/Name, überspringe")
                continue

            # Synonyme und Keywords aus semikolon-getrennten Feldern
            def split_field(key: str) -> List[str]:
                val = _col(row, key) or ""
                return [s.strip() for s in val.split(";") if s.strip()]

            entscheider_val = (_col(row, "entscheider", "decision_maker") or "").lower()

            profile = JobProfile(
                id=pid or bezeichnung.lower().replace(" ", "_"),
                bezeichnung=bezeichnung or pid,
                titel_synonyme=split_field("titel_synonyme"),
                verantwortungs_keywords=split_field("verantwortungs_keywords"),
                senioritaet_min=_col(row, "senioritaet_min", "min_seniority") or "Manager",
                entscheider=entscheider_val in ("ja", "yes", "true", "1"),
                gewichtung=float(_col(row, "gewichtung", "weight") or 1.0),
                notizen=_col(row, "notizen", "notes") or ""
            )
            profiles.append(profile)

        except Exception as e:
            logger.error(f"Fehler in Zeile {i} von {filepath}: {e}")

    logger.info(f"Jobprofile geladen: {len(profiles)} von {len(rows)}")
    return profiles
