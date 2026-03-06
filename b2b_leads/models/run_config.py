# models/run_config.py
from typing import Optional
from pydantic import BaseModel, Field


class RunConfig(BaseModel):
    companies_file: str = Field(..., description="Pfad zur Unternehmensliste CSV")
    job_profiles_file: str = Field(..., description="Pfad zur Jobprofil-CSV")
    product_context_file: str = Field(..., description="Pfad zur Produktkontext-Markdown")
    run_id: str = Field(..., description="Eindeutige Run-ID z.B. '2026-03-06-batch-01'")
    max_persons_per_company: int = Field(10, ge=1, le=50)
    min_relevanz: int = Field(1, ge=1, le=5, description="Minimale Relevanz für Export")
    export_csv: bool = True
    export_xlsx: bool = True
    export_json: bool = True


class RunResult(BaseModel):
    run_id: str
    status: str = Field("completed")
    output_csv: Optional[str] = None
    output_xlsx: Optional[str] = None
    summary_json: Optional[str] = None
    records: int = 0
    high_priority_records: int = 0
    errors: list = Field(default_factory=list)
    message: str = ""
