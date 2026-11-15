"""CareWell Hospital - Patient Records system used for all 3 PBL-III tasks.

Task 1: deployed to Kubernetes by a Jenkins CI/CD pipeline.
Task 2: deployed with a blue-green strategy (APP_COLOR shows which side is live).
Task 3: built/deployed through a DevSecOps pipeline (security headers + audit log here).

HTML pages are Jinja2 templates in app/templates (autoescape is on for .html, which
prevents XSS). The JSON API (/api, /patients, ...) is unchanged for the pipelines.
"""
import logging
import os
import re
import socket
import threading
from datetime import date

from flask import Flask, jsonify, redirect, render_template, request, url_for

from app.data import (APPOINTMENTS, BLOOD_GROUPS, DOCTORS, GENDERS, PATIENTS, STATUSES,
                      TOTAL_BEDS, WARDS)

app = Flask(__name__)

APP_VERSION = os.getenv("APP_VERSION", "dev")
APP_COLOR = os.getenv("APP_COLOR", "none")
HOSPITAL_NAME = "CareWell Hospital"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
audit = logging.getLogger("audit")

# gunicorn runs threads, so adding a patient (new id + insert) is done under a lock
_lock = threading.Lock()


@app.after_request
def security_headers(resp):
    # Healthcare data (PHI) must not be cached or framed by other sites
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'self'; img-src 'self' data:; "
        "form-action 'self'; frame-ancestors 'none'"
    )
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    return resp


# ---------------------------------------------------------------- helpers

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


@app.template_filter("mask_phone")
def mask_phone(phone):
    """PHI: only show the last 4 digits of a phone number."""
    digits = re.sub(r"\D", "", str(phone or ""))
    return "******" + digits[-4:] if len(digits) >= 4 else "—"


@app.template_filter("nice_date")
def nice_date(value):
    try:
        return date.fromisoformat(value).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return value or "—"


def doctor_name(doctor_id):
    doctor = DOCTORS.get(doctor_id)
    return doctor["name"] if doctor else "Unassigned"


app.jinja_env.globals["doctor_name"] = doctor_name


def patient_name(patient_id):
    patient = PATIENTS.get(patient_id)
    return patient["name"] if patient else "Unknown"


app.jinja_env.globals["patient_name"] = patient_name


def public(patient):
    """Shape used by the JSON API (same fields as before the UI upgrade)."""
    return {k: patient.get(k) for k in ("id", "name", "age", "ward")}


def save_new_patient(fields):
    """Store a new patient with default values for anything not given."""
    with _lock:
        new_id = max(PATIENTS, default=0) + 1
        patient = {
            "id": new_id, "name": "", "age": None, "gender": "", "blood_group": "",
            "phone": "", "ward": "General", "diagnosis": "", "doctor_id": None,
            "status": "Admitted", "admitted": date.today().isoformat(),
            "vitals": {"bp": "—", "pulse": "—", "temp": "—"},
            "visits": [{"date": date.today().isoformat(), "note": "Registered at front desk"}],
        }
        patient.update(fields)
        PATIENTS[new_id] = patient
    audit.info("AUDIT action=create_patient id=%s client=%s", new_id, request.remote_addr)
    return patient


FORM_FIELDS = ["name", "age", "gender", "blood_group", "phone", "ward", "doctor_id",
               "diagnosis", "status"]


def validate_patient_form(form):
    """Server-side validation. Returns (values, errors); errors is empty when valid."""
    v = {f: form.get(f, "").strip() for f in FORM_FIELDS}
    v["phone"] = re.sub(r"[\s-]", "", v["phone"])
    errors = {}

    if not v["name"]:
        errors["name"] = "Name is required."
    elif len(v["name"]) > 100:
        errors["name"] = "Name must be at most 100 characters."
    elif not re.fullmatch(r"[A-Za-z][A-Za-z .'-]*", v["name"]):
        errors["name"] = "Name may only contain letters, spaces, dots, hyphens and apostrophes."

    if not re.fullmatch(r"[0-9]{1,3}", v["age"]) or int(v["age"]) > 120:
        errors["age"] = "Age must be a whole number between 0 and 120."
    if v["gender"] not in GENDERS:
        errors["gender"] = "Choose a gender."
    if v["blood_group"] not in BLOOD_GROUPS:
        errors["blood_group"] = "Choose a valid blood group."
    if not re.fullmatch(r"[6-9][0-9]{9}", v["phone"]):
        errors["phone"] = "Enter a 10-digit Indian mobile number (starts with 6-9)."
    if v["ward"] not in WARDS:
        errors["ward"] = "Choose a ward."
    if not re.fullmatch(r"[0-9]+", v["doctor_id"]) or int(v["doctor_id"]) not in DOCTORS:
        errors["doctor_id"] = "Choose the assigned doctor."
    if not v["diagnosis"]:
        errors["diagnosis"] = "Diagnosis is required."
    elif len(v["diagnosis"]) > 200:
        errors["diagnosis"] = "Diagnosis must be at most 200 characters."
    if v["status"] not in STATUSES:
        errors["status"] = "Choose a status."
    return v, errors


# ---------------------------------------------------------------- HTML pages

@app.get("/")
def dashboard():
    audit.info("AUDIT action=view_dashboard client=%s", request.remote_addr)
    today = date.today().isoformat()
    patients = list(PATIENTS.values())
    todays = sorted((a for a in APPOINTMENTS if a["date"] == today), key=lambda a: a["time"])
    stats = {
        "patients": len(patients),
        "appointments": len(todays),
        "doctors_on_duty": sum(d["availability"] == "On duty" for d in DOCTORS.values()),
        "beds_occupied": sum(p.get("status") != "Discharged" for p in patients),
        "total_beds": TOTAL_BEDS,
    }
    recent = sorted(patients, key=lambda p: (p.get("admitted") or "", p["id"]), reverse=True)[:5]
    return render_template("dashboard.html", active="dashboard", stats=stats,
                           recent=recent, todays=todays)


@app.get("/patients-ui")
def patients_page():
    q = request.args.get("q", "").strip()[:100]
    audit.info("AUDIT action=list_patients_ui client=%s", request.remote_addr)
    patients = list(PATIENTS.values())
    if q:
        needle = q.lower()
        patients = [p for p in patients if needle in " ".join(
            str(p.get(k, "")) for k in ("id", "name", "ward", "diagnosis", "blood_group", "status")
        ).lower()]
    return render_template("patients.html", active="patients", patients=patients, q=q)


@app.route("/patients-ui/new", methods=["GET", "POST"])
def new_patient_page():
    values, errors = {f: "" for f in FORM_FIELDS}, {}
    if request.method == "POST":
        values, errors = validate_patient_form(request.form)
        if not errors:
            fields = dict(values, age=int(values["age"]), doctor_id=int(values["doctor_id"]))
            patient = save_new_patient(fields)
            return redirect(url_for("patient_detail_page", patient_id=patient["id"]), code=303)
    return render_template("patient_form.html", active="new", values=values,
                           errors=errors, wards=WARDS, blood_groups=BLOOD_GROUPS,
                           genders=GENDERS, statuses=STATUSES, doctors=DOCTORS.values()
                           ), 400 if errors else 200


@app.get("/patients-ui/<int:patient_id>")
def patient_detail_page(patient_id):
    audit.info("AUDIT action=view_patient id=%s client=%s", patient_id, request.remote_addr)
    patient = PATIENTS.get(patient_id)
    if patient is None:
        return render_template("not_found.html", active="patients"), 404
    return render_template("patient_detail.html", active="patients", p=patient)


@app.get("/doctors")
def doctors_page():
    return render_template("doctors.html", active="doctors", doctors=DOCTORS.values())


@app.get("/appointments")
def appointments_page():
    audit.info("AUDIT action=list_appointments client=%s", request.remote_addr)
    appts = sorted(APPOINTMENTS, key=lambda a: (a["date"], a["time"]))
    return render_template("appointments.html", active="appointments", appointments=appts)


# ---------------------------------------------------------------- JSON API (unchanged)

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
    return jsonify([public(p) for p in PATIENTS.values()])


@app.get("/patients/<int:patient_id>")
def get_patient(patient_id):
    audit.info("AUDIT action=read_patient id=%s client=%s", patient_id, request.remote_addr)
    patient = PATIENTS.get(patient_id)
    if patient is None:
        return jsonify(error="patient not found"), 404
    return jsonify(public(patient))


@app.post("/patients")
def add_patient():
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        return jsonify(error="name is required"), 400
    patient = save_new_patient({
        "name": data["name"].strip()[:100],
        "age": data.get("age"),
        "ward": str(data.get("ward", "General"))[:50],
    })
    return jsonify(public(patient)), 201
