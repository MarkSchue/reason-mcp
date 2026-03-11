"""Seed data for the Praxisbesetzung domain.

Staff scheduling rules for a medical practice.
"""

from __future__ import annotations

RULES: list[dict] = [
    {
        "rule_id": "PRAX-1",
        "domain": "Praxisbesetzung",
        "active": True,
        "trigger": {
            # These keywords fire when someone asks about availability / absence
            "keywords": ["Urlaub", "Krankheit"],
        },
        "conditions": {
            "natural_language": (
                "Fr. Meier arbeitet von Montags bis Mittwochs von 08:00 bis 10:00 Uhr"
            ),
        },
        "reasoning": {
            "possible_causes": [
                "Mitarbeiterin ist nur Montag bis Mittwoch bis 10:00 Uhr tätig",
                "Fehlende Verfügbarkeit außerhalb der Arbeitszeiten",
            ],
            "confidence_prior": 0.95,
        },
        "recommendation": {
            "action": "Versuchen Sie Hr. Müller zu erreichen",
            "urgency": "medium",
        },
        "scoring": {"severity": 3, "specificity": 0.9},
        "metadata": {"created_by": "Markus", "created_at": "2026-03-10T12:00:00Z"},
    },
    {
        "rule_id": "PRAX-2",
        "domain": "Praxisbesetzung",
        "active": True,
        "trigger": {
            "keywords": ["Urlaub", "Krankheit"],
        },
        "conditions": {
            "natural_language": (
                "Hr. Müller arbeitet von Donnerstags und Freitags von 08:00 bis 10:00 Uhr"
            ),
        },
        "reasoning": {
            "possible_causes": [
                "Mitarbeiter ist nur Donnerstag und Freitag bis 10:00 Uhr tätig",
                "Fehlende Verfügbarkeit außerhalb der Arbeitszeiten",
            ],
            "confidence_prior": 0.95,
        },
        "recommendation": {
            "action": "Versuchen Sie Fr. Meier zu erreichen",
            "urgency": "medium",
        },
        "scoring": {"severity": 3, "specificity": 0.9},
        "metadata": {"created_by": "Markus", "created_at": "2026-03-10T12:00:00Z"},
    },
]

EDGES: list[dict] = [
    # PRAX-1 and PRAX-2 are mutual fallbacks — when one is unavailable, try the other
    {
        "from_rule_id": "PRAX-1",
        "to_rule_id": "PRAX-2",
        "type": "fallback",
        "description": "If Fr. Meier is unavailable, contact Hr. Müller as fallback.",
    },
    {
        "from_rule_id": "PRAX-2",
        "to_rule_id": "PRAX-1",
        "type": "fallback",
        "description": "If Hr. Müller is unavailable, contact Fr. Meier as fallback.",
    },
]
