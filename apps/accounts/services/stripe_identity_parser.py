# apps/accounts/services/stripe_identity_parser.py

def parse_stripe_identity_event(event):
    """
    Normalize Stripe Identity webhook payload.
    """

    session = event["data"]["object"]

    event_type = event["type"]

    status = session.get("status")

    # Stripe event mapping
    if event_type == "identity.verification_session.verified":
        status = "verified"

    elif event_type == "identity.verification_session.requires_input":
        status = "requires_input"

    elif event_type == "identity.verification_session.canceled":
        status = "canceled"

    return {
        "session_id": session["id"],
        "status": status,
        "reason": session.get("last_error"),
        "risk": [],
        "raw": event,
    }