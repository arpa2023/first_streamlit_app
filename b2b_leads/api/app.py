# api/app.py
"""
FastAPI-Service für n8n-Integration.

Endpoint: POST /run
Erwartet JSON:  RunConfig
Gibt zurück:    RunResult

Beispiel-Aufruf:
    curl -X POST http://localhost:8000/run \
      -H "Content-Type: application/json" \
      -d '{
        "companies_file": "input/companies.csv",
        "job_profiles_file": "input/job_profiles.csv",
        "product_context_file": "input/product_context.md",
        "run_id": "2026-03-06-batch-01"
      }'
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

from ..models import RunConfig, RunResult
from ..pipeline import LeadPipeline
from ..utils.logger import get_logger

logger = get_logger("api")

app = FastAPI(
    title="B2B Lead Generation API",
    description="Qualifizierte B2B-Leadgenerierung mit Research, Matching und Scoring",
    version="1.0.0"
)

executor = ThreadPoolExecutor(max_workers=2)
active_runs: dict = {}


@app.get("/health")
def health() -> dict:
    """Health-Check Endpoint."""
    return {"status": "ok", "active_runs": len(active_runs)}


@app.post("/run", response_model=RunResult)
async def run_pipeline(config: RunConfig) -> RunResult:
    """
    Startet die Lead-Generierungs-Pipeline.

    n8n sendet RunConfig JSON, erhält RunResult zurück.
    Bei langen Läufen besser /run/async verwenden.
    """
    logger.info(f"API: Run gestartet - {config.run_id}")

    # Dateien prüfen
    for filepath in [config.companies_file, config.job_profiles_file]:
        if not Path(filepath).exists():
            raise HTTPException(
                status_code=400,
                detail=f"Datei nicht gefunden: {filepath}"
            )

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            _run_sync,
            config
        )
        return result
    except Exception as e:
        logger.error(f"API Fehler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run/async")
async def run_pipeline_async(config: RunConfig, background_tasks: BackgroundTasks) -> dict:
    """
    Startet Pipeline asynchron. Sofortiger Response mit run_id.
    Status abfragen mit GET /status/{run_id}
    """
    run_id = config.run_id
    active_runs[run_id] = {"status": "running", "result": None}
    background_tasks.add_task(_run_background, config, run_id)
    return {"run_id": run_id, "status": "started", "status_url": f"/status/{run_id}"}


@app.get("/status/{run_id}")
def get_status(run_id: str) -> dict:
    """Gibt den Status eines async Runs zurück."""
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' nicht gefunden")
    return active_runs[run_id]


@app.get("/download/{filename}")
def download_file(filename: str):
    """Lädt eine generierte Ausgabedatei herunter."""
    # Security: Nur Dateien aus output/ erlaubt
    safe_name = Path(filename).name
    path = Path("output") / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return FileResponse(str(path), filename=safe_name)


def _run_sync(config: RunConfig) -> RunResult:
    """Synchrone Pipeline-Ausführung (für ThreadPoolExecutor)."""
    pipeline = LeadPipeline(config)
    return pipeline.run()


async def _run_background(config: RunConfig, run_id: str):
    """Hintergrundaufgabe für async Run."""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, _run_sync, config)
        active_runs[run_id] = {
            "status": "completed",
            "result": result.model_dump()
        }
    except Exception as e:
        active_runs[run_id] = {
            "status": "failed",
            "error": str(e)
        }
