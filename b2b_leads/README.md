# B2B Lead Generation System

Qualifizierte B2B-Leadgenerierung mit Research, Matching, Scoring und Export.

---

## Architektur-Entscheidung: Warum Hybrid?

### TL;DR
**Python-First MVP** + **n8n als optionaler Orchestrierungs-Layer**.

| Szenario | Beste Lösung |
|---|---|
| Nur Trigger, Zeitpläne, simple Webhooks | n8n allein reicht |
| Komplexes Matching, NLP, Custom Scoring | Reines Python |
| Produktion mit Retries, HitL, CRM-Export | **Hybrid ← dieser Use Case** |

### Warum nicht nur n8n?
- Profil-Matching, Senioritäts-Klassifikation, Scoring-Matrix → **nicht in n8n-Nodes abbildbar ohne massiven Overhead**
- Testbarkeit: Python-Logik ist unit-testbar, n8n-Flows nicht
- Typsicherheit: Pydantic-Modelle verhindern stille Datenfehler

### Warum nicht nur Python?
- Zeitpläne, Batch-Steuerung, HitL-Schritte → n8n macht das in 5 Minuten
- CRM-Übergabe (HubSpot, Salesforce), E-Mail-Versand, Slack-Notifications → fertige n8n-Nodes
- Retry-Logik für externe Webhooks → n8n hat das eingebaut

### Hybrid-Architektur

```
┌──────────────────────────────────────────────────────────┐
│                        n8n                               │
│  Trigger → Batch-Steuerung → POST /run → Warte →        │
│  Ergebnis → CRM-Export / Sheets / Slack / Email         │
└─────────────────────────┬────────────────────────────────┘
                          │ JSON (RunConfig)
                          ▼
┌──────────────────────────────────────────────────────────┐
│              Python FastAPI Service                       │
│                                                          │
│  Parser → Research → Matching → Scoring → Export        │
│                                                          │
│  Gibt zurück: RunResult JSON mit Dateipfaden            │
└──────────────────────────────────────────────────────────┘
```

---

## Projektstruktur

```
b2b_leads/
├── main.py                    # CLI Entry Point
├── pipeline.py                # Haupt-Orchestrierung
├── requirements.txt
├── config.yaml.example
│
├── models/                    # Pydantic Datenmodelle
│   ├── lead.py                # Lead, EmailStatus, Priority, Seniority
│   ├── company.py             # Company
│   ├── job_profile.py         # JobProfile
│   └── run_config.py          # RunConfig, RunResult
│
├── parser/                    # Eingabe-Parser
│   ├── csv_parser.py          # Firmen & Jobprofile aus CSV
│   └── markdown_parser.py     # Produktkontext aus Markdown
│
├── research/                  # Öffentliche Recherche
│   ├── web_scraper.py         # requests + BeautifulSoup
│   ├── company_researcher.py  # Firmen-Anreicherung
│   └── person_finder.py       # Personen auf Websites finden
│
├── matching/                  # Profil-Matching
│   └── profile_matcher.py     # Titel-Fit, Senioritäts-Klassifikation
│
├── scoring/                   # Lead-Scoring
│   └── lead_scorer.py         # Relevanz 1-5, Priorität A/B/C
│
├── export/                    # Export-Module
│   └── lead_exporter.py       # CSV, XLSX (farbkodiert), JSON
│
├── utils/                     # Hilfsfunktionen
│   ├── logger.py              # Logging (Console + File)
│   ├── retry.py               # Retry mit exponentiellem Backoff
│   ├── email_utils.py         # Email-Inferenz & VERIFIED/INFERRED/UNKNOWN
│   └── text_utils.py          # Textnormalisierung, Keyword-Matching
│
├── api/                       # FastAPI für n8n-Integration
│   └── app.py                 # POST /run, GET /status, GET /health
│
├── input/                     # Eingabedaten
│   ├── sample_companies.csv
│   ├── sample_job_profiles.csv
│   └── product_context.md
│
├── output/                    # Generierte Exports
│   └── example_leads_output.csv
│
├── data/                      # Zwischenstände (auto-generiert)
└── logs/                      # Log-Dateien (auto-generiert)
```

---

## Installation

```bash
# 1. Verzeichnis
cd b2b_leads

# 2. Virtual Environment
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

# 3. Abhängigkeiten
pip install -r requirements.txt

# 4. Konfiguration
cp config.yaml.example config.yaml
```

---

## Verwendung

### CLI

```bash
# Demo mit Beispieldaten ausführen
python main.py demo

# Standard-Run (liest aus input/)
python main.py run

# Mit eigenen Dateien
python main.py run \
  --companies input/my_companies.csv \
  --job-profiles input/my_profiles.csv \
  --product-context input/my_product.md \
  --run-id "2026-03-06-batch-01"

# Nur Priorität A und B exportieren (Relevanz >= 3)
python main.py run --min-relevanz 3

# FastAPI Server starten
python main.py api
python main.py api --host 127.0.0.1 --port 8080
```

### FastAPI (für n8n-Integration)

```bash
# Server starten
python main.py api

# Health Check
curl http://localhost:8000/health

# Pipeline starten
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "companies_file": "input/companies.csv",
    "job_profiles_file": "input/job_profiles.csv",
    "product_context_file": "input/product_context.md",
    "run_id": "2026-03-06-batch-01"
  }'
```

**Response:**
```json
{
  "run_id": "2026-03-06-batch-01",
  "status": "completed",
  "output_csv": "output/leads_2026-03-06-batch-01.csv",
  "output_xlsx": "output/leads_2026-03-06-batch-01.xlsx",
  "summary_json": "output/summary_2026-03-06-batch-01.json",
  "records": 187,
  "high_priority_records": 42,
  "errors": [],
  "message": "Erfolgreich abgeschlossen in 142.3s. 187 Leads exportiert, 42 Priorität A."
}
```

---

## Eingabe-Formate

### companies.csv
```
name,domain,website,land,standort,branche,mitarbeiterzahl
TechVision GmbH,techvision.de,https://techvision.de,Deutschland,München,Software,250
```

**Pflichtfeld:** `name` (oder `firmenname` / `company`)
**Optional:** alle anderen Spalten

### job_profiles.csv
```
id,bezeichnung,titel_synonyme,verantwortungs_keywords,senioritaet_min,entscheider,gewichtung
head_of_marketing,Head of Marketing,"Head of Marketing;VP Marketing;CMO","marketing;demand generation",VP,ja,1.5
```

**`titel_synonyme` und `verantwortungs_keywords`** werden mit `;` getrennt.

**`senioritaet_min`:** `Specialist | Manager | Senior Manager | VP | C-Level`

### product_context.md
Freies Markdown mit Sections:
- `## Beschreibung`
- `## Core Keywords`
- `## Pain Points`
- `## Zielbranchen`
- `## Ausschluss Keywords`

---

## Scoring-Logik

### Dimensionen

| Dimension | Gewicht | Quelle |
|---|---|---|
| Titel-Fit | 30% | Jobtitel vs. Profil-Synonyme (Jaccard-Ähnlichkeit) |
| Verantwortungs-Fit | 25% | Keywords aus Titel + Beschreibung |
| Seniorität | 20% | Klassifikation aus Jobtitel-Heuristik |
| Produktrelevanz | 15% | Keyword-Überlappung mit Produktkontext |
| Entscheidernähe | 10% | Seniorität + Entscheider-Flag im Profil |

### Relevanz 1–5

| Score | Relevanz | Priorität |
|---|---|---|
| 80–100% | 5 | **A** |
| 65–79% | 4 | **A** |
| 50–64% | 3 | **B** |
| 35–49% | 2 | **C** |
| 0–34% | 1 | **C** |

---

## Email-Logik

| Status | Bedeutung | Confidence |
|---|---|---|
| `VERIFIED` | Öffentlich auf Website/LinkedIn gefunden | 90–100 |
| `INFERRED` | Aus bestätigtem Domain-Pattern abgeleitet | 70–89 |
| `INFERRED` | Aus schwachem Pattern (häufigstes Format) | 40–69 |
| `UNKNOWN` | Kein Pattern ermittelbar | 0–39 |

---

## n8n-Integration

### Beispiel-Workflow (n8n JSON-Struktur)

```
Cron-Trigger (täglich 06:00)
  → HTTP Request Node: POST /run {RunConfig JSON}
  → IF Status = "completed"
    → Ja: Google Sheets Node (output_csv lesen)
    → Ja: Slack Node (high_priority_records melden)
    → Nein: E-Mail Fehler-Notification
```

### Async-Pattern für lange Runs

```
HTTP POST /run/async         → run_id
  → Warte 60s (Wait Node)
  → HTTP GET /status/{run_id}
  → IF status != "completed" → Loop zurück
  → Ergebnis weiterverarbeiten
```

---

## Ausbaupfad (nach MVP)

### Phase 1 (MVP) ✅
- Python-Pipeline mit CSV/XLSX-Export
- FastAPI für n8n-Integration
- Heuristisches Scraping (Website)

### Phase 2
- DuckDB für Lead-Persistierung und Deduplizierung
- LinkedIn-öffentliche Profilsuche (via Google-Suche, kein Login)
- Verbesserte Senioritäts-Klassifikation mit ML

### Phase 3
- Playwright-Fallback für JS-heavy Seiten
- Hunter.io / Snov.io API-Integration (kostenpflichtig, optional)
- n8n-Workflow-Templates für CRM-Übergabe

---

## Annahmen & Limitationen

### Was das System kann
- Öffentlich zugängliche Websites scrapen (Team-Seiten, Impressum, About)
- Schema.org-Markup und Meta-Tags auswerten
- Emails mit Pattern-Matching ableiten (nicht verifizieren)
- Scoring transparent und nachvollziehbar dokumentieren
- Zwischenstände sichern (Resume bei Unterbrechung)

### Was das System nicht kann
- **LinkedIn-Scraping**: Login erforderlich → verboten
- **Email-Verifizierung**: SMTP-Check nicht enthalten (separately per Hunter.io etc.)
- **NLP/KI-basiertes Matching**: MVP nutzt Keyword-Matching (erweiterbar)
- **Vollständige Personenprofile**: Abhängig von öffentlichen Website-Inhalten

### Qualitätserwartung
- Research-Vollständigkeit: ~60–80% der Zielunternehmen (abhängig von Website-Qualität)
- Email-Confidence INFERRED: Muster-basiert, nicht verifiziert
- Scoring-Genauigkeit: Heuristisch, nicht ML-basiert (gezielt anpassbar)
