"""Patient Records API - a small healthcare REST service used for all 3 PBL-III tasks.

Task 1: deployed to Kubernetes by a Jenkins CI/CD pipeline.
Task 2: deployed with a blue-green strategy (APP_COLOR shows which side is live).
Task 3: built/deployed through a DevSecOps pipeline (security headers + audit log here).
"""
import html
import logging
import os
import socket

from flask import Flask, jsonify, request

app = Flask(__name__)

APP_VERSION = os.getenv("APP_VERSION", "dev")
APP_COLOR = os.getenv("APP_COLOR", "none")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
audit = logging.getLogger("audit")

# In-memory store (demo only - a real system would use an encrypted database)
PATIENTS = {
    1: {"id": 1, "name": "Asha Sharma", "age": 34, "ward": "Cardiology"},
    2: {"id": 2, "name": "Rohan Mehta", "age": 52, "ward": "Orthopedics"},
}


@app.after_request
def security_headers(resp):
    # Healthcare data (PHI) must not be cached or framed by other sites
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"
    )
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    return resp


BG_COLORS = {"blue": "#1d4ed8", "green": "#15803d"}

DASHBOARD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="2">
<title>Patient Records System</title>
<style>
  body {{ margin: 0; padding: 32px; background: {bg}; color: #fff;
         font-family: Arial, Helvetica, sans-serif; }}
  h1 {{ margin-top: 0; }}
  .badge {{ display: inline-block; margin: 0 8px 8px 0; padding: 6px 12px;
           border-radius: 999px; background: rgba(255, 255, 255, 0.2); font-weight: bold; }}
  table {{ margin-top: 24px; border-collapse: collapse; background: #fff; color: #111;
          min-width: 480px; }}
  th, td {{ padding: 8px 12px; border: 1px solid #ccc; text-align: left; }}
  th {{ background: #f3f4f6; }}
</style>
</head>
<body>
<h1>Patient Records System</h1>
<span class="badge">Version: {version}</span>
<span class="badge">Environment: {env}</span>
<span class="badge">Pod: {pod}</span>
<table>
<tr><th>ID</th><th>Name</th><th>Age</th><th>Ward</th></tr>
{rows}
</table>
</body>
</html>
"""


def esc(value):
    """Escape a value for HTML output (prevents XSS)."""
    return html.escape(str(value))


@app.get("/")
def dashboard():
    # Simple HTML view for the demo; every value goes through esc()
    rows = "\n".join(
        f"<tr><td>{esc(p['id'])}</td><td>{esc(p['name'])}</td>"
        f"<td>{esc(p['age'])}</td><td>{esc(p['ward'])}</td></tr>"
        for p in PATIENTS.values()
    )
    page = DASHBOARD.format(
        bg=BG_COLORS.get(APP_COLOR, "#0f766e"),
        version=esc(APP_VERSION),
        env=esc("PRODUCTION" if APP_COLOR == "none" else APP_COLOR.upper()),
        pod=esc(socket.gethostname()),
        rows=rows,
    )
    return page, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/api")
def index():
    return jsonify(
        service="patient-records-api",
        version=APP_VERSION,
        color=APP_COLOR,
        pod=socket.gethostname(),  # shows which Kubernetes pod answered
        endpoints=["/", "/api", "/health", "/version", "/patients", "/patients/<id>"],
    )


@app.get("/health")
def health():
    return jsonify(status="ok"), 200


@app.get("/version")
def version():
    return jsonify(version=APP_VERSION, color=APP_COLOR, pod=socket.gethostname())


@app.get("/patients")
def list_patients():
    audit.info("AUDIT action=list_patients client=%s", request.remote_addr)
    return jsonify(list(PATIENTS.values()))


@app.get("/patients/<int:patient_id>")
def get_patient(patient_id):
    audit.info("AUDIT action=read_patient id=%s client=%s", patient_id, request.remote_addr)
    patient = PATIENTS.get(patient_id)
    if patient is None:
        return jsonify(error="patient not found"), 404
    return jsonify(patient)


@app.post("/patients")
def add_patient():
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        return jsonify(error="name is required"), 400
    new_id = max(PATIENTS, default=0) + 1
    patient = {
        "id": new_id,
        "name": data["name"].strip()[:100],
        "age": data.get("age"),
        "ward": str(data.get("ward", "General"))[:50],
    }
    PATIENTS[new_id] = patient
    audit.info("AUDIT action=create_patient id=%s client=%s", new_id, request.remote_addr)
    return jsonify(patient), 201
