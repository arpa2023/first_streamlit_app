# export/lead_exporter.py
"""
Lead-Exporter: Exportiert Leads in CSV, XLSX und JSON.

CSV:  Einfacher Export für CRM-Import und Tabellenkalkulation
XLSX: Formatierter Export mit Farbkodierung nach Priorität
JSON: Summary-Export für API und weitere Verarbeitung
"""
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models.lead import Lead, Priority
from ..utils.logger import get_logger

logger = get_logger("export")

# Spaltenreihenfolge für alle Exporte
EXPORT_COLUMNS = [
    "Firmenname", "Domain", "Vorname", "Nachname", "Vollständiger_Name",
    "Jobtitel", "Jobprofil_Match", "Verantwortung", "Relevanz_1_bis_5",
    "Relevanz_Begruendung", "Senioritaet", "Entscheiderrolle",
    "Email", "Email_Status", "Email_Confidence", "LinkedIn_URL",
    "Personenquelle", "Firmenquelle", "Land", "Standort",
    "Prioritaet", "Notizen"
]

# Priorität-Farben für XLSX (RGB)
PRIORITY_COLORS = {
    Priority.A: "C6EFCE",  # Grün
    Priority.B: "FFEB9C",  # Gelb
    Priority.C: "FFCCCC",  # Rot-Rosa
}

HEADER_COLOR = "4472C4"  # Blau


class LeadExporter:
    """Exportiert Lead-Listen in verschiedene Formate."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(
        self,
        leads: List[Lead],
        run_id: str,
        min_relevanz: int = 1,
        export_csv: bool = True,
        export_xlsx: bool = True,
        export_json: bool = True
    ) -> dict:
        """
        Exportiert alle Leads in die gewünschten Formate.

        Returns:
            Dict mit Pfaden zu den erstellten Dateien
        """
        # Leads nach Relevanz filtern
        filtered = [l for l in leads if l.relevanz >= min_relevanz]

        # Sortierung: Priorität A zuerst, dann nach Relevanz absteigend
        filtered.sort(key=lambda x: (-["C","B","A"].index(x.prioritaet.value), -x.relevanz))

        logger.info(f"Export: {len(filtered)} Leads (von {len(leads)} gesamt, min_relevanz={min_relevanz})")

        result = {}

        if export_csv:
            csv_path = self.export_csv(filtered, run_id)
            result["output_csv"] = str(csv_path)

        if export_xlsx:
            xlsx_path = self.export_xlsx(filtered, run_id)
            result["output_xlsx"] = str(xlsx_path)

        if export_json:
            json_path = self.export_summary_json(leads, filtered, run_id)
            result["summary_json"] = str(json_path)

        return result

    def export_csv(self, leads: List[Lead], run_id: str) -> Path:
        """Exportiert Leads als CSV."""
        path = self.output_dir / f"leads_{run_id}.csv"

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for lead in leads:
                writer.writerow(lead.to_export_dict())

        logger.info(f"CSV exportiert: {path} ({len(leads)} Zeilen)")
        return path

    def export_xlsx(self, leads: List[Lead], run_id: str) -> Path:
        """Exportiert Leads als formatiertes XLSX mit Farbkodierung."""
        try:
            import openpyxl
            from openpyxl.styles import (
                PatternFill, Font, Alignment, Border, Side
            )
            from openpyxl.utils import get_column_letter
        except ImportError:
            logger.error("openpyxl nicht installiert. XLSX-Export übersprungen.")
            return None

        path = self.output_dir / f"leads_{run_id}.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "B2B Leads"

        # Header-Styling
        header_fill = PatternFill("solid", fgColor=HEADER_COLOR)
        header_font = Font(bold=True, color="FFFFFF", size=11)
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin")
        )

        # Header schreiben
        for col_idx, col_name in enumerate(EXPORT_COLUMNS, 1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
            cell.border = thin_border

        # Daten schreiben
        for row_idx, lead in enumerate(leads, 2):
            data = lead.to_export_dict()
            priority = lead.prioritaet
            row_fill = PatternFill("solid", fgColor=PRIORITY_COLORS.get(priority, "FFFFFF"))

            for col_idx, col_name in enumerate(EXPORT_COLUMNS, 1):
                value = data.get(col_name, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.fill = row_fill
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                cell.border = thin_border

        # Spaltenbreiten anpassen
        col_widths = {
            "Firmenname": 25, "Domain": 20, "Vorname": 15, "Nachname": 15,
            "Vollständiger_Name": 22, "Jobtitel": 28, "Jobprofil_Match": 22,
            "Verantwortung": 35, "Relevanz_1_bis_5": 10, "Relevanz_Begruendung": 45,
            "Senioritaet": 18, "Entscheiderrolle": 14, "Email": 28,
            "Email_Status": 12, "Email_Confidence": 12, "LinkedIn_URL": 35,
            "Personenquelle": 25, "Firmenquelle": 25, "Land": 12,
            "Standort": 18, "Prioritaet": 10, "Notizen": 30
        }
        for col_idx, col_name in enumerate(EXPORT_COLUMNS, 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = col_widths.get(col_name, 15)

        # Zeile 1 einfrieren (Header sichtbar beim Scrollen)
        ws.freeze_panes = "A2"

        # AutoFilter aktivieren
        ws.auto_filter.ref = f"A1:{get_column_letter(len(EXPORT_COLUMNS))}1"

        wb.save(path)
        logger.info(f"XLSX exportiert: {path} ({len(leads)} Zeilen)")
        return path

    def export_summary_json(
        self,
        all_leads: List[Lead],
        filtered_leads: List[Lead],
        run_id: str
    ) -> Path:
        """Exportiert Summary und alle Leads als JSON."""
        path = self.output_dir / f"summary_{run_id}.json"

        # Statistiken berechnen
        prio_counts = {"A": 0, "B": 0, "C": 0}
        relevanz_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        email_status = {"VERIFIED": 0, "INFERRED": 0, "UNKNOWN": 0}

        for lead in filtered_leads:
            prio_counts[lead.prioritaet.value] += 1
            relevanz_dist[lead.relevanz] += 1
            email_status[lead.email_status.value] += 1

        summary = {
            "run_id": run_id,
            "generated_at": datetime.now().isoformat(),
            "total_leads_researched": len(all_leads),
            "total_leads_exported": len(filtered_leads),
            "high_priority_records": prio_counts["A"],
            "priority_distribution": prio_counts,
            "relevanz_distribution": {str(k): v for k, v in relevanz_dist.items()},
            "email_status_distribution": email_status,
            "top_leads": [
                {
                    "name": l.vollstaendiger_name or f"{l.vorname} {l.nachname}".strip(),
                    "firma": l.firmenname,
                    "jobtitel": l.jobtitel,
                    "relevanz": l.relevanz,
                    "prioritaet": l.prioritaet.value,
                    "email_status": l.email_status.value
                }
                for l in filtered_leads[:20]
            ]
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info(f"Summary JSON exportiert: {path}")
        return path

    def save_intermediate(self, leads: List[Lead], run_id: str, step: str, data_dir: str = "data") -> Path:
        """Speichert Zwischenstand als JSON (für Debugging und Resume)."""
        data_path = Path(data_dir)
        data_path.mkdir(parents=True, exist_ok=True)
        path = data_path / f"{run_id}_{step}.json"

        data = [l.model_dump() for l in leads]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.debug(f"Zwischenstand gespeichert: {path} ({len(leads)} Leads)")
        return path
