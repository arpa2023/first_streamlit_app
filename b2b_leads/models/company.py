# models/company.py
from typing import Optional, List
from pydantic import BaseModel, Field


class Company(BaseModel):
    name: str
    domain: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    land: Optional[str] = None
    standort: Optional[str] = None
    branche: Optional[str] = None
    beschreibung: Optional[str] = None
    mitarbeiterzahl: Optional[str] = None
    technologien: List[str] = Field(default_factory=list)
    quelle: Optional[str] = None
    rohdaten: dict = Field(default_factory=dict)
