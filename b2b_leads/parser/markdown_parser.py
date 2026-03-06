# parser/markdown_parser.py
"""
Parst die Produktkontext-Datei (Markdown).
Extrahiert strukturierte Informationen für Scoring und Matching.
"""
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List
from ..utils.logger import get_logger

logger = get_logger("parser.markdown")


@dataclass
class ProductContext:
    """Strukturierter Produktkontext für Relevanz-Scoring."""
    produktname: str = ""
    beschreibung: str = ""
    zielgruppe_beschreibung: str = ""
    core_keywords: List[str] = field(default_factory=list)
    pain_points: List[str] = field(default_factory=list)
    anwendungsfaelle: List[str] = field(default_factory=list)
    ausschluss_keywords: List[str] = field(default_factory=list)
    branchen: List[str] = field(default_factory=list)
    raw_text: str = ""


def parse_product_context(filepath: str) -> ProductContext:
    """
    Parst eine Produktkontext-Markdown-Datei.

    Die Datei wird nach bekannten Sections durchsucht.
    Unbekannte Abschnitte landen als raw_text.
    """
    path = Path(filepath)
    if not path.exists():
        logger.warning(f"Produktkontext nicht gefunden: {filepath}. Verwende leeren Kontext.")
        return ProductContext()

    text = path.read_text(encoding="utf-8")
    ctx = ProductContext(raw_text=text)

    # Produktname aus erstem H1
    h1 = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if h1:
        ctx.produktname = h1.group(1).strip()

    # Sections extrahieren
    sections = _extract_sections(text)

    for section_title, content in sections.items():
        key = section_title.lower()
        lines = [l.strip().lstrip("- •*").strip() for l in content.split("\n") if l.strip()]

        if any(k in key for k in ["beschreibung", "description", "produkt"]):
            ctx.beschreibung = content.strip()
        elif any(k in key for k in ["zielgruppe", "target", "audience", "persona"]):
            ctx.zielgruppe_beschreibung = content.strip()
        elif any(k in key for k in ["keyword", "suchbegriff", "themen"]):
            ctx.core_keywords = lines
        elif any(k in key for k in ["pain", "problem", "herausforderung", "challenge"]):
            ctx.pain_points = lines
        elif any(k in key for k in ["anwendung", "use case", "einsatz"]):
            ctx.anwendungsfaelle = lines
        elif any(k in key for k in ["ausschluss", "exclusion", "nicht", "kein"]):
            ctx.ausschluss_keywords = lines
        elif any(k in key for k in ["branche", "industrie", "industry", "sektor"]):
            ctx.branchen = lines

    # Fallback: Keywords aus raw_text extrahieren wenn leer
    if not ctx.core_keywords and text:
        ctx.core_keywords = _extract_prominent_keywords(text)

    logger.info(
        f"Produktkontext geladen: '{ctx.produktname}' | "
        f"{len(ctx.core_keywords)} Keywords | {len(ctx.pain_points)} Pain Points"
    )
    return ctx


def _extract_sections(text: str) -> dict:
    """Extrahiert Markdown-Sections als dict {title: content}."""
    sections = {}
    current_title = None
    current_lines = []

    for line in text.split("\n"):
        heading = re.match(r"^#{1,3}\s+(.+)$", line)
        if heading:
            if current_title and current_lines:
                sections[current_title] = "\n".join(current_lines).strip()
            current_title = heading.group(1).strip()
            current_lines = []
        elif current_title:
            current_lines.append(line)

    if current_title and current_lines:
        sections[current_title] = "\n".join(current_lines).strip()

    return sections


def _extract_prominent_keywords(text: str) -> List[str]:
    """Extrahiert Keywords aus Bold/Italic Markdown."""
    bold = re.findall(r"\*\*(.+?)\*\*", text)
    italic = re.findall(r"\*(.+?)\*", text)
    # Bullet-Points
    bullets = re.findall(r"^[-*•]\s+(.+)$", text, re.MULTILINE)
    all_terms = bold + italic + bullets
    return list({t.strip() for t in all_terms if 3 <= len(t.strip()) <= 50})[:30]
