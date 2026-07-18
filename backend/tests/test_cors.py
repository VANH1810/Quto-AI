from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_vercel_origin_preflight_is_allowed() -> None:
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://quto-ai.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://quto-ai.vercel.app"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_unknown_origin_preflight_is_rejected() -> None:
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://example.invalid",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
