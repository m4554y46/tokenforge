"""ACE — Adaptive Compression Engine.

Apprend la perte d'utilité induite par chaque niveau de compression,
et maximise la marge économique nette sous contrainte de qualité.
"""

from backend.ace.decider import Decider
from backend.ace.features import extract_features
from backend.ace.state import (
    CellState, read_cell, read_cells_for_context, write_cell,
    RATES, RATE_TO_PROFILE, RATE_TO_PROFILE as PROFILE_MAP,
    TF_SHARE, FAILURE_COST, TOKEN_PRICE, PROFILE_COMPUTE_COST,
)
from backend.ace.signals import detect_signals, update_from_signals
from backend.ace.tables import ACE_TABLES_SQL, init_ace_tables
from backend.ace.exploration import knowledge_gradient, should_explore
from backend.ace.attribution import attribute, AttributionResult
from backend.ace.embeddings import CompressionEmbeddings
from backend.ace.models.quality_model import QualityModel

__all__ = [
    "Decider", "extract_features",
    "CellState", "read_cell", "read_cells_for_context", "write_cell",
    "RATES", "RATE_TO_PROFILE", "PROFILE_MAP",
    "TF_SHARE", "FAILURE_COST", "TOKEN_PRICE", "PROFILE_COMPUTE_COST",
    "detect_signals", "update_from_signals",
    "ACE_TABLES_SQL", "init_ace_tables",
    "knowledge_gradient", "should_explore",
    "attribute", "AttributionResult",
    "CompressionEmbeddings", "QualityModel",
]
