from datetime import datetime, timedelta, timezone

from app.services import ad_service


def test_false_active_value_pauses_advertisement():
    data = {"is_active": False}

    ad_service._normalize_lifecycle(data, current={"status": "active"})

    assert data == {"is_active": False, "status": "paused"}


def test_paused_status_disables_advertisement():
    data = {"status": "paused"}

    ad_service._normalize_lifecycle(data, current={"is_active": True})

    assert data == {"status": "paused", "is_active": False}


def test_active_status_enables_advertisement():
    data = {"status": "active"}

    ad_service._normalize_lifecycle(data, current={"is_active": False})

    assert data == {"status": "active", "is_active": True}


def test_past_end_date_forces_expired_and_inactive():
    data = {
        "status": "active",
        "end_date": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
    }

    ad_service._normalize_lifecycle(data)

    assert data["status"] == "expired"
    assert data["is_active"] is False
