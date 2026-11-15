import copy

import pytest

from app.main import PATIENTS, app

VALID_FORM = {
    "name": "Ramesh Kumar", "age": "45", "gender": "Male", "blood_group": "O+",
    "phone": "9812345678", "ward": "General", "doctor_id": "4",
    "diagnosis": "Viral fever", "status": "Admitted",
}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    saved = copy.deepcopy(PATIENTS)  # tests that add patients don't leak into other tests
    with app.test_client() as c:
        yield c
    PATIENTS.clear()
    PATIENTS.update(saved)


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
    "/doctors", "/appointments", "/static/style.css",
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
    r = client.post("/patients-ui/new", data=VALID_FORM)
    assert r.status_code == 303
    assert len(PATIENTS) == before + 1
    detail = client.get(r.headers["Location"]).get_data(as_text=True)
    assert "Ramesh Kumar" in detail


def test_form_empty_shows_errors(client):
    before = len(PATIENTS)
    r = client.post("/patients-ui/new", data={})
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
    r = client.post("/patients-ui/new", data=dict(VALID_FORM, **{field: value}))
    assert r.status_code == 400
    assert message in r.get_data(as_text=True)


def test_form_keeps_entered_values_on_error(client):
    r = client.post("/patients-ui/new", data=dict(VALID_FORM, age="-1"))
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
    r = client.post("/patients-ui/new", data=dict(VALID_FORM, diagnosis='"><script>alert(1)</script>',
                                                  age="x"))
    body = r.get_data(as_text=True)
    assert "<script>" not in body
    assert "&#34;&gt;&lt;script&gt;" in body
