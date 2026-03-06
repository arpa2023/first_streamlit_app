# pipeline.py
"""
Haupt-Pipeline: Orchestriert alle Schritte.

Ablauf:
1. Parse Eingabedateien (Firmen, Jobprofile, Produktkontext)
2. Für jede Firma: Website recherchieren, Personen finden
3. Personen gegen Jobprofile matchen
4. Leads scoren (Relevanz + Priorität)
5. Email-Logik anwenden
6. Exportieren (CSV/XLSX/JSON)
7. Zwischenstände sichern
"""
import time
from typing import List, Optional
from pathlib import Path

from .models import Lead, RunConfig, RunResult
from .models.lead import EmailStatus
from .parser import parse_companies_csv, parse_job_profiles_csv, parse_product_context
from .research import CompanyResearcher, PersonFinder, WebScraper
from .matching import ProfileMatcher
from .scoring import LeadScorer
from .export import LeadExporter
from .utils.logger import get_logger
from .utils.email_utils import infer_email, validate_email_format

logger = get_logger("pipeline")


class LeadPipeline:
    """Haupt-Pipeline für B2B-Leadgenerierung."""

    def __init__(self, config: RunConfig):
        self.config = config
        scraper = WebScraper()
        self.company_researcher = CompanyResearcher(scraper)
        self.person_finder = PersonFinder(
            scraper,
            max_persons=config.max_persons_per_company
        )
        self.exporter = LeadExporter(output_dir="output")

    def run(self) -> RunResult:
        """Führt die komplette Pipeline aus."""
        start_time = time.time()
        result = RunResult(run_id=self.config.run_id)
        all_leads: List[Lead] = []

        try:
            logger.info(f"=== Pipeline gestartet: Run {self.config.run_id} ===")

            # 1. Eingaben laden
            companies = parse_companies_csv(self.config.companies_file)
            job_profiles = parse_job_profiles_csv(self.config.job_profiles_file)
            product_ctx = parse_product_context(self.config.product_context_file)

            logger.info(
                f"Geladen: {len(companies)} Firmen | "
                f"{len(job_profiles)} Jobprofile | "
                f"Produkt: '{product_ctx.produktname}'"
            )

            # 2. Matcher und Scorer initialisieren
            matcher = ProfileMatcher(job_profiles)
            scorer = LeadScorer(product_ctx)

            # 3. Pro Firma: Research → Match → Score → Email
            for i, company in enumerate(companies, 1):
                logger.info(f"[{i}/{len(companies)}] Verarbeite: {company.name}")

                try:
                    # Firma anreichern
                    company = self.company_researcher.enrich(company)

                    # Personen finden
                    raw_persons = self.person_finder.find_persons(company)
                    logger.info(f"  → {len(raw_persons)} Personen gefunden")

                    # Domain-Emails sammeln (für Email-Inferenz)
                    domain_emails = [
                        p.email for p in raw_persons
                        if p.email and validate_email_format(p.email)
                    ]

                    for person in raw_persons:
                        try:
                            lead = self._build_lead(
                                person, company, matcher, scorer, domain_emails
                            )
                            all_leads.append(lead)
                        except Exception as e:
                            logger.error(
                                f"Fehler bei Person '{person.name}' "
                                f"({company.name}): {e}"
                            )
                            result.errors.append(str(e))

                except Exception as e:
                    logger.error(f"Fehler bei Firma '{company.name}': {e}")
                    result.errors.append(str(e))
                    continue

                # Zwischenstand sichern (alle 10 Firmen)
                if i % 10 == 0:
                    self.exporter.save_intermediate(
                        all_leads, self.config.run_id, f"step_{i}"
                    )

            logger.info(f"Research abgeschlossen: {len(all_leads)} Leads total")

            # 4. Export
            export_result = self.exporter.export_all(
                all_leads,
                run_id=self.config.run_id,
                min_relevanz=self.config.min_relevanz,
                export_csv=self.config.export_csv,
                export_xlsx=self.config.export_xlsx,
                export_json=self.config.export_json,
            )

            # 5. Ergebnis zusammenstellen
            result.status = "completed"
            result.output_csv = export_result.get("output_csv")
            result.output_xlsx = export_result.get("output_xlsx")
            result.summary_json = export_result.get("summary_json")
            result.records = len([l for l in all_leads if l.relevanz >= self.config.min_relevanz])
            result.high_priority_records = sum(
                1 for l in all_leads if l.prioritaet.value == "A"
            )

            elapsed = time.time() - start_time
            result.message = (
                f"Erfolgreich abgeschlossen in {elapsed:.1f}s. "
                f"{result.records} Leads exportiert, "
                f"{result.high_priority_records} Priorität A."
            )
            logger.info(f"=== Pipeline fertig: {result.message} ===")

        except Exception as e:
            result.status = "failed"
            result.message = str(e)
            logger.error(f"Pipeline fehlgeschlagen: {e}", exc_info=True)

        return result

    def _build_lead(
        self,
        person,
        company,
        matcher: ProfileMatcher,
        scorer: LeadScorer,
        domain_emails: List[str]
    ) -> Lead:
        """Baut ein vollständiges Lead-Objekt aus Roh-Person-Daten."""
        # Lead-Grunddaten
        lead = Lead(
            firmenname=company.name,
            domain=company.domain,
            land=company.land,
            standort=company.standort,
            vorname=person.vorname,
            nachname=person.nachname,
            vollstaendiger_name=person.name,
            jobtitel=person.jobtitel,
            verantwortung=person.zusatzinfo or None,
            linkedin_url=person.linkedin_url or None,
            personen_quelle=person.quelle,
            firmen_quelle=company.quelle,
        )

        # Matching
        match_result = matcher.match(person.jobtitel, person.zusatzinfo or "")

        # Scoring
        lead = scorer.score(lead, match_result)

        # Email-Logik
        lead = self._apply_email_logic(lead, person, company.domain or "", domain_emails)

        return lead

    def _apply_email_logic(
        self,
        lead: Lead,
        person,
        domain: str,
        domain_emails: List[str]
    ) -> Lead:
        """Wendet Email-Logik an: VERIFIED → INFERRED → UNKNOWN."""
        # Direkt gefundene Email prüfen
        if person.email and validate_email_format(person.email):
            lead.email = person.email
            lead.email_status = EmailStatus.VERIFIED
            lead.email_confidence = 92
            return lead

        # Email ableiten
        if lead.vorname and lead.nachname and domain:
            pattern = infer_email(
                lead.vorname,
                lead.nachname,
                domain,
                verified_emails=domain_emails
            )
            if pattern.email and validate_email_format(pattern.email):
                lead.email = pattern.email
                lead.email_status = pattern.status
                lead.email_confidence = pattern.confidence

        return lead
