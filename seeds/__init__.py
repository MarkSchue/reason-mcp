"""reason-mcp seed data package.

Each module in this package defines a ``RULES`` list and an ``EDGES`` list for
a specific domain.  Import :data:`RULES` and :data:`EDGES` to get the full set.

Adding a new domain
-------------------
1. Create a new module alongside the existing ones, e.g. ``seeds/my_domain.py``.
2. Define ``RULES: list[dict]`` and ``EDGES: list[dict]`` in it.
3. Import them below and extend ``RULES`` and ``EDGES``.
4. Run the seed script::

       python scripts/seed_arango.py
"""

from __future__ import annotations

from seeds.car_facts import EDGES as _CAR_EDGES
from seeds.car_facts import RULES as _CAR_RULES
from seeds.fleet_and_industrial import EDGES as _FLEET_EDGES
from seeds.fleet_and_industrial import RULES as _FLEET_RULES
from seeds.praxis import EDGES as _PRAX_EDGES
from seeds.praxis import RULES as _PRAX_RULES

# Aggregated sets — extend here when adding new domain modules.
RULES: list[dict] = [
    *_CAR_RULES,
    *_PRAX_RULES,
    *_FLEET_RULES,
]

EDGES: list[dict] = [
    *_CAR_EDGES,
    *_PRAX_EDGES,
    *_FLEET_EDGES,
]
