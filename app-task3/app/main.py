"""CareWell Hospital - v3 SECURE EDITION (PBL-III Task 3, DevSecOps).

Everything from v2 plus: patient detail page (vitals status cards, allergies, emergency
contact, visit timeline), add-patient form with server-side validation and a CSRF token,
phone masking (PHI), status filters, ward occupancy, critical-patient alerts, an in-memory
audit log (/audit) next to the AUDIT log lines, and a Security Center (/security).

HTML pages are Jinja2 templates in app/templates (autoescape is on for .html, which
prevents XSS). No JavaScript and no external CDNs, so the strict CSP stays as it is.
The JSON API (/api, /health, /version, /patients, ...) is unchanged for the pipelines.
"""
import hmac
import logging
import os
import re
import secrets
import socket
import threading
from collections import Counter, deque
from datetime import date, datetime, timezone

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from app.data import (APPOINTMENTS, BLOOD_GROUPS, DOCTORS, GENDERS, PATIENTS, STATUSES,
                      TOTAL_BEDS, WARD_BEDS, WARDS)

app = Flask(__name__)

APP_VERSION = os.getenv("APP_VERSION", "dev")
APP_COLOR = os.getenv("APP_COLOR", "none")
# Build info, passed in by Jenkinsfile.task3 through k8s/task3/deployment.yaml
BUILD_NUMBER = os.getenv("BUILD_NUMBER", "local")
GIT_COMMIT = os.getenv("GIT_COMMIT", "unknown")
HOSPITAL_NAME = "CareWell Hospital"
EDITION = "Secure Edition"

# Signs the session cookie that holds the CSRF token. In Kubernetes it comes from a Secret
# (created by Jenkins at deploy time); locally a random key is generated on start.
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
audit = logging.getLogger("audit")

# gunicorn runs threads, so adding a patient (new id + insert) is done under a lock
_lock = threading.Lock()

# In-memory audit trail shown on /audit (per pod, newest kept). The AUDIT log lines stay too.
AUDIT_EVENTS = deque(maxlen=500)
_audit_lock = threading.Lock()


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


# ---------------------------------------------------------------- audit trail

def record_audit(action, patient_id=None):
    """Write the AUDIT log line (kubectl logs) and keep the event for the /audit page."""
    client = request.remote_addr
    if patient_id is None:
        audit.info("AUDIT action=%s client=%s", action, client)
    else:
        audit.info("AUDIT action=%s id=%s client=%s", action, patient_id, client)
    event = {"time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
             "action": action, "patient_id": patient_id, "client": client}
    with _audit_lock:
        AUDIT_EVENTS.append(event)


def audit_events():
    """Newest first."""
    with _audit_lock:
        return list(reversed(AUDIT_EVENTS))


ACTIVITY_TEXT = {
    "view_patient": "Patient #{id} viewed",
    "read_patient": "Patient #{id} read via API",
    "create_patient": "New patient added (#{id})",
}


def recent_activity(limit=6):
    """Patient-related events for the dashboard feed."""
    feed = []
    for e in audit_events():
        if e["action"] in ACTIVITY_TEXT:
            feed.append({"time": e["time"][11:], "action": e["action"],
                         "text": ACTIVITY_TEXT[e["action"]].format(id=e["patient_id"])})
            if len(feed) == limit:
                break
    return feed


# ---------------------------------------------------------------- CSRF

def csrf_token():
    """One random token per browser session, stored in the signed session cookie."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def csrf_ok(form):
    expected = session.get("csrf_token", "")
    sent = form.get("csrf_token", "")
    return bool(expected) and hmac.compare_digest(expected, sent)


app.jinja_env.globals["csrf_token"] = csrf_token


# ---------------------------------------------------------------- helpers

def env_name():
    return "PRODUCTION" if APP_COLOR not in ("blue", "green") else APP_COLOR.upper()


@app.context_processor
def page_globals():
    # Available in every template: drives the top bar + environment badge
    return {
        "hospital": HOSPITAL_NAME,
        "edition": EDITION,
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


def patient_name(patient_id):
    patient = PATIENTS.get(patient_id)
    return patient["name"] if patient else "Unknown"


def vital_status(kind, value):
    """normal / high / low for a vital sign, 'unknown' when not measured yet.

    Thresholds (adult): BP high >= 140/90, low < 90/60; pulse 60-100 bpm;
    temperature 36.0-37.5 °C.
    """
    try:
        if kind == "bp":
            systolic, diastolic = (int(x) for x in str(value).split("/"))
            if systolic >= 140 or diastolic >= 90:
                return "high"
            if systolic < 90 or diastolic < 60:
                return "low"
            return "normal"
        number = float(value)
    except (TypeError, ValueError):
        return "unknown"
    low, high = {"pulse": (60, 100), "temp": (36.0, 37.5)}[kind]
    if number > high:
        return "high"
    if number < low:
        return "low"
    return "normal"


app.jinja_env.globals.update(doctor_name=doctor_name, patient_name=patient_name,
                             vital_status=vital_status)


def pct5(part, whole):
    """Percentage rounded to the nearest 5 (0-100): CSS has one width class per step,
    because the CSP forbids inline style="width: ..." attributes."""
    if not whole:
        return 0
    return max(0, min(100, int(round(part * 100 / whole / 5)) * 5))


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
            "allergies": [], "emergency_contact": None,
            "visits": [{"date": date.today().isoformat(), "note": "Registered at front desk"}],
        }
        patient.update(fields)
        PATIENTS[new_id] = patient
    record_audit("create_patient", new_id)
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
    record_audit("view_dashboard")
    today = date.today().isoformat()
    patients = list(PATIENTS.values())
    in_bed = [p for p in patients if p.get("status") != "Discharged"]
    todays = sorted((a for a in APPOINTMENTS if a["date"] == today), key=lambda a: a["time"])
    stats = {
        "patients": len(patients),
        "appointments": len(todays),
        "doctors_on_duty": sum(d["availability"] == "On duty" for d in DOCTORS.values()),
        "beds_occupied": len(in_bed),
        "total_beds": TOTAL_BEDS,
    }
    critical = [p for p in patients if p.get("status") == "Critical"]

    used = Counter(p.get("ward") for p in in_bed)
    wards = []
    for ward in WARDS:
        beds, n = WARD_BEDS[ward], used.get(ward, 0)
        percent = round(n * 100 / beds) if beds else 0
        level = "low" if percent < 60 else "medium" if percent < 85 else "high"
        wards.append({"name": ward, "used": n, "beds": beds, "percent": percent,
                      "pct5": pct5(n, beds), "level": level})

    per_doctor = Counter(a["doctor_id"] for a in todays)
    top = max(per_doctor.values(), default=0)
    doctor_load = [{"name": d["name"], "department": d["department"],
                    "count": per_doctor.get(d["id"], 0),
                    "pct5": pct5(per_doctor.get(d["id"], 0), top)}
                   for d in DOCTORS.values()]

    recent = sorted(patients, key=lambda p: (p.get("admitted") or "", p["id"]), reverse=True)[:5]
    return render_template("dashboard.html", active="dashboard", stats=stats,
                           recent=recent, todays=todays, critical=critical, wards=wards,
                           doctor_load=doctor_load, activity=recent_activity())


@app.get("/patients-ui")
def patients_page():
    q = request.args.get("q", "").strip()[:100]
    status = request.args.get("status", "")
    if status not in STATUSES:
        status = ""  # "All"
    record_audit("list_patients_ui")
    everyone = list(PATIENTS.values())
    counts = Counter(p.get("status") for p in everyone)
    chips = [{"label": "All", "value": "", "count": len(everyone)}] + [
        {"label": s, "value": s, "count": counts.get(s, 0)} for s in STATUSES]

    patients = everyone
    if status:
        patients = [p for p in patients if p.get("status") == status]
    if q:
        needle = q.lower()
        patients = [p for p in patients if needle in " ".join(
            str(p.get(k, "")) for k in ("id", "name", "ward", "diagnosis", "blood_group", "status")
        ).lower()]
    return render_template("patients.html", active="patients", patients=patients, q=q,
                           status=status, chips=chips)


@app.route("/patients-ui/new", methods=["GET", "POST"])
def new_patient_page():
    values, errors = {f: "" for f in FORM_FIELDS}, {}
    if request.method == "POST":
        if not csrf_ok(request.form):
            record_audit("csrf_rejected")
            values = {f: request.form.get(f, "").strip() for f in FORM_FIELDS}
            errors = {"csrf": "Security check failed (missing or invalid CSRF token). "
                              "Please submit the form again."}
        else:
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
    record_audit("view_patient", patient_id)
    patient = PATIENTS.get(patient_id)
    if patient is None:
        return render_template("not_found.html", active="patients"), 404
    return render_template("patient_detail.html", active="patients", p=patient)


@app.get("/doctors")
def doctors_page():
    return render_template("doctors.html", active="doctors", doctors=DOCTORS.values())


@app.get("/appointments")
def appointments_page():
    record_audit("list_appointments")
    appts = sorted(APPOINTMENTS, key=lambda a: (a["date"], a["time"]))
    return render_template("appointments.html", active="appointments", appointments=appts)


PIPELINE_GATES = [
    ("1", "Secret scan", "Gitleaks", "No passwords, keys or tokens anywhere in Git history"),
    ("2", "SAST", "Bandit", "No HIGH-severity, HIGH-confidence issues in the Python code"),
    ("3", "Dependency scan", "Trivy SCA", "No HIGH/CRITICAL CVEs in requirements.txt"),
    ("4", "Dockerfile lint", "Hadolint", "No error-level Dockerfile issues"),
    ("5", "Unit tests", "pytest", "All tests pass inside the Docker test stage"),
    ("7", "Image scan", "Trivy image", "No fixable CRITICAL CVEs in the container image"),
    ("8", "K8s manifest scan", "Trivy K8s", "No HIGH/CRITICAL misconfigurations in k8s/task3"),
]


def root_fs_read_only(mounts_file="/proc/self/mounts"):
    """True when "/" is mounted read-only (readOnlyRootFilesystem in k8s/task3)."""
    try:
        with open(mounts_file, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[1] == "/":
                    return "ro" in parts[3].split(",")
    except OSError:
        pass  # not Linux (e.g. running the tests on Windows)
    return False


def security_controls():
    """Controls active on this pod. 'live' = checked by the app right now."""
    uid = os.getuid() if hasattr(os, "getuid") else None
    read_only = root_fs_read_only()
    return [
        {"name": "Non-root user", "detail": f"Running as uid {uid}" if uid is not None
         else "uid not available on this OS", "ok": uid not in (None, 0), "source": "live"},
        {"name": "Read-only root filesystem", "detail": "App files cannot be modified"
         if read_only else "Filesystem is writable (not running in the hardened pod)",
         "ok": read_only, "source": "live"},
        {"name": "Secrets from Kubernetes", "detail": "DB_PASSWORD and SECRET_KEY injected "
         "from Kubernetes Secrets, never stored in Git",
         "ok": bool(os.getenv("DB_PASSWORD")) and bool(os.getenv("SECRET_KEY")), "source": "live"},
        {"name": "CSP + security headers", "detail": "CSP, X-Frame-Options DENY, nosniff, "
         "no-store, no-referrer on every response", "ok": True, "source": "app"},
        {"name": "CSRF protection", "detail": "Session token + hidden field on the "
         "Add-patient form", "ok": True, "source": "app"},
        {"name": "PHI masking", "detail": "Phone numbers show only the last 4 digits",
         "ok": True, "source": "app"},
        {"name": "Audit logging", "detail": "Every patient-record access is logged "
         "(AUDIT lines + Audit Log page)", "ok": True, "source": "app"},
        {"name": "Pod Security \"restricted\"", "detail": "Namespace pbl-task3 rejects root, "
         "privileged and extra-capability pods", "ok": True, "source": "k8s/task3"},
        {"name": "Network policy", "detail": "Default deny; only port 5000 in and DNS out",
         "ok": True, "source": "k8s/task3"},
    ]


@app.get("/security")
def security_page():
    return render_template("security.html", active="security", gates=PIPELINE_GATES,
                           controls=security_controls(), build_number=BUILD_NUMBER,
                           git_commit=GIT_COMMIT)


@app.get("/audit")
def audit_page():
    record_audit("view_audit_log")
    return render_template("audit.html", active="audit", events=audit_events()[:200])


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
    record_audit("list_patients")
    return jsonify([public(p) for p in PATIENTS.values()])


@app.get("/patients/<int:patient_id>")
def get_patient(patient_id):
    record_audit("read_patient", patient_id)
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
