#!/usr/bin/env python3
"""
OFFLINE DEMO - Funktioniert ohne Internet.
Liest direkt aus den CSV-Dateien und führt Matching + Scoring durch.
Perfekt zum Testen der gesamten Logik ohne Web-Scraping.
"""
import sys
sys.path.insert(0, "/home/user/first_streamlit_app")

from b2b_leads.parser import parse_companies_csv, parse_job_profiles_csv, parse_product_context
from b2b_leads.matching import ProfileMatcher
from b2b_leads.scoring import LeadScorer
from b2b_leads.export import LeadExporter
from b2b_leads.models.lead import Lead, EmailStatus
from b2b_leads.utils.email_utils import infer_email
from b2b_leads.utils.logger import get_logger

logger = get_logger("demo_offline")

# ---------------------------------------------------------------
# Beispiel-Personen (simulieren was ein Web-Scraper finden würde)
# In der echten Nutzung kommen diese von den Firmen-Websites
# ---------------------------------------------------------------
EXAMPLE_PERSONS = {
    "TechVision GmbH": [
        {"name": "Anna Müller",     "jobtitel": "Head of Marketing"},
        {"name": "Klaus Berger",    "jobtitel": "CTO"},
        {"name": "Maria Schmidt",   "jobtitel": "Product Manager"},
    ],
    "DataFlow AG": [
        {"name": "Thomas Weber",    "jobtitel": "VP Sales"},
        {"name": "Sandra Klein",    "jobtitel": "CEO"},
        {"name": "Felix Braun",     "jobtitel": "Marketing Manager"},
    ],
    "CloudBase Ltd": [
        {"name": "Julia Fischer",   "jobtitel": "Head of Sales"},
        {"name": "Peter Koch",      "jobtitel": "Senior Product Manager"},
    ],
    "MarketPro GmbH": [
        {"name": "Stefan Wagner",   "jobtitel": "Founder & CEO"},
        {"name": "Lisa Hoffmann",   "jobtitel": "VP Marketing"},
        {"name": "Max Richter",     "jobtitel": "Sales Director"},
    ],
    "InnoFinance AG": [
        {"name": "Nina Bauer",      "jobtitel": "CMO"},
        {"name": "Robert Schulz",   "jobtitel": "CTO"},
    ],
}


def run_offline_demo():
    print("\n" + "="*65)
    print("  B2B Lead Generation - OFFLINE DEMO")
    print("  (Matching + Scoring ohne Web-Scraping)")
    print("="*65 + "\n")

    # 1. Eingaben laden
    companies  = parse_companies_csv("b2b_leads/input/sample_companies.csv")
    profiles   = parse_job_profiles_csv("b2b_leads/input/sample_job_profiles.csv")
    product    = parse_product_context("b2b_leads/input/product_context.md")

    print(f"Firmen geladen:     {len(companies)}")
    print(f"Jobprofile geladen: {len(profiles)}")
    print(f"Produkt:            {product.produktname}\n")

    # 2. Matcher & Scorer
    matcher = ProfileMatcher(profiles)
    scorer  = LeadScorer(product)
    leads   = []

    # 3. Pro Firma Leads erzeugen
    for company in companies:
        persons = EXAMPLE_PERSONS.get(company.name, [])
        print(f"  {company.name}: {len(persons)} Personen")

        for p in persons:
            parts = p["name"].split(" ", 1)
            vorname  = parts[0]
            nachname = parts[1] if len(parts) > 1 else ""

            lead = Lead(
                firmenname=company.name,
                domain=company.domain,
                land=company.land,
                standort=company.standort,
                vorname=vorname,
                nachname=nachname,
                vollstaendiger_name=p["name"],
                jobtitel=p["jobtitel"],
                firmen_quelle="offline_demo",
                personen_quelle="offline_demo",
            )

            # Matching
            match = matcher.match(p["jobtitel"])

            # Scoring
            lead = scorer.score(lead, match)

            # Email-Inferenz (kein Internet nötig)
            if company.domain:
                ep = infer_email(vorname, nachname, company.domain)
                lead.email = ep.email
                lead.email_status = ep.status
                lead.email_confidence = ep.confidence

            leads.append(lead)

    # 4. Export
    print(f"\n{len(leads)} Leads erstellt. Exportiere...\n")
    exporter = LeadExporter(output_dir="output")
    result   = exporter.export_all(leads, run_id="offline-demo", min_relevanz=1)

    # 5. Ergebnis anzeigen
    print("="*65)
    print("  ERGEBNIS")
    print("="*65)

    # Schöne Tabelle
    print(f"\n{'Name':<22} {'Firma':<18} {'Jobtitel':<25} {'Rel':>3} {'Prio':>4}  Email-Status")
    print("-"*95)
    sorted_leads = sorted(leads, key=lambda x: (-x.relevanz, x.firmenname))
    for l in sorted_leads:
        print(
            f"{l.vollstaendiger_name:<22} "
            f"{l.firmenname:<18} "
            f"{l.jobtitel:<25} "
            f"{l.relevanz:>3} "
            f"{l.prioritaet.value:>4}  "
            f"{l.email_status.value} ({l.email_confidence}%)"
        )

    # Statistik
    prio_a = sum(1 for l in leads if l.prioritaet.value == "A")
    prio_b = sum(1 for l in leads if l.prioritaet.value == "B")
    prio_c = sum(1 for l in leads if l.prioritaet.value == "C")

    print("\n" + "="*65)
    print(f"  Priorität A: {prio_a} Leads   B: {prio_b}   C: {prio_c}")
    print(f"  CSV:  {result.get('output_csv', '-')}")
    print(f"  XLSX: {result.get('output_xlsx', '-')}")
    print(f"  JSON: {result.get('summary_json', '-')}")
    print("="*65 + "\n")


if __name__ == "__main__":
    run_offline_demo()
