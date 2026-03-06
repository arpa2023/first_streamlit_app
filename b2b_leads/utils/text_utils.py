# utils/text_utils.py
import re
import unicodedata
from typing import List, Set


def normalize_text(text: str) -> str:
    """Normalisiert Text: lowercase, Leerzeichen, Sonderzeichen."""
    if not text:
        return ""
    text = text.lower().strip()
    # Umlaute
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    # Unicode normalisieren
    nfkd = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    # Sonderzeichen entfernen (außer Leerzeichen und Bindestrich)
    text = re.sub(r"[^\w\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_keywords(text: str, min_length: int = 3) -> Set[str]:
    """Extrahiert relevante Keywords aus Text."""
    if not text:
        return set()
    normalized = normalize_text(text)
    words = normalized.split()
    # Stoppwörter entfernen
    stopwords = {
        "und", "oder", "der", "die", "das", "ein", "eine", "ist", "sind",
        "the", "and", "or", "of", "in", "at", "for", "with", "on", "by",
        "as", "an", "a", "to", "from", "is", "are", "was", "were",
        "de", "du", "le", "la", "les", "un", "une"
    }
    return {w for w in words if len(w) >= min_length and w not in stopwords}


def keyword_overlap_score(text1: str, keywords: List[str]) -> float:
    """
    Berechnet Keyword-Überlappungs-Score zwischen Text und Keywords.
    Gibt Wert zwischen 0.0 und 1.0 zurück.
    """
    if not text1 or not keywords:
        return 0.0

    text_normalized = normalize_text(text1)
    matched = sum(
        1 for kw in keywords
        if normalize_text(kw) in text_normalized
    )
    return min(1.0, matched / len(keywords))


def title_similarity(title1: str, title2: str) -> float:
    """
    Einfache Token-basierte Ähnlichkeit zwischen zwei Jobtiteln.
    Gibt Wert zwischen 0.0 und 1.0 zurück.
    """
    if not title1 or not title2:
        return 0.0

    tokens1 = extract_keywords(title1)
    tokens2 = extract_keywords(title2)

    if not tokens1 or not tokens2:
        return 0.0

    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(intersection) / len(union)  # Jaccard-Ähnlichkeit
