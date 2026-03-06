#!/usr/bin/env python3
# main.py
"""
B2B Lead Generation - CLI Entry Point

Verwendung:
    python main.py --help
    python main.py run
    python main.py run --companies input/companies.csv
    python main.py run --run-id "2026-03-06-batch-01"
    python main.py api  (startet FastAPI Server)
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime


def cmd_run(args):
    """Startet die Lead-Pipeline."""
    from b2b_leads.models import RunConfig
    from b2b_leads.pipeline import LeadPipeline
    from b2b_leads.utils.logger import get_logger

    logger = get_logger("main")

    run_id = args.run_id or f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

    config = RunConfig(
        companies_file=args.companies,
        job_profiles_file=args.job_profiles,
        product_context_file=args.product_context,
        run_id=run_id,
        max_persons_per_company=args.max_persons,
        min_relevanz=args.min_relevanz,
        export_csv=not args.no_csv,
        export_xlsx=not args.no_xlsx,
        export_json=not args.no_json,
    )

    logger.info(f"Starte Pipeline: Run-ID '{run_id}'")
    pipeline = LeadPipeline(config)
    result = pipeline.run()

    # Ergebnis ausgeben
    print("\n" + "="*60)
    print(f"  B2B Lead Pipeline - Ergebnis")
    print("="*60)
    print(f"  Run-ID:           {result.run_id}")
    print(f"  Status:           {result.status}")
    print(f"  Leads exportiert: {result.records}")
    print(f"  Priorität A:      {result.high_priority_records}")
    if result.output_csv:
        print(f"  CSV:              {result.output_csv}")
    if result.output_xlsx:
        print(f"  XLSX:             {result.output_xlsx}")
    if result.summary_json:
        print(f"  Summary JSON:     {result.summary_json}")
    if result.errors:
        print(f"  Fehler:           {len(result.errors)}")
    print("="*60)
    print(f"  {result.message}")
    print("="*60 + "\n")

    return 0 if result.status == "completed" else 1


def cmd_api(args):
    """Startet den FastAPI-Server."""
    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn nicht installiert. Bitte: pip install uvicorn")
        return 1

    print(f"Starte FastAPI auf http://{args.host}:{args.port}")
    print(f"Docs:   http://{args.host}:{args.port}/docs")
    print(f"Health: http://{args.host}:{args.port}/health")

    import uvicorn
    uvicorn.run(
        "b2b_leads.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )
    return 0


def cmd_demo(args):
    """Erstellt Demo-Eingabedateien und führt Beispiel-Run aus."""
    from b2b_leads.utils.logger import get_logger
    logger = get_logger("demo")

    print("Erstelle Demo-Eingabedateien...")

    # Demo-Dateien kopieren falls vorhanden
    input_dir = Path("input")
    input_dir.mkdir(exist_ok=True)

    sample_companies = Path("input/sample_companies.csv")
    sample_profiles = Path("input/sample_job_profiles.csv")
    sample_product = Path("input/product_context.md")

    if not sample_companies.exists():
        print("  Erstelle input/sample_companies.csv ...")
        _create_demo_companies(sample_companies)

    if not sample_profiles.exists():
        print("  Erstelle input/sample_job_profiles.csv ...")
        _create_demo_profiles(sample_profiles)

    if not sample_product.exists():
        print("  Erstelle input/product_context.md ...")
        _create_demo_product_context(sample_product)

    print("Demo-Dateien erstellt. Starte Demo-Run...")

    # Argparse-Namespace für run
    import argparse
    run_args = argparse.Namespace(
        companies="input/sample_companies.csv",
        job_profiles="input/sample_job_profiles.csv",
        product_context="input/product_context.md",
        run_id="demo-run",
        max_persons=5,
        min_relevanz=1,
        no_csv=False,
        no_xlsx=False,
        no_json=False,
    )
    return cmd_run(run_args)


def _create_demo_companies(path: Path):
    content = """name,domain,website,land,standort,branche,mitarbeiterzahl
TechVision GmbH,techvision.de,https://techvision.de,Deutschland,München,Software,250
DataFlow AG,dataflow.ch,https://dataflow.ch,Schweiz,Zürich,Analytics,120
CloudBase Ltd,cloudbase.io,https://cloudbase.io,Deutschland,Berlin,Cloud,80
MarketPro GmbH,marketpro.de,https://marketpro.de,Deutschland,Hamburg,Marketing,320
InnoFinance AG,innofinance.at,https://innofinance.at,Österreich,Wien,Fintech,150
"""
    path.write_text(content, encoding="utf-8")


def _create_demo_profiles(path: Path):
    content = """id,bezeichnung,titel_synonyme,verantwortungs_keywords,senioritaet_min,entscheider,gewichtung
head_of_marketing,Head of Marketing,"Head of Marketing;VP Marketing;Marketing Director;CMO;Marketingleiter","marketing;demand generation;lead generation;brand;campaign;digital marketing",VP,ja,1.5
sales_director,Sales Director,"Sales Director;Head of Sales;VP Sales;CSO;Vertriebsleiter","sales;revenue;pipeline;business development;key account;b2b sales",VP,ja,1.8
cto_vp_tech,CTO / VP Technology,"CTO;VP Engineering;Head of Technology;Technologieleiter;IT-Leiter","technology;engineering;software;infrastructure;cloud;digitalisierung",VP,ja,1.6
product_manager,Product Manager,"Product Manager;Head of Product;CPO;Produktmanager","product;roadmap;features;user stories;product strategy;ux",Manager,nein,1.2
ceo_founder,CEO / Founder,"CEO;Founder;Gründer;Geschäftsführer;Managing Director","strategy;growth;fundraising;vision;leadership",C-Level,ja,2.0
"""
    path.write_text(content, encoding="utf-8")


def _create_demo_product_context(path: Path):
    content = """# B2B SaaS Plattform für Marketing-Automatisierung

## Beschreibung
Unsere Plattform automatisiert B2B-Marketing-Workflows und verbindet
CRM, E-Mail-Marketing und Lead-Scoring in einer einheitlichen Lösung.

## Zielgruppe
Mittelständische B2B-Unternehmen (50–500 Mitarbeiter) in der DACH-Region,
die ihre Marketing-Effizienz steigern und qualifizierte Leads generieren wollen.

## Core Keywords
- Marketing Automatisierung
- Lead Scoring
- CRM Integration
- E-Mail Marketing
- Demand Generation
- B2B SaaS
- Marketing ROI
- Pipeline Management

## Pain Points (Kundenproblem)
- Manuelle Marketing-Prozesse kosten zu viel Zeit
- Unklarer ROI von Marketing-Aktivitäten
- Schlechte Abstimmung zwischen Marketing und Sales
- Fehlende Personalisierung in der Kundenkommunikation

## Anwendungsfälle
- Automatisierte Lead-Nurturing-Kampagnen
- Lead-Scoring und Qualifizierung
- CRM-Synchronisation mit HubSpot/Salesforce
- Multi-Channel-Kampagnen (E-Mail, LinkedIn, Ads)

## Zielbranchen
- Software / SaaS
- Fintech
- Professional Services
- IT-Beratung
- E-Commerce B2B

## Ausschluss Keywords
- B2C
- Einzelhandel
- stationärer Handel
- Gastronomie
"""
    path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="B2B Lead Generation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python main.py run                           # Mit Standardpfaden
  python main.py run --companies input/my_companies.csv
  python main.py run --min-relevanz 3          # Nur Relevanz 3+
  python main.py api                           # FastAPI Server starten
  python main.py demo                          # Demo mit Beispieldaten
        """
    )
    subparsers = parser.add_subparsers(dest="command", help="Befehl")

    # --- run ---
    run_parser = subparsers.add_parser("run", help="Pipeline ausführen")
    run_parser.add_argument(
        "--companies", default="input/companies.csv",
        help="Pfad zur Unternehmensliste CSV (default: input/companies.csv)"
    )
    run_parser.add_argument(
        "--job-profiles", default="input/job_profiles.csv",
        dest="job_profiles",
        help="Pfad zur Jobprofil-CSV (default: input/job_profiles.csv)"
    )
    run_parser.add_argument(
        "--product-context", default="input/product_context.md",
        dest="product_context",
        help="Pfad zur Produktkontext-Markdown (default: input/product_context.md)"
    )
    run_parser.add_argument(
        "--run-id", default=None, dest="run_id",
        help="Run-ID (default: Zeitstempel)"
    )
    run_parser.add_argument(
        "--max-persons", type=int, default=10, dest="max_persons",
        help="Maximale Personen pro Firma (default: 10)"
    )
    run_parser.add_argument(
        "--min-relevanz", type=int, default=1, dest="min_relevanz",
        help="Minimale Relevanz für Export 1-5 (default: 1)"
    )
    run_parser.add_argument("--no-csv", action="store_true", help="CSV-Export deaktivieren")
    run_parser.add_argument("--no-xlsx", action="store_true", help="XLSX-Export deaktivieren")
    run_parser.add_argument("--no-json", action="store_true", help="JSON-Export deaktivieren")

    # --- api ---
    api_parser = subparsers.add_parser("api", help="FastAPI Server starten")
    api_parser.add_argument("--host", default="0.0.0.0")
    api_parser.add_argument("--port", type=int, default=8000)
    api_parser.add_argument("--reload", action="store_true", help="Auto-Reload (dev)")

    # --- demo ---
    subparsers.add_parser("demo", help="Demo mit Beispieldaten ausführen")

    args = parser.parse_args()

    if args.command == "run":
        sys.exit(cmd_run(args))
    elif args.command == "api":
        sys.exit(cmd_api(args))
    elif args.command == "demo":
        sys.exit(cmd_demo(args))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
