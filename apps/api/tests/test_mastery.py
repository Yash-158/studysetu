"""modules/mastery.py: pure BKT update function against the golden vectors in
packages/shared/testdata/bkt_vectors.json (README.md: "so the Python implementation and any TS
mirror agree"). No database needed - bkt_update() is a pure function (RULES.md #9: deterministic,
no LLM). packages/shared/bkt_test_vectors.json (repo root, not testdata/) looks like a stray
duplicate from an earlier draft - see MEMORY.md, left alone rather than silently deleted."""
from __future__ import annotations

import json
from pathlib import Path

from app.modules.mastery import bkt_update

_VECTORS_PATH = Path(__file__).resolve().parents[3] / "packages" / "shared" / "testdata" / "bkt_vectors.json"


def test_bkt_matches_golden_vectors():
    data = json.loads(_VECTORS_PATH.read_text())
    for vector in data["vectors"]:
        p_known = 0.3  # database.yaml's bkt.p_init - the vectors were generated starting here
        for correct, expected in zip(vector["sequence"], vector["expected_p_known"]):
            p_known = bkt_update(p_known, correct)
            assert round(p_known, 6) == expected, vector["name"]


def test_bkt_stays_in_bounds():
    p_known = 0.3
    for _ in range(50):
        p_known = bkt_update(p_known, True)
    assert 0.0 <= p_known <= 1.0
    p_known = 0.3
    for _ in range(50):
        p_known = bkt_update(p_known, False)
    assert 0.0 <= p_known <= 1.0
