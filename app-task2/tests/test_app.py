import pytest

import app.main as main
from app.main import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------- used by the pipeline (readiness probe + smoke test)

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_version_reports_version_and_color(client):
    data = client.get("/version").get_json()
    assert "version" in data
    assert "color" in data


# ---------------- HTML pages

@pytest.mark.parametrize("url", [
    "/", "/patients", "/patients?q=cardio", "/doctors", "/appointments", "/static/style.css",
])
def test_pages_return_200(client, url):
    assert client.get(url).status_code == 200


def test_dashboard_shows_hospital_and_stats(client):
    body = client.get("/").get_data(as_text=True)
    assert "CareWell Hospital" in body
    assert "Total patients" in body
    assert "PRODUCTION" in body  # APP_COLOR not set in tests


@pytest.mark.parametrize("color", ["blue", "green"])
def test_environment_bar_uses_app_color(client, monkeypatch, color):
    monkeypatch.setattr(main, "APP_COLOR", color)
    body = client.get("/").get_data(as_text=True)
    assert f"env-{color}" in body
    assert color.upper() in body


def test_search_filters_patients(client):
    body = client.get("/patients?q=Asha").get_data(as_text=True)
    assert "Asha Sharma" in body
    assert "Rohan Mehta" not in body


def test_search_query_is_escaped(client):
    body = client.get("/patients", query_string={"q": "<script>x</script>"}).get_data(as_text=True)
    assert "<script>" not in body


def test_v2_has_no_detail_page_or_form(client):
    assert client.get("/patients/1").status_code == 404
    assert client.get("/patients-ui/new").status_code == 404


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
