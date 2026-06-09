"""Controlador Flask. Rutas delgadas; lógica en services/."""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import uuid

from flask import Flask, Response, render_template, request, send_file

from src.export.excel_exporter import export_to_excel
from src.services.analysis_service import run_analysis
from src.sources.local_source import LocalSource


def _resource_path(relative: str) -> str:
    """Resuelve rutas de recursos tanto en desarrollo como en ejecutable bundled."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


app = Flask(
    __name__,
    template_folder=_resource_path("templates"),
    static_folder=_resource_path("static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

# ── Estado global del proceso ────────────────────────────────────────────────
_TEMP_DIR: str | None = None
_RESULTADO = None          # último ResultadoAuditoria completado (para /exportar)
_JOBS: dict[str, dict] = {}  # job_id → estado del análisis en curso


# ── Index ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ── Analizar (POST → inicia hilo + devuelve job_id JSON) ─────────────────────
@app.route("/analizar", methods=["POST"])
def analizar():
    global _TEMP_DIR

    archivos = request.files.getlist("archivos")
    if not archivos or all(f.filename == "" for f in archivos):
        return {"error": "No se seleccionaron archivos."}, 400

    # Limpiar directorio temporal anterior
    if _TEMP_DIR and os.path.exists(_TEMP_DIR):
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)
    _TEMP_DIR = tempfile.mkdtemp(prefix="auditoria_")

    for f in archivos:
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            continue
        ruta = os.path.join(_TEMP_DIR, _sanitize_path(f.filename))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        f.save(ruta)

    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {
        "status": "starting",
        "n_done": 0,
        "n_total": 0,
        "current": "",
        "students": [],   # [{name, curso, state}]  state: pending|active|done
        "error": None,
        "cancelado": False,
    }

    temp_dir = _TEMP_DIR
    threading.Thread(target=_run_job, args=(job_id, temp_dir), daemon=True).start()
    return {"job_id": job_id}


def _run_job(job_id: str, temp_dir: str) -> None:
    global _RESULTADO
    job = _JOBS[job_id]
    progress_lock = threading.Lock()

    try:
        source = LocalSource(temp_dir)
        folders = source.list_student_folders()
        n_total = len(folders)

        job["n_total"] = n_total
        job["status"] = "running"
        job["students"] = [
            {"name": f.name, "curso": f.curso, "state": "pending"}
            for f in folders
        ]

        def on_progress(event: str, name: str, n_done: int, n_total: int) -> None:
            with progress_lock:
                job["n_done"] = n_done
                if event == "start":
                    for s in job["students"]:
                        if s["name"] == name:
                            s["state"] = "active"
                            break
                else:  # "done"
                    for s in job["students"]:
                        if s["name"] == name:
                            s["state"] = "done"
                            break
                # Mostrar uno de los alumnos activos como "current"
                activos = [s["name"] for s in job["students"] if s["state"] == "active"]
                job["current"] = activos[0] if activos else ""

        resultado = run_analysis(
            source,
            on_progress=on_progress,
            cancelado=lambda: _JOBS.get(job_id, {}).get("cancelado", False),
        )

        with progress_lock:
            for s in job["students"]:
                s["state"] = "done"
            job["n_done"] = n_total
            job["current"] = ""
            job["status"] = "done"
        _RESULTADO = resultado

    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)


# ── SSE: progreso del análisis ────────────────────────────────────────────────
@app.route("/progresso/<job_id>")
def progresso(job_id: str):
    def generate():
        while True:
            job = _JOBS.get(job_id)
            if not job:
                yield f"data: {json.dumps({'status': 'error', 'error': 'Job no encontrado'})}\n\n"
                return

            payload = {
                "status":   job["status"],
                "n_done":   job["n_done"],
                "n_total":  job["n_total"],
                "current":  job["current"],
                "students": job["students"],
                "error":    job["error"],
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            if job["status"] in ("done", "error"):
                return

            time.sleep(0.4)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Cancelar análisis en curso ────────────────────────────────────────────────
@app.route("/cancelar/<job_id>", methods=["POST"])
def cancelar(job_id: str):
    job = _JOBS.get(job_id)
    if job:
        job["cancelado"] = True
        job["status"] = "cancelled"
    return {"ok": True}


# ── Cerrar aplicación ─────────────────────────────────────────────────────────
@app.route("/shutdown", methods=["POST"])
def shutdown():
    def _exit():
        time.sleep(0.4)
        os._exit(0)
    threading.Thread(target=_exit, daemon=True).start()
    return {"ok": True}


# ── Resultado ─────────────────────────────────────────────────────────────────
@app.route("/resultado/<job_id>")
def resultado(job_id: str):
    global _RESULTADO
    job = _JOBS.get(job_id)
    if not job or job["status"] != "done":
        return render_template("index.html", error="Resultado no disponible. Analiza de nuevo.")
    _RESULTADO = job.get("resultado") or _RESULTADO
    return render_template("resultado.html", resultado=_RESULTADO)


# ── Exportar Excel ────────────────────────────────────────────────────────────
@app.route("/exportar")
def exportar():
    if _RESULTADO is None:
        return render_template("index.html", error="No hay análisis disponible. Analiza primero.")
    export_dir = _TEMP_DIR or tempfile.gettempdir()
    ruta_xlsx = export_to_excel(_RESULTADO, export_dir)
    return send_file(
        ruta_xlsx,
        as_attachment=True,
        download_name=os.path.basename(ruta_xlsx),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────
def _sanitize_path(filename: str) -> str:
    parts = filename.replace("\\", "/").split("/")
    safe = [p for p in parts if p and p != ".."]
    return os.path.join(*safe) if safe else "archivo.pdf"


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
