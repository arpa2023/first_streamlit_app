# models/__init__.py
from .lead import Lead, EmailStatus, Priority, Seniority
from .company import Company
from .job_profile import JobProfile
from .run_config import RunConfig, RunResult

__all__ = [
    "Lead", "EmailStatus", "Priority", "Seniority",
    "Company", "JobProfile", "RunConfig", "RunResult"
]
