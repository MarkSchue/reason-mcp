"""Seed data for the CarFacts domain.

Physical car and engine specifications used for vehicle weight/lifting queries.
"""

from __future__ import annotations

RULES: list[dict] = [
    {
        "rule_id": "CAR-1",
        "domain": "CarFacts",
        "active": True,
        "trigger": {
            "keywords": [
                "car", "weight", "load", "fleet", "heavy vehicle", "kg",
                "mustang", "ford",
            ],
        },
        "conditions": {
            "natural_language": "The weight of a Ford Mustang is about 1500 kg.",
        },
        "reasoning": {
            "possible_causes": [
                "Vehicle classification error",
                "Wrong vehicle model",
                "Check the number of vehicles",
            ],
            "confidence_prior": 0.95,
        },
        "recommendation": {
            "action": "Check the vehicle specifications",
            "urgency": "medium",
        },
        "scoring": {"severity": 3, "specificity": 0.9},
        "metadata": {"created_by": "Markus", "created_at": "2026-03-10T12:00:00Z"},
    },
    {
        "rule_id": "CAR-2",
        "domain": "CarFacts",
        "active": True,
        "trigger": {
            "keywords": [
                "car", "weight", "load", "fleet", "heavy vehicle", "kg",
                "porsche", "911",
            ],
        },
        "conditions": {
            "natural_language": "The weight of a Porsche 911 is about 800 kg.",
        },
        "reasoning": {
            "possible_causes": [
                "Vehicle classification error",
                "Wrong vehicle model",
            ],
            "confidence_prior": 0.95,
        },
        "scoring": {"severity": 3, "specificity": 0.9},
        "metadata": {"created_by": "Markus", "created_at": "2026-03-10T12:00:00Z"},
    },
    {
        "rule_id": "CAR-3",
        "domain": "CarFacts",
        "active": True,
        "trigger": {
            "keywords": ["motor", "engine", "lift", "weight", "torque", "siemens", "4711"],
        },
        "conditions": {
            "natural_language": (
                "The electric engine Siemens 4711 can lift up to 2000 kg. "
                "It has a dimension of h=2000mm, w=1000mm, length=500mm "
                "and a weight of 150 kg."
            ),
        },
        "reasoning": {
            "possible_causes": [
                "too much weight to lift",
                "wrong dimensions",
                "engine malfunction",
            ],
            "confidence_prior": 0.90,
        },
        "recommendation": {
            "action": "Verify the weight to be lifted and check engine specifications.",
            "urgency": "high",
        },
        "scoring": {"severity": 2, "specificity": 0.95},
    },
]

EDGES: list[dict] = []
