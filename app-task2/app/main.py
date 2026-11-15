"""CareWell Hospital - v2 IMPROVED (PBL-III Task 2).

Multi-page hospital dashboard with a sidebar. The coloured top bar comes from APP_COLOR
(blue / green), so during a blue-green release you can see which side is serving you.
/health and /version are used by the Jenkins pipeline (readiness probe + smoke test).
"""
import os
import socket
from datetime import date

from flask import Flask, jsonify, render_template, request

from app.data import APPOINTMENTS, DOCTORS, PATIENTS, TOTAL_BEDS

app = Flask(__name__)

APP_VERSION = os.getenv("APP_VERSION", "dev")
APP_COLOR = os.getenv("APP_COLOR", "none")
HOSPITAL_NAME = "CareWell Hospital"


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'self'; img-src 'self' data:; "
        "form-action 'self'; frame-ancestors 'none'"
    )
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


def env_name():
    return "PRODUCTION" if APP_COLOR not in ("blue", "green") else APP_COLOR.upper()


@app.context_processor
def page_globals():
    # Available in every template: drives the coloured top bar + environment badge
    return {
        "hospital": HOSPITAL_NAME,
        "env_name": env_name(),
        "env_class": "env-" + env_name().lower(),
        "version": APP_VERSION,
        "pod": socket.gethostname(),
    }


@app.template_filter("nice_date")
def nice_date(value):
    try:
        return date.fromisoformat(value).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return value or "—"


def doctor_name(doctor_id):
    doctor = DOCTORS.get(doctor_id)
    return doctor["name"] if doctor else "Unassigned"


def patient_name(patient_id):
    patient = PATIENTS.get(patient_id)
    return patient["name"] if patient else "Unknown"


app.jinja_env.globals.update(doctor_name=doctor_name, patient_name=patient_name)


# ---------------------------------------------------------------- HTML pages

@app.get("/")
def dashboard():
    today = date.today().isoformat()
    patients = list(PATIENTS.values())
    todays = sorted((a for a in APPOINTMENTS if a["date"] == today), key=lambda a: a["time"])
    stats = {
        "patients": len(patients),
        "appointments": len(todays),
        "doctors_on_duty": sum(d["availability"] == "On duty" for d in DOCTORS.values()),
        "beds_occupied": sum(p["status"] != "Discharged" for p in patients),
        "total_beds": TOTAL_BEDS,
    }
    recent = sorted(patients, key=lambda p: (p["admitted"], p["id"]), reverse=True)[:5]
    return render_template("dashboard.html", active="dashboard", stats=stats,
                           recent=recent, todays=todays)


@app.get("/patients")
def patients_page():
    q = request.args.get("q", "").strip()[:100]
    patients = list(PATIENTS.values())
    if q:
        needle = q.lower()
        patients = [p for p in patients if needle in " ".join(
            str(p[k]) for k in ("id", "name", "ward", "diagnosis", "blood_group", "status")
        ).lower()]
    return render_template("patients.html", active="patients", patients=patients, q=q)


@app.get("/doctors")
def doctors_page():
    return render_template("doctors.html", active="doctors", doctors=DOCTORS.values())


@app.get("/appointments")
def appointments_page():
    appts = sorted(APPOINTMENTS, key=lambda a: (a["date"], a["time"]))
    return render_template("appointments.html", active="appointments", appointments=appts)


# ---------------------------------------------------------------- used by the pipeline

@app.get("/health")
def health():
    return jsonify(status="ok"), 200


@app.get("/version")
def version():
    return jsonify(version=APP_VERSION, color=APP_COLOR, pod=socket.gethostname())
