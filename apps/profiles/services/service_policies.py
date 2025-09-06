# services/service_policies.py
# -*- coding: utf-8 -*-

"""
Policy dictionary for sensitive ministries.

- Keep the main structure intact:
  get_policy() returns {"policy": SERVICE_DOC_POLICY, "labels": EVIDENCE_LABELS, "legend": LEGEND (optional)}
- Frontend currently relies on "policy" and "labels". "legend" is additive/optional.
- Time markers (<=12m / <=24m) are explained in labels, not as symbols.
"""

# ------------------------------
# Alternative requirement paths (A/B/C) per sensitive service.
# Each "required" item refers to a code listed in EVIDENCE_LABELS.
# ------------------------------
SERVICE_DOC_POLICY = {
    "pastoring":   {"paths": [{"required": ["endorsement<=12m"]},
                              {"required": ["two_references<=12m", "coc"]}]},
    "shepherding": {"paths": [{"required": ["endorsement<=12m"]},
                              {"required": ["two_references<=12m", "coc"]}]},
    "leadership":  {"paths": [{"required": ["endorsement<=12m"]},
                              {"required": ["two_references<=12m", "coc"]}]},
    "governance":  {"paths": [{"required": ["appointment_letter<=12m"]},
                              {"required": ["two_references<=12m", "coc"]}]},

    "teaching":     {"paths": [{"required": ["teaching_training", "endorsement<=12m"]},
                               {"required": ["two_references<=12m", "coc"]}]},
    "biblestudy":   {"paths": [{"required": ["bible_training", "endorsement<=12m"]},
                               {"required": ["two_references<=12m", "coc"]}]},
    "discipleship": {"paths": [{"required": ["discipleship_training", "endorsement<=12m"]},
                               {"required": ["two_references<=12m", "coc"]}]},
    "smallgroups":  {"paths": [{"required": ["smallgroup_training", "endorsement<=12m"]},
                               {"required": ["two_references<=12m", "coc"]}]},
    "mentoring":    {"paths": [{"required": ["endorsement<=12m"]},
                               {"required": ["two_references<=12m", "coc"]}]},

    "counseling": {"paths": [{"required": ["prof_license|church_counsel_cert", "endorsement<=12m", "background<=12m"]},
                             {"required": ["two_references<=12m", "coc", "counsel_training"]}]},
    "marriage":   {"paths": [{"required": ["marriage_care_cert", "endorsement<=12m", "background<=12m"]},
                             {"required": ["two_references<=12m", "coc", "marriage_care_cert"]}]},
    "griefcare":  {"paths": [{"required": ["grief_care_cert", "endorsement<=12m", "background<=12m"]},
                             {"required": ["two_references<=12m", "coc", "grief_care_cert"]}]},

    "chaplaincy": {"paths": [{"required": ["CPE_units", "eccles_endorsement<=12m", "facility_approval", "background<=12m"]},
                             {"required": ["two_references<=12m", "coc", "CPE_units"]}]},
    "hospital":   {"paths": [{"required": ["facility_approval", "background<=12m"]},
                             {"required": ["endorsement<=12m"]}]},
    "prison":     {"paths": [{"required": ["facility_approval", "background<=12m"]},
                             {"required": ["endorsement<=12m"]}]},
    "visitation": {"paths": [{"required": ["endorsement<=12m"]},
                             {"required": ["two_references<=12m", "coc"]}]},

    "children": {"paths": [{"required": ["endorsement<=12m", "safeguarding<=24m"]},
                           {"required": ["two_references<=12m", "safeguarding<=24m", "coc"]},
                           {"required": ["background<=12m", "safeguarding<=24m"]}]},
    "youth":    {"paths": [{"required": ["endorsement<=12m", "safeguarding<=24m"]},
                           {"required": ["two_references<=12m", "safeguarding<=24m", "coc"]},
                           {"required": ["background<=12m", "safeguarding<=24m"]}]},

    "refugee": {"paths": [{"required": ["ngo_or_church_letter<=12m"]},
                          {"required": ["two_references<=12m", "coc"]}]},
    "seniors": {"paths": [{"required": ["endorsement<=12m"]},
                          {"required": ["two_references<=12m", "coc"]}]},

    "security": {"paths": [{"required": ["site_security_training", "background<=12m", "site_manager_letter<=12m"]},
                           {"required": ["two_references<=12m", "site_security_training", "coc"]}]},

    "reconciliation": {"paths": [{"required": ["mediation_training", "endorsement<=12m"]},
                                 {"required": ["two_references<=12m", "coc", "mediation_training"]}]},
    "peacemaking":    {"paths": [{"required": ["peacemaking_training", "endorsement<=12m"]},
                                 {"required": ["two_references<=12m", "coc", "peacemaking_training"]}]},

    "tutoring": {"paths": [{"required": ["teaching_or_subject_cert", "endorsement<=12m"]},
                           {"required": ["two_references<=12m", "coc", "teaching_or_subject_cert"]}]},

    "finance":  {"paths": [{"required": ["prof_license|bookkeeping_cert", "treasurer_appointment<=12m"]},
                           {"required": ["two_references<=12m", "coc", "bookkeeping_cert"]}]},
}

# ------------------------------
# Human-readable labels for each evidence code.
# Use plain language instead of ≤12m/≤24m symbols.
# ------------------------------
EVIDENCE_LABELS = {
    # General endorsements / references / checks
    "endorsement<=12m":            "Endorsement / Good Standing — issued within the last 12 months",
    "eccles_endorsement<=12m":     "Ecclesiastical Endorsement — issued within the last 12 months",
    "appointment_letter<=12m":     "Appointment Letter — dated within the last 12 months",
    "site_manager_letter<=12m":    "Site/Facility Manager Letter — dated within the last 12 months",
    "two_references<=12m":         "Two Independent References — written within the last 12 months",
    "background<=12m":             "Background / Police Check — completed within the last 12 months",
    "safeguarding<=24m":           "Safeguarding / Child-Protection Training — completed within the last 24 months",
    "ngo_or_church_letter<=12m":   "NGO or Church Letter — issued within the last 12 months",

    # Training / Education
    "CPE_units":                   "CPE Units (Clinical Pastoral Education)",
    "facility_approval":           "Facility Approval / Official Volunteer ID",
    "teaching_training":           "Teaching Training Certificate",
    "bible_training":              "Bible Study Teaching Certificate",
    "discipleship_training":       "Discipleship Training Certificate",
    "smallgroup_training":         "Small Group Leadership Training",
    "mentoring_training":          "Mentoring / Coaching Training",
    "counsel_training":            "Counseling Training (Church-based)",
    "marriage_care_cert":          "Marriage Care Training Certificate",
    "grief_care_cert":             "Grief Care Training Certificate",
    "site_security_training":      "Site Security / Safety Training",
    "mediation_training":          "Mediation Training Certificate",
    "peacemaking_training":        "Peacemaking Training Certificate",
    "teaching_or_subject_cert":    "Teaching or Subject-Matter Certificate",
    "bookkeeping_cert":            "Bookkeeping / Accounting Certificate",

    # Professional vs. Church equivalence (OR)
    "prof_license|church_counsel_cert": "Professional Counseling License — or — Church Counseling Certificate",
    "prof_license|bookkeeping_cert":    "Professional Accounting License (e.g., CPA / ACCA) — or — Bookkeeping Certificate",

    # Code of Conduct
    "coc":                         "Signed Code of Conduct & Statement of Truth",
    "treasurer_appointment<=12m":  "Treasurer Appointment — dated within the last 12 months",
}

# ------------------------------
# Optional legend for UI helpers (non-breaking)
# ------------------------------
LEGEND = {
    "time_window_note": "“within the last N months” refers to the document’s date (issue or completion) not being older than N months.",
    "or_note": "“A — or — B” means either document is acceptable.",
    "references_note": "References should be from unrelated adults who can speak to character and suitability.",
    "background_note": "If government checks are not available in your country, consult your church for an equivalent letter.",
    "safeguarding_note": "Church/NGO child-protection courses are acceptable if recognized locally.",
}

# ------------------------------
# Public API
# ------------------------------
def get_policy(service_code: str | None = None):
    """
    Return policy + labels (+ legend) for all services or a single service.
    This keeps backward compatibility (labels) while adding an optional legend.
    """
    if service_code:
        return {
            "policy": SERVICE_DOC_POLICY.get(service_code, {"paths": []}),
            "labels": EVIDENCE_LABELS,
            "legend": LEGEND,
        }
    return {
        "policy": SERVICE_DOC_POLICY,
        "labels": EVIDENCE_LABELS,
        "legend": LEGEND,
    }
