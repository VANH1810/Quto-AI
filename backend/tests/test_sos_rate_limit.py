from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _payload(note: str = "Có người cần hỗ trợ khẩn cấp") -> dict:
    return {
        "lat": 22.3958973,
        "lon": 102.274572,
        "danger_type": "other",
        "num_people": 2,
        "reported_at": "2026-07-18T10:30:00+07:00",
        "note": note,
        "commune_code": "03158",
        "commune_name": "Xã Sín Thầu",
    }


def test_public_sos_is_created_and_duplicate_is_rate_limited() -> None:
    device_id = f"test-device-{uuid.uuid4()}"
    first = client.post("/api/v1/rescue/sos", json=_payload(), headers={"X-Device-ID": device_id})

    assert first.status_code == 201
    assert first.json()["id"].startswith("sos_")
    assert first.json()["status"] == "pending"
    assert first.json()["commune_name"] == "Xã Sín Thầu"
    assert first.headers["x-sos-cooldown"] == "600"

    duplicate = client.post("/api/v1/rescue/sos", json=_payload(), headers={"X-Device-ID": device_id})

    assert duplicate.status_code == 429
    assert "trùng tọa độ và nội dung" in duplicate.json()["detail"]
    assert 1 <= int(duplicate.headers["retry-after"]) <= 600


def test_public_sos_rate_limit_also_blocks_changed_content_during_cooldown() -> None:
    device_id = f"test-device-{uuid.uuid4()}"
    assert client.post("/api/v1/rescue/sos", json=_payload("Nội dung thứ nhất"), headers={"X-Device-ID": device_id}).status_code == 201

    changed = client.post("/api/v1/rescue/sos", json=_payload("Nội dung khác"), headers={"X-Device-ID": device_id})

    assert changed.status_code == 429
    assert "Vui lòng chờ" in changed.json()["detail"]
    assert "retry-after" in changed.headers
