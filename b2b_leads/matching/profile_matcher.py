# matching/profile_matcher.py
"""
Profil-Matcher: Matched Personen gegen Ziel-Jobprofile.

Scoring-Dimensionen:
- Titel-Fit:        Ähnlichkeit des Jobtitels mit Profil-Synonymen
- Verantwortungs-Fit: Überlappung der Verantwortungs-Keywords
- Seniorität:       Passt die Seniorität zur Mindest-Anforderung
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..models.job_profile import JobProfile
from ..models.lead import Seniority
from ..utils.text_utils import normalize_text, title_similarity, keyword_overlap_score
from ..utils.logger import get_logger

logger = get_logger("matching.profile")


# Senioritäts-Hierarchie (höher = mehr Senior)
SENIORITY_RANK = {
    Seniority.SPECIALIST: 1,
    Seniority.MANAGER: 2,
    Seniority.SENIOR_MANAGER: 3,
    Seniority.VP: 4,
    Seniority.C_LEVEL: 5,
    Seniority.UNKNOWN: 0,
}

# Jobtitel → Seniorität Mapping
SENIORITY_RULES = [
    # C-Level
    (["ceo", "cto", "cfo", "coo", "cmo", "cso", "cpo", "chief", "geschaeftsfuehrer",
      "managing director", "geschäftsführer", "vorstand", "vorstandsmitglied",
      "president", "gründer", "founder", "partner", "principal"], Seniority.C_LEVEL),
    # VP / Director
    (["vp ", "vice president", "director", "head of", "leiter", "leiterin",
      "abteilungsleiter", "bereichsleiter", "gruppenleiter"], Seniority.VP),
    # Senior Manager
    (["senior manager", "senior director", "senior lead", "principal manager",
      "team lead", "teamleiter", "sr. manager", "sr manager"], Seniority.SENIOR_MANAGER),
    # Manager
    (["manager", "projektleiter", "project manager", "program manager",
      "account manager", "product manager", "marketing manager"], Seniority.MANAGER),
    # Specialist
    (["specialist", "expert", "engineer", "consultant", "analyst", "associate",
      "coordinator", "koordinator", "sachbearbeiter", "referent"], Seniority.SPECIALIST),
]


@dataclass
class MatchResult:
    """Ergebnis eines Profil-Matchings."""
    matched_profile: Optional[JobProfile]
    titel_fit: float        # 0.0 – 1.0
    verantwortungs_fit: float  # 0.0 – 1.0
    senioritaet_score: float   # 0.0 – 1.0
    senioritaet: Seniority
    entscheiderrolle: bool
    gesamt_match_score: float  # 0.0 – 1.0


def classify_seniority(jobtitel: str) -> Seniority:
    """Klassifiziert Seniorität anhand des Jobtitels."""
    if not jobtitel:
        return Seniority.UNKNOWN

    title_norm = normalize_text(jobtitel)
    for keywords, seniority in SENIORITY_RULES:
        if any(kw in title_norm for kw in keywords):
            return seniority

    return Seniority.UNKNOWN


def seniority_fit_score(detected: Seniority, required_min: str) -> float:
    """
    Bewertet ob die erkannte Seniorität die Mindestanforderung erfüllt.
    Gibt 0.0–1.0 zurück (1.0 = erfüllt oder übertrifft).
    """
    required_map = {
        "Specialist": Seniority.SPECIALIST,
        "Manager": Seniority.MANAGER,
        "Senior Manager": Seniority.SENIOR_MANAGER,
        "VP": Seniority.VP,
        "VP / Director": Seniority.VP,
        "C-Level": Seniority.C_LEVEL,
    }
    required = required_map.get(required_min, Seniority.MANAGER)

    detected_rank = SENIORITY_RANK.get(detected, 0)
    required_rank = SENIORITY_RANK.get(required, 2)

    if detected_rank == 0:
        return 0.3  # Unbekannte Seniorität: moderate Penalty
    if detected_rank >= required_rank:
        # Bonus für höhere Seniorität (aber nicht zu hoch – C-Level bucht nicht immer selbst)
        over_rank = detected_rank - required_rank
        return min(1.0, 0.85 + (over_rank * 0.05))
    else:
        # Unterhalb der Mindestanforderung
        deficit = required_rank - detected_rank
        return max(0.0, 0.6 - (deficit * 0.2))


class ProfileMatcher:
    """Matched Personen gegen definierte Jobprofile."""

    def __init__(self, profiles: List[JobProfile]):
        self.profiles = profiles

    def match(self, jobtitel: str, beschreibung: str = "") -> MatchResult:
        """
        Findet das beste passende Profil für einen Jobtitel/eine Beschreibung.

        Args:
            jobtitel: Jobtitel der Person
            beschreibung: Optionale Beschreibung des Verantwortungsbereichs

        Returns:
            MatchResult mit dem besten Match
        """
        if not self.profiles:
            seniority = classify_seniority(jobtitel)
            return MatchResult(
                matched_profile=None,
                titel_fit=0.0,
                verantwortungs_fit=0.0,
                senioritaet_score=0.3,
                senioritaet=seniority,
                entscheiderrolle=False,
                gesamt_match_score=0.0
            )

        seniority = classify_seniority(jobtitel)
        best_result = None
        best_score = -1.0

        for profile in self.profiles:
            result = self._match_against_profile(
                jobtitel, beschreibung, seniority, profile
            )
            if result.gesamt_match_score > best_score:
                best_score = result.gesamt_match_score
                best_result = result

        return best_result

    def _match_against_profile(
        self,
        jobtitel: str,
        beschreibung: str,
        seniority: Seniority,
        profile: JobProfile
    ) -> MatchResult:
        """Berechnet Match-Score für ein spezifisches Profil."""

        # 1. Titel-Fit: Direkter Vergleich mit Synonymen
        titel_fit = self._compute_title_fit(jobtitel, profile)

        # 2. Verantwortungs-Fit: Keyword-Überlappung
        verantwortungs_fit = 0.0
        if profile.verantwortungs_keywords:
            combined_text = f"{jobtitel} {beschreibung}"
            verantwortungs_fit = keyword_overlap_score(
                combined_text, profile.verantwortungs_keywords
            )

        # 3. Seniorität
        senioritaet_score = seniority_fit_score(seniority, profile.senioritaet_min)

        # 4. Entscheiderrolle
        is_entscheider = (
            profile.entscheider and
            SENIORITY_RANK.get(seniority, 0) >= SENIORITY_RANK.get(Seniority.MANAGER, 2)
        )

        # Gewichtetes Gesamtergebnis
        weights = {
            "titel": 0.45,
            "verantwortung": 0.30,
            "senioritaet": 0.25,
        }
        gesamt = (
            titel_fit * weights["titel"] +
            verantwortungs_fit * weights["verantwortung"] +
            senioritaet_score * weights["senioritaet"]
        ) * profile.gewichtung

        return MatchResult(
            matched_profile=profile,
            titel_fit=round(titel_fit, 3),
            verantwortungs_fit=round(verantwortungs_fit, 3),
            senioritaet_score=round(senioritaet_score, 3),
            senioritaet=seniority,
            entscheiderrolle=is_entscheider,
            gesamt_match_score=round(min(1.0, gesamt), 3)
        )

    def _compute_title_fit(self, jobtitel: str, profile: JobProfile) -> float:
        """Berechnet Titel-Fit gegen alle Synonyme."""
        if not jobtitel:
            return 0.0

        scores = []
        for synonym in profile.titel_synonyme:
            sim = title_similarity(jobtitel, synonym)
            scores.append(sim)
            # Exact-Match Bonus
            if normalize_text(jobtitel) == normalize_text(synonym):
                return 1.0

        # Teilstring-Check
        jobtitel_norm = normalize_text(jobtitel)
        for synonym in profile.titel_synonyme:
            syn_norm = normalize_text(synonym)
            if syn_norm in jobtitel_norm or jobtitel_norm in syn_norm:
                scores.append(0.85)

        return max(scores) if scores else 0.0
