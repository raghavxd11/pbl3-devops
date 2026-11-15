import copy
import logging
import re

import pytest

import app.main as main
from app.main import AUDIT_EVENTS, PATIENTS, app

VALID_FORM = {
    "name": "Ramesh Kumar", "age": "45", "gender": "Male", "blood_group": "O+",
    "phone": "9812345678", "ward": "General", "doctor_id": "4",
    "diagnosis": "Viral fever", "status": "Admitted",
}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    saved = copy.deepcopy(PATIENTS)  # tests that add patients don't leak into other tests
    AUDIT_EVENTS.clear()
    with app.test_client() as c:
        yield c
    PATIENTS.clear()
    PATIENTS.update(saved)
    AUDIT_EVENTS.clear()


def csrf_from(client):
    """Open the Add-patient form like a browser and read the hidden CSRF token."""
    body = client.get("/patients-ui/new").get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', body).group(1)


def post_form(client, data):
    return client.post("/patients-ui/new", data=dict(data, csrf_token=csrf_from(client)))


# ---------------- JSON API (used by the pipelines - must not change)

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_version(client):
    r = client.get("/version")
    assert r.status_code == 200
    assert "version" in r.get_json()


def test_list_patients(client):
    r = client.get("/patients")
    assert r.status_code == 200
    assert len(r.get_json()) >= 2


def test_api_keeps_original_fields_and_hides_phone(client):
    p = client.get("/patients/1").get_json()
    assert set(p) == {"id", "name", "age", "ward"}


def test_get_missing_patient(client):
    assert client.get("/patients/9999").status_code == 404


def test_add_patient(client):
    r = client.post("/patients", json={"name": "Test Patient", "age": 40})
    assert r.status_code == 201
    assert r.get_json()["name"] == "Test Patient"
    # a patient created through the API can also be opened in the UI
    assert client.get(f"/patients-ui/{r.get_json()['id']}").status_code == 200


def test_add_patient_requires_name(client):
    assert client.post("/patients", json={}).status_code == 400


def test_api_index(client):
    r = client.get("/api")
    assert r.status_code == 200
    assert r.get_json()["service"] == "patient-records-api"


# ---------------- HTML pages

@pytest.mark.parametrize("url", [
    "/", "/patients-ui", "/patients-ui?q=cardio", "/patients-ui/1", "/patients-ui/new",
    "/doctors", "/appointments", "/static/style.css", "/security", "/audit",
    "/patients-ui?status=Critical",
])
def test_pages_return_200(client, url):
    assert client.get(url).status_code == 200


def test_dashboard_shows_hospital_and_environment(client):
    body = client.get("/").get_data(as_text=True)
    assert "CareWell Hospital" in body
    assert "PRODUCTION" in body  # APP_COLOR not set in tests
    assert "Total patients" in body


def test_missing_patient_page_is_404(client):
    assert client.get("/patients-ui/9999").status_code == 404


def test_search_filters_patients(client):
    body = client.get("/patients-ui?q=Asha").get_data(as_text=True)
    assert "Asha Sharma" in body
    assert "Rohan Mehta" not in body


def test_phone_is_masked(client):
    body = client.get("/patients-ui/1").get_data(as_text=True)
    assert "9876543210" not in body
    assert "******3210" in body


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["Content-Security-Policy"] == (
        "default-src 'none'; style-src 'self'; img-src 'self' data:; "
        "form-action 'self'; frame-ancestors 'none'"
    )
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cache-Control"] == "no-store"


# ---------------- Add-patient form validation

def test_form_creates_patient_and_redirects(client):
    before = len(PATIENTS)
    r = post_form(client, VALID_FORM)
    assert r.status_code == 303
    assert len(PATIENTS) == before + 1
    detail = client.get(r.headers["Location"]).get_data(as_text=True)
    assert "Ramesh Kumar" in detail


def test_form_empty_shows_errors(client):
    before = len(PATIENTS)
    r = post_form(client, {})
    body = r.get_data(as_text=True)
    assert r.status_code == 400
    assert "Name is required." in body
    assert "Diagnosis is required." in body
    assert len(PATIENTS) == before


@pytest.mark.parametrize("field,value,message", [
    ("age", "200", "Age must be a whole number"),
    ("age", "abc", "Age must be a whole number"),
    ("phone", "12345", "10-digit Indian mobile"),
    ("blood_group", "Z+", "valid blood group"),
    ("doctor_id", "99", "assigned doctor"),
    ("name", "<b>x</b>", "Name may only contain"),
])
def test_form_rejects_bad_values(client, field, value, message):
    r = post_form(client, dict(VALID_FORM, **{field: value}))
    assert r.status_code == 400
    assert message in r.get_data(as_text=True)


def test_form_keeps_entered_values_on_error(client):
    r = post_form(client, dict(VALID_FORM, age="-1"))
    assert 'value="Ramesh Kumar"' in r.get_data(as_text=True)


# ---------------- XSS: everything is HTML-escaped

XSS = "<script>alert(1)</script>"
XSS_ESCAPED = "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_dashboard_escapes_html(client, monkeypatch):
    monkeypatch.setitem(PATIENTS, 999, {"id": 999, "name": XSS, "age": 1, "ward": "Test",
                                        "admitted": "2999-01-01"})
    body = client.get("/").get_data(as_text=True)
    assert "<script>" not in body
    assert XSS_ESCAPED in body


def test_detail_escapes_html(client):
    pid = client.post("/patients", json={"name": XSS, "ward": XSS}).get_json()["id"]
    body = client.get(f"/patients-ui/{pid}").get_data(as_text=True)
    assert "<script>" not in body
    assert XSS_ESCAPED in body


def test_search_query_is_escaped(client):
    body = client.get("/patients-ui", query_string={"q": XSS}).get_data(as_text=True)
    assert "<script>" not in body
    assert XSS_ESCAPED in body


def test_form_redisplay_is_escaped(client):
    r = post_form(client, dict(VALID_FORM, diagnosis='"><script>alert(1)</script>', age="x"))
    body = r.get_data(as_text=True)
    assert "<script>" not in body
    assert "&#34;&gt;&lt;script&gt;" in body


# ---------------- CSRF on the Add-patient form

def test_form_has_hidden_csrf_token(client):
    body = client.get("/patients-ui/new").get_data(as_text=True)
    assert re.search(r'<input type="hidden" name="csrf_token" value="[A-Za-z0-9_-]{40,}">', body)


def test_form_without_csrf_token_is_rejected(client):
    before = len(PATIENTS)
    client.get("/patients-ui/new")  # session has a token, but the POST doesn't send it
    r = client.post("/patients-ui/new", data=VALID_FORM)
    assert r.status_code == 400
    assert "CSRF token" in r.get_data(as_text=True)
    assert len(PATIENTS) == before


def test_form_with_wrong_csrf_token_is_rejected(client):
    before = len(PATIENTS)
    csrf_from(client)
    r = client.post("/patients-ui/new", data=dict(VALID_FORM, csrf_token="forged"))
    assert r.status_code == 400
    assert len(PATIENTS) == before
    assert AUDIT_EVENTS[-1]["action"] == "csrf_rejected"


def test_csrf_token_without_session_is_rejected(client):
    # A token copied from another browser session is useless without that session cookie
    token = csrf_from(client)
    with app.test_client() as other:
        r = other.post("/patients-ui/new", data=dict(VALID_FORM, csrf_token=token))
    assert r.status_code == 400


def test_session_cookie_flags(client):
    r = client.get("/patients-ui/new")
    cookie = r.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_json_api_post_still_works_without_csrf(client):
    assert client.post("/patients", json={"name": "Api User"}).status_code == 201


# ---------------- Look: secure edition

def test_secure_edition_branding(client):
    body = client.get("/").get_data(as_text=True)
    assert "CareWell Hospital" in body
    assert "Secure Edition" in body
    assert "Secured by DevSecOps" in body
    assert '<svg class="icon"' in body  # sidebar icons are inline SVG
    assert "<script" not in body        # still no JavaScript


# ---------------- Dashboard

def test_dashboard_critical_alert(client):
    body = client.get("/").get_data(as_text=True)
    assert "alert-critical" in body
    assert "2 critical patients" in body
    assert "Imran Qureshi" in body and "Venkatesh Rao" in body


def test_dashboard_no_alert_without_critical_patients(client, monkeypatch):
    for pid, p in list(PATIENTS.items()):
        monkeypatch.setitem(PATIENTS, pid, dict(p, status="Admitted"))
    assert "alert-critical" not in client.get("/").get_data(as_text=True)


def test_dashboard_ward_occupancy(client):
    body = client.get("/").get_data(as_text=True)
    assert "Ward occupancy" in body
    # Neurology: 2 of 2 beds -> 100%, red; General: 2 of 6 -> 33%, green
    assert re.search(r'ward-high">\s*<div class="ward-head"><strong>Neurology', body)
    assert "2 / 2 beds used" in body
    assert re.search(r'ward-low">\s*<div class="ward-head"><strong>General', body)
    assert "pct-100" in body and "pct-35" in body


def test_ward_bar_is_capped_at_100(client):
    for _ in range(3):
        client.post("/patients", json={"name": "Overflow", "ward": "ICU"})
    body = client.get("/").get_data(as_text=True)
    assert "4 / 2 beds used" in body
    assert "pct-200" not in body


def test_dashboard_appointments_per_doctor_chart(client):
    body = client.get("/").get_data(as_text=True)
    assert "appointments per doctor" in body
    # Dr. Sanjay Gupta has the most appointments today (3) -> full-width bar
    assert re.search(r'Dr\. Sanjay Gupta</span>\s*<span class="chart-track"><span class="chart-bar pct-100">'
                     r'</span></span>\s*<span class="chart-value">3<', body)


def test_dashboard_activity_feed(client):
    assert "No patient activity" in client.get("/").get_data(as_text=True)
    client.get("/patients-ui/4")
    new_id = client.post("/patients", json={"name": "Feed Test"}).get_json()["id"]
    body = client.get("/").get_data(as_text=True)
    assert "Patient #4 viewed" in body
    assert f"New patient added (#{new_id})" in body


# ---------------- Security Center

def test_security_center_lists_gates(client):
    body = client.get("/security").get_data(as_text=True)
    for tool in ["Gitleaks", "Bandit", "Trivy SCA", "Hadolint", "Trivy image", "Trivy K8s",
                 "OWASP ZAP"]:
        assert tool in body


def test_security_center_lists_controls(client):
    body = client.get("/security").get_data(as_text=True)
    for control in ["Non-root user", "Read-only root filesystem", "CSP + security headers",
                    "PHI masking", "Audit logging", "Pod Security &#34;restricted&#34;"]:
        assert control in body


def test_security_center_shows_build_info(client, monkeypatch):
    monkeypatch.setattr(main, "BUILD_NUMBER", "42")
    monkeypatch.setattr(main, "GIT_COMMIT", "abc1234")
    body = client.get("/security").get_data(as_text=True)
    assert "#42" in body
    assert "abc1234" in body
    assert "build #42 cleared all of these" in body
    assert "check-pass" in body


def test_security_center_local_build_has_no_ticks(client, monkeypatch):
    monkeypatch.setattr(main, "BUILD_NUMBER", "local")
    body = client.get("/security").get_data(as_text=True)
    assert "Not deployed by Jenkins" in body
    assert "check-pending" in body


# ---------------- Audit Log

def test_audit_page_records_access(client):
    client.get("/patients-ui/4")
    client.get("/patients/2")
    body = client.get("/audit").get_data(as_text=True)
    assert "view_patient" in body and "read_patient" in body
    assert 'href="/patients-ui/4">#4</a>' in body
    assert "127.0.0.1" in body


def test_audit_page_newest_first(client):
    client.get("/patients-ui/1")
    client.get("/patients-ui")
    body = client.get("/audit").get_data(as_text=True)
    assert body.index("list_patients_ui") < body.index("view_patient")


def test_audit_page_lists_views_lists_creates_and_csrf(client):
    client.get("/patients-ui/1")                                   # patient view
    client.get("/patients/2")                                      # patient view (API)
    client.get("/patients-ui")                                     # list view
    client.get("/appointments")                                    # list view
    client.post("/patients", json={"name": "Listed"})              # create
    client.post("/patients-ui/new", data=dict(VALID_FORM, csrf_token="x"))  # CSRF rejection
    assert [e["action"] for e in AUDIT_EVENTS] == [
        "view_patient", "read_patient", "list_patients_ui", "list_appointments",
        "create_patient", "csrf_rejected"]


def test_dashboard_and_audit_views_are_log_lines_only(client, caplog):
    with caplog.at_level(logging.INFO, logger="audit"):
        client.get("/")
        client.get("/audit")
    assert "AUDIT action=view_dashboard client=127.0.0.1" in caplog.text
    assert "AUDIT action=view_audit_log client=127.0.0.1" in caplog.text
    assert list(AUDIT_EVENTS) == []
    assert "view_dashboard" not in client.get("/audit").get_data(as_text=True)


def test_audit_log_lines_are_kept(client, caplog):
    with caplog.at_level(logging.INFO, logger="audit"):
        client.get("/patients-ui/4")
    assert "AUDIT action=view_patient id=4 client=127.0.0.1" in caplog.text


# ---------------- Patients: status filter chips

def test_status_filter_critical(client):
    body = client.get("/patients-ui?status=Critical").get_data(as_text=True)
    assert "Imran Qureshi" in body and "Venkatesh Rao" in body
    assert "Asha Sharma" not in body
    assert 'chip chip-active" href="/patients-ui?status=Critical"' in body


def test_status_filter_discharged(client):
    body = client.get("/patients-ui?status=Discharged").get_data(as_text=True)
    assert "Harpreet Kaur" in body
    assert "Imran Qureshi" not in body


def test_status_filter_all_and_invalid(client):
    for url in ["/patients-ui", "/patients-ui?status=bogus"]:
        body = client.get(url).get_data(as_text=True)
        assert "Asha Sharma" in body and "Imran Qureshi" in body
        assert 'chip chip-active" href="/patients-ui"' in body


def test_status_filter_with_search(client):
    body = client.get("/patients-ui?status=Admitted&q=cardio").get_data(as_text=True)
    assert "Asha Sharma" in body          # Cardiology, Admitted
    assert "Neha Banerjee" not in body    # Cardiology, Discharged
    assert "Rohan Mehta" not in body      # Admitted, Orthopedics


def test_status_chips_show_counts(client):
    body = client.get("/patients-ui").get_data(as_text=True)
    assert re.search(r'All <span class="chip-count">12</span>', body)
    assert re.search(r'Critical <span class="chip-count">2</span>', body)


# ---------------- Patient detail: vitals, allergies, emergency contact, timeline

@pytest.mark.parametrize("kind,value,expected", [
    ("bp", "120/80", "normal"), ("bp", "168/98", "high"), ("bp", "140/80", "high"),
    ("bp", "85/55", "low"), ("pulse", 72, "normal"), ("pulse", 118, "high"),
    ("pulse", 50, "low"), ("temp", 36.8, "normal"), ("temp", 38.4, "high"),
    ("temp", 35.2, "low"), ("bp", "—", "unknown"), ("pulse", "—", "unknown"),
])
def test_vital_status_thresholds(kind, value, expected):
    assert main.vital_status(kind, value) == expected


def test_detail_vital_cards(client):
    body = client.get("/patients-ui/7").get_data(as_text=True)  # BP 168/98, pulse 96, 37.2
    assert '<div class="vital vital-high">' in body
    assert body.count('<div class="vital vital-normal">') == 2
    assert "HIGH" in body


def test_new_patient_vitals_not_measured(client):
    pid = client.post("/patients", json={"name": "No Vitals"}).get_json()["id"]
    body = client.get(f"/patients-ui/{pid}").get_data(as_text=True)
    assert body.count('<div class="vital vital-unknown">') == 3
    assert "NOT MEASURED" in body
    assert "No known allergies" in body
    assert "Not recorded" in body


def test_detail_allergies_and_masked_emergency_contact(client):
    body = client.get("/patients-ui/3").get_data(as_text=True)
    assert "Peanuts" in body and "Ibuprofen" in body
    assert "Anil Pillai (Father)" in body
    assert "9845100033" not in body
    assert "******0033" in body


def test_detail_visit_timeline(client):
    body = client.get("/patients-ui/2").get_data(as_text=True)
    assert '<ol class="timeline">' in body
    assert body.count('<span class="timeline-date">') == 3
    # newest visit first
    assert body.index("Physiotherapy started") < body.index("Admitted after road accident")


def test_root_fs_read_only_detection(tmp_path):
    ro = tmp_path / "ro"
    ro.write_text("overlay / overlay ro,relatime 0 0\nproc /proc proc rw 0 0\n")
    rw = tmp_path / "rw"
    rw.write_text("overlay / overlay rw,relatime 0 0\n")
    assert main.root_fs_read_only(str(ro)) is True
    assert main.root_fs_read_only(str(rw)) is False
    assert main.root_fs_read_only(str(tmp_path / "missing")) is False
