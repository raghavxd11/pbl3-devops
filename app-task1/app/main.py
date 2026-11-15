"""CareWell Hospital - v1 BASIC (PBL-III Task 1).

One page: the hospital header and a simple table of patients.
/health and /version are used by the Jenkins pipeline (readiness probe + smoke test).
"""
import os
import socket

from flask import Flask, jsonify, render_template

app = Flask(__name__)

APP_VERSION = os.getenv("APP_VERSION", "dev")

PATIENTS = [
    {"id": 1, "name": "Asha Sharma", "age": 34, "ward": "Cardiology"},
    {"id": 2, "name": "Rohan Mehta", "age": 52, "ward": "Orthopedics"},
    {"id": 3, "name": "Kavya Pillai", "age": 8, "ward": "Paediatrics"},
    {"id": 4, "name": "Imran Qureshi", "age": 67, "ward": "ICU"},
    {"id": 5, "name": "Sunita Joshi", "age": 45, "ward": "General"},
    {"id": 6, "name": "Venkatesh Rao", "age": 71, "ward": "Neurology"},
]


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


@app.get("/")
def home():
    return render_template("index.html", patients=PATIENTS, version=APP_VERSION,
                           pod=socket.gethostname())


@app.get("/health")
def health():
    return jsonify(status="ok"), 200


@app.get("/version")
def version():
    return jsonify(version=APP_VERSION, pod=socket.gethostname())
