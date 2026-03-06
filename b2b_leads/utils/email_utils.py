# utils/email_utils.py
"""
Email-Logik:
- VERIFIED:  Öffentlich auf Website/LinkedIn gefunden       → Confidence 90–100
- INFERRED:  Aus bestätigtem Domain-Pattern abgeleitet      → Confidence 70–89
- INFERRED:  Aus schwachem Pattern abgeleitet               → Confidence 40–69
- UNKNOWN:   Kein Pattern ermittelbar                       → Confidence 0–39
"""
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional, List
from ..models.lead import EmailStatus


# Bekannte Domain-Muster für Email-Inferenz
EMAIL_PATTERNS = [
    "{vorname}.{nachname}",      # max.mustermann@
    "{v}{nachname}",             # mmustermann@
    "{vorname}{n}",              # maxm@
    "{vorname}",                 # max@
    "{nachname}",                # mustermann@
    "{vorname}_{nachname}",      # max_mustermann@
    "{nachname}.{vorname}",      # mustermann.max@
]


@dataclass
class EmailPattern:
    pattern_template: str
    confidence: int
    status: EmailStatus
    email: str


def _transliterate(text: str) -> str:
    """Umlaute und Sonderzeichen normalisieren."""
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue",
        "Ä": "ae", "Ö": "oe", "Ü": "ue", "ß": "ss"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    # Weitere Unicode-Zeichen normalisieren
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def _clean_name_part(name: str) -> str:
    """Name für Email vorbereiten: lowercase, nur a-z."""
    name = _transliterate(name.lower().strip())
    return re.sub(r"[^a-z]", "", name)


def infer_email(
    vorname: str,
    nachname: str,
    domain: str,
    verified_emails: Optional[List[str]] = None
) -> EmailPattern:
    """
    Leitet Email-Adresse ab. Priorisiert verifizierte Emails.

    Args:
        vorname: Vorname der Person
        nachname: Nachname der Person
        domain: Domain des Unternehmens (ohne @)
        verified_emails: Öffentlich gefundene Emails dieser Domain

    Returns:
        EmailPattern mit email, status, confidence
    """
    v = _clean_name_part(vorname) if vorname else ""
    n = _clean_name_part(nachname) if nachname else ""
    domain = domain.lower().strip()

    if not (v or n) or not domain:
        return EmailPattern(
            pattern_template="unknown",
            confidence=0,
            status=EmailStatus.UNKNOWN,
            email=""
        )

    # 1. Bereits verifizierte Emails prüfen
    if verified_emails:
        for email in verified_emails:
            if email.lower().endswith(f"@{domain}"):
                local = email.split("@")[0].lower()
                if (v and v in local) or (n and n in local):
                    return EmailPattern(
                        pattern_template="verified_found",
                        confidence=95,
                        status=EmailStatus.VERIFIED,
                        email=email.lower()
                    )

    # 2. Pattern aus verifizierten Emails der Domain ableiten
    detected_pattern = _detect_domain_pattern(domain, verified_emails or [])

    if detected_pattern:
        email = _apply_pattern(detected_pattern, v, n, domain)
        confidence = 78  # Bestätigtes Pattern
        return EmailPattern(
            pattern_template=detected_pattern,
            confidence=confidence,
            status=EmailStatus.INFERRED,
            email=email
        )

    # 3. Häufigstes Pattern als Fallback
    if v and n:
        email = f"{v}.{n}@{domain}"
        return EmailPattern(
            pattern_template="{vorname}.{nachname}",
            confidence=45,
            status=EmailStatus.INFERRED,
            email=email
        )

    return EmailPattern(
        pattern_template="unknown",
        confidence=15,
        status=EmailStatus.UNKNOWN,
        email=""
    )


def _apply_pattern(pattern: str, v: str, n: str, domain: str) -> str:
    """Wendet ein Muster auf Namen an."""
    local = pattern.replace("{vorname}", v)
    local = local.replace("{nachname}", n)
    local = local.replace("{v}", v[0] if v else "")
    local = local.replace("{n}", n[0] if n else "")
    return f"{local}@{domain}"


def _detect_domain_pattern(domain: str, known_emails: List[str]) -> Optional[str]:
    """
    Erkennt das Email-Muster einer Domain anhand bekannter Emails.
    Gibt das erkannte Pattern zurück oder None.
    """
    domain_emails = [e for e in known_emails if e.lower().endswith(f"@{domain}")]
    if not domain_emails:
        return None

    # Vereinfachte Mustererkennung: häufigstes Format
    patterns_found = {}
    for email in domain_emails:
        local = email.split("@")[0].lower()
        if "." in local:
            patterns_found["{vorname}.{nachname}"] = patterns_found.get("{vorname}.{nachname}", 0) + 1
        elif "_" in local:
            patterns_found["{vorname}_{nachname}"] = patterns_found.get("{vorname}_{nachname}", 0) + 1
        elif len(local) > 8:
            patterns_found["{vorname}{nachname}"] = patterns_found.get("{vorname}{nachname}", 0) + 1
        else:
            patterns_found["{v}{nachname}"] = patterns_found.get("{v}{nachname}", 0) + 1

    if patterns_found:
        return max(patterns_found, key=patterns_found.get)
    return None


def validate_email_format(email: str) -> bool:
    """Prüft ob eine Email-Adresse syntaktisch valide ist."""
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))
