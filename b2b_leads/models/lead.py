# models/lead.py
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class EmailStatus(str, Enum):
    VERIFIED = "VERIFIED"      # Öffentlich gefunden
    INFERRED = "INFERRED"      # Aus bestätigtem Muster abgeleitet
    UNKNOWN = "UNKNOWN"        # Nicht bestimmbar


class Priority(str, Enum):
    A = "A"   # Top-Priorität  (Relevanz 4–5)
    B = "B"   # Gut (Relevanz 3)
    C = "C"   # Möglich (Relevanz 1–2)


class Seniority(str, Enum):
    C_LEVEL = "C-Level"
    VP = "VP / Director"
    SENIOR_MANAGER = "Senior Manager"
    MANAGER = "Manager"
    SPECIALIST = "Specialist"
    UNKNOWN = "Unknown"


class Lead(BaseModel):
    # --- Firma ---
    firmenname: str = Field(..., description="Name des Unternehmens")
    domain: Optional[str] = Field(None, description="Domain der Firma")
    land: Optional[str] = Field(None)
    standort: Optional[str] = Field(None)

    # --- Person ---
    vorname: Optional[str] = Field(None)
    nachname: Optional[str] = Field(None)
    vollstaendiger_name: Optional[str] = Field(None)
    jobtitel: Optional[str] = Field(None)
    verantwortung: Optional[str] = Field(None, description="Kurzbeschreibung Verantwortungsbereich")
    senioritaet: Seniority = Field(Seniority.UNKNOWN)
    entscheiderrolle: bool = Field(False, description="Ist die Person Entscheider?")

    # --- Matching ---
    jobprofil_match: Optional[str] = Field(None, description="Gematchtes Ziel-Jobprofil")
    titel_fit_score: float = Field(0.0, ge=0.0, le=1.0)
    verantwortungs_fit_score: float = Field(0.0, ge=0.0, le=1.0)
    senioritaet_score: float = Field(0.0, ge=0.0, le=1.0)
    produkt_relevanz_score: float = Field(0.0, ge=0.0, le=1.0)
    entscheider_naehe_score: float = Field(0.0, ge=0.0, le=1.0)

    # --- Scoring ---
    relevanz: int = Field(0, ge=1, le=5, description="Gesamtrelevanz 1–5")
    relevanz_begruendung: Optional[str] = Field(None)
    prioritaet: Priority = Field(Priority.C)

    # --- Kontakt ---
    email: Optional[str] = Field(None)
    email_status: EmailStatus = Field(EmailStatus.UNKNOWN)
    email_confidence: int = Field(0, ge=0, le=100)
    linkedin_url: Optional[str] = Field(None)

    # --- Quellen ---
    personen_quelle: Optional[str] = Field(None)
    firmen_quelle: Optional[str] = Field(None)

    # --- Meta ---
    notizen: Optional[str] = Field(None)

    def compute_full_name(self) -> str:
        parts = [p for p in [self.vorname, self.nachname] if p]
        return " ".join(parts) if parts else (self.vollstaendiger_name or "")

    def to_export_dict(self) -> dict:
        return {
            "Firmenname": self.firmenname,
            "Domain": self.domain,
            "Vorname": self.vorname,
            "Nachname": self.nachname,
            "Vollständiger_Name": self.vollstaendiger_name or self.compute_full_name(),
            "Jobtitel": self.jobtitel,
            "Jobprofil_Match": self.jobprofil_match,
            "Verantwortung": self.verantwortung,
            "Relevanz_1_bis_5": self.relevanz,
            "Relevanz_Begruendung": self.relevanz_begruendung,
            "Senioritaet": self.senioritaet.value,
            "Entscheiderrolle": "Ja" if self.entscheiderrolle else "Nein",
            "Email": self.email,
            "Email_Status": self.email_status.value,
            "Email_Confidence": self.email_confidence,
            "LinkedIn_URL": self.linkedin_url,
            "Personenquelle": self.personen_quelle,
            "Firmenquelle": self.firmen_quelle,
            "Land": self.land,
            "Standort": self.standort,
            "Prioritaet": self.prioritaet.value,
            "Notizen": self.notizen,
        }
