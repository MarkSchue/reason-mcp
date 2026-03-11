"""Configuration loading from environment variables.

ArangoDB credentials are loaded from a ``.env`` file first (via python-dotenv),
and can then be overridden by shell environment variables.  See ``.env.example``
for the full set of supported variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env before reading os.environ — shell variables always win.
load_dotenv()


@dataclass(frozen=True)
class VertexSpec:
    """Schema definition for one vertex collection in a graph database.

    Attributes:
        type_name:  The ``type`` value stored in node documents (e.g. ``"Worker"``).
        collection: ArangoDB collection name (e.g. ``"workers"``).
        key_prefix: Prefix used in ``node_id`` values (e.g. ``"worker_"``).
                    Used to resolve the collection from a bare node key.
    """

    type_name: str
    collection: str
    key_prefix: str


@dataclass(frozen=True)
class EdgeSpec:
    """Schema definition for one edge collection in a graph database.

    Attributes:
        type_name:       The ``type`` value stored in edge documents (e.g. ``"arbeitet"``).
        collection:      ArangoDB edge collection name (e.g. ``"arbeitet"``).
        from_collection: Vertex collection on the tail end of the edge.
        to_collection:   Vertex collection on the head end of the edge.
    """

    type_name: str
    collection: str
    from_collection: str
    to_collection: str


def _parse_vertex_specs(raw: str) -> list[VertexSpec]:
    """Parse ``REASON_PRAXIS_VERTEX_SPECS`` into a list of :class:`VertexSpec`.

    Format: ``TypeName:collection:key_prefix`` entries separated by commas.

    Example::

        Worker:workers:worker_,WorkingHours:working_hours:hours_
    """
    specs = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        type_name, collection, key_prefix = part.split(":")
        specs.append(VertexSpec(type_name.strip(), collection.strip(), key_prefix.strip()))
    return specs


def _parse_edge_specs(raw: str) -> list[EdgeSpec]:
    """Parse ``REASON_PRAXIS_EDGE_SPECS`` into a list of :class:`EdgeSpec`.

    Format: ``TypeName:collection:from_collection:to_collection`` entries separated by commas.

    Example::

        arbeitet:arbeitet:workers:working_hours,vertritt:vertritt:workers:workers
    """
    specs = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        type_name, collection, from_coll, to_coll = part.split(":")
        specs.append(EdgeSpec(type_name.strip(), collection.strip(), from_coll.strip(), to_coll.strip()))
    return specs


class Config:
    """
    Runtime configuration resolved from environment variables.
    Each project deployment sets its own REASON_* env vars (via .env or shell).
    """

    # ArangoDB connection — rules database ("reason")
    arango_url: str
    arango_user: str
    arango_password: str
    arango_db: str
    arango_rules_coll: str
    arango_edges_coll: str

    # ArangoDB — praxis graph database
    praxis_db: str
    praxis_graph_name: str

    # Praxis graph schema — vertex and edge definitions.
    # Driven by REASON_PRAXIS_VERTEX_SPECS and REASON_PRAXIS_EDGE_SPECS.
    # Defaults reproduce the original workers / working_hours / arbeitet / vertritt schema.
    praxis_vertex_specs: list[VertexSpec]
    praxis_edge_specs: list[EdgeSpec]

    # Retrieval defaults
    default_top_k: int
    min_relevance: float
    max_summary_chars: int

    # Observability
    log_level: str
    log_requests: bool
    output_dir: Path

    def __init__(self) -> None:
        # --- ArangoDB (rules) ---
        self.arango_url = os.environ.get("REASON_ARANGO_URL", "http://localhost:8529")
        self.arango_user = os.environ.get("REASON_ARANGO_USER", "root")
        self.arango_password = os.environ.get("REASON_ARANGO_PASSWORD", "")
        self.arango_db = os.environ.get("REASON_ARANGO_DB", "reason")
        self.arango_rules_coll = os.environ.get("REASON_ARANGO_RULES_COLL", "rules")
        self.arango_edges_coll = os.environ.get("REASON_ARANGO_EDGES_COLL", "rule_relations")

        # --- ArangoDB (praxis graph) ---
        self.praxis_db = os.environ.get("REASON_PRAXIS_DB", "praxis")
        self.praxis_graph_name = os.environ.get("REASON_PRAXIS_GRAPH_NAME", "praxis_graph")

        # Graph schema — declarative vertex and edge definitions.
        # Override REASON_PRAXIS_VERTEX_SPECS / REASON_PRAXIS_EDGE_SPECS to adapt
        # the schema for a different domain without touching any code.
        self.praxis_vertex_specs = _parse_vertex_specs(
            os.environ.get(
                "REASON_PRAXIS_VERTEX_SPECS",
                "Worker:workers:worker_,WorkingHours:working_hours:hours_",
            )
        )
        self.praxis_edge_specs = _parse_edge_specs(
            os.environ.get(
                "REASON_PRAXIS_EDGE_SPECS",
                "arbeitet:arbeitet:workers:working_hours,vertritt:vertritt:workers:workers",
            )
        )

        # --- Retrieval ---
        self.default_top_k = int(os.environ.get("REASON_DEFAULT_TOP_K", "3"))
        self.min_relevance = float(os.environ.get("REASON_MIN_RELEVANCE", "0.5"))
        self.max_summary_chars = int(os.environ.get("REASON_MAX_SUMMARY_CHARS", "900"))

        # --- Observability ---
        self.log_level = os.environ.get("REASON_LOG_LEVEL", "INFO").upper()
        # When true, each MCP request is written as a Markdown session log to output_dir.
        self.log_requests: bool = os.environ.get("REASON_LOG_REQUESTS", "").lower() in (
            "1", "true", "yes"
        )
        self.output_dir: Path = Path(
            os.environ.get("REASON_OUTPUT_DIR", "./output")
        ).resolve()


# Module-level singleton – import this wherever config is needed.
config = Config()
