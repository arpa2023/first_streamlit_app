# models/job_profile.py
from typing import List
from pydantic import BaseModel, Field


class JobProfile(BaseModel):
    id: str = Field(..., description="Eindeutiger Bezeichner z.B. 'head_of_marketing'")
    bezeichnung: str = Field(..., description="Lesbarer Name des Jobprofils")
    titel_synonyme: List[str] = Field(
        default_factory=list,
        description="Akzeptierte Jobtitel (case-insensitiv)"
    )
    verantwortungs_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords die auf Verantwortungsbereich hinweisen"
    )
    senioritaet_min: str = Field(
        "Manager",
        description="Minimale Seniorität: Specialist | Manager | Senior Manager | VP | C-Level"
    )
    entscheider: bool = Field(
        False,
        description="Ist dieses Profil typischerweise ein Entscheider?"
    )
    gewichtung: float = Field(
        1.0,
        ge=0.1,
        le=2.0,
        description="Gewichtungsfaktor für Scoring (höher = wichtiger)"
    )
    notizen: str = Field("", description="Freitext-Anmerkungen")
