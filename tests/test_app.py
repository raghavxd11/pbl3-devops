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


def test_list_patients(client):
    r = client.get("/patients")
    assert r.status_code == 200
    assert len(r.get_json()) >= 2


def test_get_missing_patient(client):
    assert client.get("/patients/9999").status_code == 404


def test_add_patient(client):
    r = client.post("/patients", json={"name": "Test Patient", "age": 40})
    assert r.status_code == 201
    assert r.get_json()["name"] == "Test Patient"


def test_add_patient_requires_name(client):
    assert client.post("/patients", json={}).status_code == 400
