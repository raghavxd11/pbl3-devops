import pytest

from app.main import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_version(client):
    r = client.get("/version")
    assert r.status_code == 200
    assert "version" in r.get_json()


def test_home_shows_patient_table(client):
    r = client.get("/")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "CareWell Hospital" in body
    assert "Asha Sharma" in body
    assert "<th>Ward</th>" in body


def test_stylesheet(client):
    assert client.get("/static/style.css").status_code == 200


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
