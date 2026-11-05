"""Rule-based emergency screening for CivicCare AI.

This module flags potential emergencies for urgent human review.
It does not replace emergency services or professional assessment.
"""

import re


EMERGENCY_RULES = {
    "fire": re.compile(
        r"\b(fire|building is burning|smoke coming from)\b",
        re.IGNORECASE,
    ),
        "injury_or_immediate_danger": re.compile(
        r"\b(injured|seriously hurt|trapped person|person trapped|"
        r"trapped inside|person is trapped|people trapped|"
        r"someone is trapped|person stuck inside|"
        r"someone is injured|person is unconscious|"
        r"unconscious person|serious injury|medical emergency)\b",
        re.IGNORECASE,
    ),
    "structural_collapse": re.compile(
        r"\b(collapse|collapsed building|building collapsing|"
        r"wall collapsing|structure collapsing)\b",
        re.IGNORECASE,
    ),
    "electrical_hazard": re.compile(
        r"\b(live wire|exposed live wire|fallen electric wire|"
        r"electrical wire is sparking|electric wire sparking)\b",
        re.IGNORECASE,
    ),
    "severe_flooding": re.compile(
        r"\b(severe flooding|flood water entering homes|"
        r"people trapped by flood|flooding trapping residents)\b",
        re.IGNORECASE,
    ),
    "landslide": re.compile(
        r"\b(landslide|landsliding|slope collapse)\b",
        re.IGNORECASE,
    ),
}


def screen_emergency(description: str) -> dict:
    """Flag potential emergencies for urgent human review."""

    text = " ".join((description or "").split())

    if not text:
        return {
            "emergency_review_required": False,
            "matched_indicators": [],
            "priority": "normal",
            "message": "No description provided.",
        }

    matched = [
        name
        for name, pattern in EMERGENCY_RULES.items()
        if pattern.search(text)
    ]

    if matched:
        return {
            "emergency_review_required": True,
            "matched_indicators": matched,
            "priority": "urgent_review",
            "message": (
                "Potential emergency indicator detected. "
                "Arrange urgent human assessment and follow applicable "
                "emergency procedures. This automated screening is not "
                "confirmation of an emergency or emergency-service dispatch."
            ),
        }

    return {
        "emergency_review_required": False,
        "matched_indicators": [],
        "priority": "normal",
        "message": (
            "No configured emergency phrase was detected. "
            "This does not guarantee that the complaint is safe or routine."
        ),
    }