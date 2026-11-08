import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Secure Internal Comms" in data["app"]


def test_swagger_and_openapi_docs():
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200

    openapi_resp = client.get("/api/v1/openapi.json")
    assert openapi_resp.status_code == 200
    schema = openapi_resp.json()
    assert "paths" in schema
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/compliance/blind-sign" in schema["paths"]
    assert "/api/v1/anonymous/cases" in schema["paths"]
    assert "/api/v1/officer/cases" in schema["paths"]
