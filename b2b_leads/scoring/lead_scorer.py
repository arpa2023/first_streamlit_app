# scoring/lead_scorer.py
"""
Lead-Scorer: Berechnet Gesamtrelevanz, Priorität und Begründung.

Scoring-Matrix:
┌────────────────────┬──────────┬─────────────────────────────────────────┐
│ Dimension          │ Gewicht  │ Beschreibung                            │
├────────────────────┼──────────┼─────────────────────────────────────────┤
│ Titel-Fit          │  30%     │ Wie gut passt der Titel zum Profil?     │
│ Verantwortungs-Fit │  25%     │ Keywords aus Verantwortungsbereich      │
│ Seniorität         │  20%     │ Mindest-Seniorität erfüllt?             │
│ Produktrelevanz    │  15%     │ Bezug zum Produktkontext                │
│ Entscheidernähe    │  10%     │ Ist die Person Entscheider?             │
└────────────────────┴──────────┴─────────────────────────────────────────┘

Gesamtrelevanz → 1–5:
  0.80–1.00 → 5 (Top-Priorität A)
  0.65–0.79 → 4 (Priorität A)
  0.50–0.64 → 3 (Priorität B)
  0.35–0.49 → 2 (Priorität C)
  0.00–0.34 → 1 (Priorität C)
"""
from typing import List, Optional

from ..models.lead import Lead, Priority, Seniority
from ..matching.profile_matcher import MatchResult, SENIORITY_RANK
from ..parser.markdown_parser import ProductContext
from ..utils.text_utils import keyword_overlap_score
from ..utils.logger import get_logger

logger = get_logger("scoring.lead")

# Gewichtungsmatrix
WEIGHTS = {
    "titel_fit": 0.30,
    "verantwortungs_fit": 0.25,
    "senioritaet": 0.20,
    "produkt_relevanz": 0.15,
    "entscheider_naehe": 0.10,
}

# Score → Relevanz 1–5
RELEVANZ_THRESHOLDS = [
    (0.80, 5),
    (0.65, 4),
    (0.50, 3),
    (0.35, 2),
    (0.00, 1),
]

# Relevanz → Priorität
PRIORITY_MAP = {5: Priority.A, 4: Priority.A, 3: Priority.B, 2: Priority.C, 1: Priority.C}


class LeadScorer:
    """Bewertet Leads und schreibt Scoring-Daten zurück."""

    def __init__(self, product_context: Optional[ProductContext] = None):
        self.product_context = product_context

    def score(self, lead: Lead, match_result: MatchResult) -> Lead:
        """
        Berechnet alle Scores für einen Lead und schreibt sie zurück.

        Args:
            lead: Lead-Objekt (wird in-place modifiziert)
            match_result: Ergebnis des Profil-Matchings

        Returns:
            Modifiziertes Lead-Objekt
        """
        # Matching-Scores übernehmen
        lead.titel_fit_score = match_result.titel_fit
        lead.verantwortungs_fit_score = match_result.verantwortungs_fit
        lead.senioritaet_score = match_result.senioritaet_score
        lead.senioritaet = match_result.senioritaet
        lead.entscheiderrolle = match_result.entscheiderrolle

        if match_result.matched_profile:
            lead.jobprofil_match = match_result.matched_profile.bezeichnung

        # Produktrelevanz berechnen
        lead.produkt_relevanz_score = self._compute_product_relevance(lead)

        # Entscheidernähe
        lead.entscheider_naehe_score = self._compute_entscheider_naehe(lead, match_result)

        # Gewichteter Gesamtscore
        raw_score = (
            lead.titel_fit_score * WEIGHTS["titel_fit"] +
            lead.verantwortungs_fit_score * WEIGHTS["verantwortungs_fit"] +
            lead.senioritaet_score * WEIGHTS["senioritaet"] +
            lead.produkt_relevanz_score * WEIGHTS["produkt_relevanz"] +
            lead.entscheider_naehe_score * WEIGHTS["entscheider_naehe"]
        )

        # Relevanz 1–5
        lead.relevanz = self._score_to_relevanz(raw_score)
        lead.prioritaet = PRIORITY_MAP[lead.relevanz]
        lead.relevanz_begruendung = self._generate_begruendung(lead, raw_score)

        logger.debug(
            f"{lead.vollstaendiger_name or lead.jobtitel}: "
            f"Score={raw_score:.2f} → Relevanz={lead.relevanz} ({lead.prioritaet})"
        )

        return lead

    def _compute_product_relevance(self, lead: Lead) -> float:
        """Berechnet Produktrelevanz anhand des Produktkontexts."""
        if not self.product_context:
            return 0.5  # Neutral wenn kein Kontext

        keywords = self.product_context.core_keywords
        if not keywords:
            return 0.5

        # Text der Person für Matching
        person_text = " ".join(filter(None, [
            lead.jobtitel,
            lead.verantwortung,
            lead.jobprofil_match
        ]))

        if not person_text:
            return 0.3

        score = keyword_overlap_score(person_text, keywords)

        # Ausschluss-Keywords penalty
        if self.product_context.ausschluss_keywords:
            exclusion_hit = keyword_overlap_score(
                person_text, self.product_context.ausschluss_keywords
            )
            score = max(0.0, score - exclusion_hit * 0.5)

        return round(score, 3)

    def _compute_entscheider_naehe(self, lead: Lead, match_result: MatchResult) -> float:
        """Bewertet die Entscheidernähe."""
        seniority_rank = SENIORITY_RANK.get(lead.senioritaet, 0)

        if lead.entscheiderrolle and seniority_rank >= 4:  # VP oder höher
            return 1.0
        elif lead.entscheiderrolle and seniority_rank >= 3:  # Senior Manager
            return 0.85
        elif seniority_rank >= 4:  # VP ohne explizite Entscheiderrolle
            return 0.75
        elif seniority_rank >= 3:  # Senior Manager
            return 0.60
        elif seniority_rank >= 2:  # Manager
            return 0.45
        elif seniority_rank >= 1:  # Specialist
            return 0.25
        else:
            return 0.15

    @staticmethod
    def _score_to_relevanz(score: float) -> int:
        """Konvertiert kontinuierlichen Score zu Relevanz 1–5."""
        for threshold, relevanz in RELEVANZ_THRESHOLDS:
            if score >= threshold:
                return relevanz
        return 1

    def _generate_begruendung(self, lead: Lead, raw_score: float) -> str:
        """Erstellt lesbare Begründung für das Scoring."""
        parts = []

        # Stärken
        if lead.titel_fit_score >= 0.7:
            parts.append(f"Titel passt gut zu '{lead.jobprofil_match}'")
        elif lead.titel_fit_score >= 0.4:
            parts.append(f"Titel teilweise relevant")
        else:
            parts.append(f"Titel-Match schwach")

        if lead.senioritaet != Seniority.UNKNOWN:
            parts.append(f"Seniorität: {lead.senioritaet.value}")

        if lead.entscheiderrolle:
            parts.append("Entscheiderrolle bestätigt")

        if lead.produkt_relevanz_score >= 0.6:
            parts.append("Hohe Produktrelevanz")
        elif lead.produkt_relevanz_score >= 0.3:
            parts.append("Mittlere Produktrelevanz")

        if lead.verantwortungs_fit_score >= 0.5:
            parts.append("Verantwortungsbereich trifft Zielthemen")

        parts.append(f"Gesamtscore: {raw_score:.0%}")
        return " | ".join(parts)
