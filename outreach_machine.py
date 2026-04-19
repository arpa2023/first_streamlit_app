"""
Automatisierte Sales-Outreach-Maschine
======================================
Workflow:
  1. CSV einlesen (Firma, Vorname, Nachname)
  2. E-Mail suchen (Hunter.io) oder per Muster generieren + SMTP-Check
  3. Personen-Research via Tavily
  4. Software-Beschreibung aus Google Drive laden
  5. Personalisierte E-Mail via Claude LLM generieren (Deutsch, formell)
  6. Ergebnisse als Excel-Datei exportieren
"""

import csv
import json
import logging
import os
import re
import smtplib
import socket
import time
from pathlib import Path
from typing import Optional

import anthropic
import openpyxl
import requests
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceCredentials
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# Konfiguration – API-Keys hier eintragen oder als Umgebungsvariablen setzen
# ---------------------------------------------------------------------------

HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "DEIN_HUNTER_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "DEIN_TAVILY_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "DEIN_ANTHROPIC_API_KEY")

# Google Drive: entweder Service-Account-JSON-Datei oder OAuth-Token
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE", "google_service_account.json"
)
# ID des Google Docs / Drive-Ordners mit der Software-Beschreibung
GOOGLE_DOC_ID = os.getenv("GOOGLE_DOC_ID", "DEINE_GOOGLE_DOC_ID")

# SMTP-Verifikation (nur MX-Check, kein echter Versand)
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "verify@example.com")

INPUT_CSV = "kontakte.csv"           # Spalten: firma, vorname, nachname, (optional: geschlecht)
OUTPUT_XLSX = "outreach_ergebnisse.xlsx"

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modul 1 – E-Mail-Suche & Generierung
# ---------------------------------------------------------------------------

def find_email_hunter(vorname: str, nachname: str, firma_domain: str) -> Optional[str]:
    """Sucht E-Mail über Hunter.io Email Finder API."""
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/email-finder",
            params={
                "domain": firma_domain,
                "first_name": vorname,
                "last_name": nachname,
                "api_key": HUNTER_API_KEY,
            },
            timeout=10,
        )
        data = resp.json()
        email = data.get("data", {}).get("email")
        if email:
            log.info(f"Hunter.io gefunden: {email}")
        return email
    except Exception as e:
        log.warning(f"Hunter.io Fehler: {e}")
        return None


def guess_domain_from_firma(firma: str) -> str:
    """Leitet eine Vermutungs-Domain aus dem Firmennamen ab."""
    cleaned = re.sub(r"\s+(GmbH|AG|KG|SE|UG|e\.V\.|GbR).*$", "", firma, flags=re.IGNORECASE)
    domain = re.sub(r"[^a-zA-Z0-9]", "", cleaned).lower()
    return f"{domain}.de"


def generate_email_patterns(vorname: str, nachname: str, domain: str) -> list[str]:
    """Erzeugt typische E-Mail-Muster für eine Domain."""
    v = vorname.lower()
    n = nachname.lower()
    return [
        f"{v}.{n}@{domain}",
        f"{v[0]}.{n}@{domain}",
        f"{v}@{domain}",
        f"{v}{n}@{domain}",
        f"{v[0]}{n}@{domain}",
        f"info@{domain}",
    ]


def smtp_verify(email: str) -> bool:
    """
    Prüft per SMTP (RCPT TO), ob eine Adresse existiert.
    Kein echter Versand – Verbindung wird nach RCPT TO abgebrochen.
    """
    domain = email.split("@")[1]
    try:
        mx_records = _get_mx(domain)
        if not mx_records:
            return False
        mx_host = mx_records[0]
        with smtplib.SMTP(timeout=10) as smtp:
            smtp.connect(mx_host, 25)
            smtp.helo("verify.local")
            smtp.mail(SMTP_FROM_EMAIL)
            code, _ = smtp.rcpt(email)
            return code == 250
    except Exception:
        return False


def _get_mx(domain: str) -> list[str]:
    """Gibt MX-Records für eine Domain zurück (ohne dnspython)."""
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "MX")
        return sorted(
            [str(r.exchange).rstrip(".") for r in answers],
            key=lambda x: x,
        )
    except ImportError:
        # Fallback ohne dnspython: socket-basierter Trick funktioniert nicht zuverlässig,
        # daher direkt den Domain-Namen als MX-Host versuchen
        return [f"mail.{domain}"]
    except Exception:
        return []


def resolve_email(vorname: str, nachname: str, firma: str) -> tuple[str, bool]:
    """
    Gibt (email, verifiziert) zurück.
    Reihenfolge: Hunter.io → Muster-Generierung + SMTP-Check
    """
    domain = guess_domain_from_firma(firma)

    # 1. Hunter.io
    email = find_email_hunter(vorname, nachname, domain)
    if email:
        verified = smtp_verify(email)
        return email, verified

    # 2. Muster generieren und SMTP-prüfen
    for candidate in generate_email_patterns(vorname, nachname, domain):
        if smtp_verify(candidate):
            log.info(f"Muster-Match: {candidate}")
            return candidate, True

    # 3. Bestes Muster ohne Verifikation zurückgeben
    best_guess = generate_email_patterns(vorname, nachname, domain)[0]
    log.warning(f"Keine verifizierte E-Mail gefunden, Schätzung: {best_guess}")
    return best_guess, False


# ---------------------------------------------------------------------------
# Modul 2 – Personen-Research via Tavily
# ---------------------------------------------------------------------------

def research_person(vorname: str, nachname: str, firma: str) -> str:
    """Führt eine Tavily-Suche durch und gibt eine Zusammenfassung zurück."""
    query = f"{vorname} {nachname} {firma} Rolle Herausforderungen Projekte"
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": True,
            },
            timeout=15,
        )
        data = resp.json()
        answer = data.get("answer", "")
        results = data.get("results", [])
        snippets = " | ".join(r.get("content", "")[:300] for r in results[:3])
        summary = f"{answer}\n\nQuellen-Snippets: {snippets}".strip()
        return summary if summary else "Keine Informationen gefunden."
    except Exception as e:
        log.warning(f"Tavily Fehler für {vorname} {nachname}: {e}")
        return "Research nicht verfügbar."


# ---------------------------------------------------------------------------
# Modul 3 – Google Drive: Software-Beschreibung laden
# ---------------------------------------------------------------------------

def load_software_description() -> str:
    """
    Lädt den Text des Google Docs mit der Software-Beschreibung.
    Benötigt eine Service-Account-JSON-Datei oder lokale Fallback-Datei.
    """
    # Lokaler Fallback (z. B. software_beschreibung.txt)
    local_fallback = Path("software_beschreibung.txt")
    if not Path(GOOGLE_SERVICE_ACCOUNT_FILE).exists():
        if local_fallback.exists():
            log.info("Nutze lokale Software-Beschreibung.")
            return local_fallback.read_text(encoding="utf-8")
        raise FileNotFoundError(
            "Weder Google-Service-Account noch lokale software_beschreibung.txt gefunden."
        )

    try:
        creds = ServiceCredentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/documents.readonly"],
        )
        service = build("docs", "v1", credentials=creds)
        doc = service.documents().get(documentId=GOOGLE_DOC_ID).execute()
        text_parts = []
        for element in doc.get("body", {}).get("content", []):
            para = element.get("paragraph")
            if para:
                for run in para.get("elements", []):
                    text_run = run.get("textRun")
                    if text_run:
                        text_parts.append(text_run.get("content", ""))
        return "".join(text_parts).strip()
    except Exception as e:
        log.error(f"Google Drive Fehler: {e}")
        if local_fallback.exists():
            return local_fallback.read_text(encoding="utf-8")
        raise


# ---------------------------------------------------------------------------
# Modul 4 – E-Mail-Generierung via Claude LLM
# ---------------------------------------------------------------------------

def generate_email(
    vorname: str,
    nachname: str,
    firma: str,
    geschlecht: str,  # "m" oder "w"
    research: str,
    software_description: str,
    client: anthropic.Anthropic,
) -> tuple[str, str]:
    """
    Gibt (betreff, email_text) zurück.
    Sprache: Deutsch. Anrede: formell (Herr/Frau).
    """
    anrede = "Herr" if geschlecht.lower() in ("m", "männlich", "herr") else "Frau"

    system_prompt = (
        "Du bist ein erfahrener B2B-Sales-Experte. "
        "Schreibe hochpersonalisierte, professionelle Kaltakquise-E-Mails auf Deutsch. "
        "Stil: formell, präzise, kein Spam-Sprache, max. 150 Wörter im E-Mail-Körper. "
        "Antworte ausschließlich als JSON mit den Feldern 'betreff' und 'nachricht'."
    )

    user_prompt = f"""
Kontakt-Informationen:
- Name: {anrede} {nachname}
- Vorname: {vorname}
- Firma: {firma}

Research über die Person:
{research}

Beschreibung unserer Software-Lösung:
{software_description}

Aufgabe:
1. Analysiere, welche konkreten Herausforderungen dieser Person unsere Software löst.
2. Schreibe eine personalisierte E-Mail:
   - Beginne zwingend mit: "Sehr geehrte(r) {anrede} {nachname},"
   - Beziehe dich auf einen konkreten Aspekt aus dem Research
   - Erkläre in 2-3 Sätzen, wie unsere Software hilft
   - Schließe mit einer klaren, unverbindlichen Call-to-Action
3. Erstelle einen prägnanten Betreff (max. 8 Wörter)

Antworte NUR als JSON: {{"betreff": "...", "nachricht": "..."}}
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()
    # JSON aus dem Response extrahieren
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        parsed = json.loads(json_match.group())
        return parsed.get("betreff", ""), parsed.get("nachricht", "")

    log.warning("LLM-Antwort konnte nicht als JSON geparst werden.")
    return "", raw


# ---------------------------------------------------------------------------
# Modul 5 – Excel-Export
# ---------------------------------------------------------------------------

def export_to_excel(rows: list[dict], filepath: str) -> None:
    """Speichert die Ergebnisse als .xlsx-Datei."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Outreach"

    headers = [
        "Firma", "Vorname", "Name", "Jobbeschreibung",
        "Email", "Email verifiziert", "Betreff", "Email Nachricht",
    ]
    ws.append(headers)

    # Header-Zeile formatieren
    from openpyxl.styles import Font, PatternFill
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(fill_type="solid", fgColor="2E75B6")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill

    for row in rows:
        ws.append([
            row.get("firma", ""),
            row.get("vorname", ""),
            row.get("nachname", ""),
            row.get("jobbeschreibung", ""),
            row.get("email", ""),
            "Ja" if row.get("email_verifiziert") else "Nein",
            row.get("betreff", ""),
            row.get("email_nachricht", ""),
        ])

    # Spaltenbreiten automatisch anpassen
    for col in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    wb.save(filepath)
    log.info(f"Excel gespeichert: {filepath}")


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def run_outreach(input_csv: str = INPUT_CSV, output_xlsx: str = OUTPUT_XLSX) -> None:
    """Führt den gesamten Outreach-Workflow aus."""

    # Software-Beschreibung einmalig laden
    log.info("Lade Software-Beschreibung aus Google Drive...")
    software_description = load_software_description()

    # Anthropic-Client initialisieren
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    results = []

    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        kontakte = list(reader)

    log.info(f"{len(kontakte)} Kontakte geladen.")

    for i, kontakt in enumerate(kontakte, 1):
        firma = kontakt.get("firma", "").strip()
        vorname = kontakt.get("vorname", "").strip()
        nachname = kontakt.get("nachname", "").strip()
        geschlecht = kontakt.get("geschlecht", "m").strip()  # Standard: männlich

        log.info(f"[{i}/{len(kontakte)}] Verarbeite: {vorname} {nachname} @ {firma}")

        # 1. E-Mail finden
        email, verifiziert = resolve_email(vorname, nachname, firma)

        # 2. Research
        research = research_person(vorname, nachname, firma)

        # 3. E-Mail generieren
        betreff, nachricht = generate_email(
            vorname, nachname, firma, geschlecht,
            research, software_description, client
        )

        results.append({
            "firma": firma,
            "vorname": vorname,
            "nachname": nachname,
            "jobbeschreibung": research[:500],  # Kurzfassung für Excel
            "email": email,
            "email_verifiziert": verifiziert,
            "betreff": betreff,
            "email_nachricht": nachricht,
        })

        # Rate-Limiting: kurze Pause zwischen Kontakten
        time.sleep(1)

    export_to_excel(results, output_xlsx)
    log.info(f"Fertig! {len(results)} Kontakte verarbeitet.")


if __name__ == "__main__":
    run_outreach()
