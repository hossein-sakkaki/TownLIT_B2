# apps/accounts/services/veriff.py

import requests
from django.conf import settings


def create_veriff_session(user, success_url=None, failure_url=None):
    # Create Veriff verification session
    payload = {
        "verification": {
            "person": {
                "firstName": user.name,
                "lastName": user.family,
                "gender": user.gender,
                "dateOfBirth": user.birthday.isoformat() if user.birthday else None,
            },
            "vendorData": str(user.id),
            "timestamp": None,
        }
    }

    if success_url:
        payload["verification"]["callback"] = success_url

    headers = {
        "Authorization": f"Bearer {settings.VERIFF_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(f"{settings.VERIFF_BASE_URL}/sessions", json=payload, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()


def parse_veriff_webhook(payload: dict) -> dict:
    # Normalize webhook payload
    verification = payload.get("verification", {})
    decision = verification.get("decision", {})

    return {
        "session_id": verification.get("id"),
        "status": decision.get("status"),
        "reason": decision.get("reason"),
        "risk": decision.get("riskLabels", []),
        "raw": payload,
    }
