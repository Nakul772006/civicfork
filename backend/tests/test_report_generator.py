"""Tests for ReportLab PDF report generation and the /api/report endpoint.

Verifies:
1. Prerequisite enforcement (session existence, plot analysis, simulation).
2. End-to-end 6-page PDF generation via POST /api/report.
3. Deterministic fallback behavior when AI narrative is disabled or unavailable.
4. Authoritative data consistency across all 6 pages.
"""

import base64
import re
import zlib
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

MYSURU_PLOT = {
    "lat": 12.3100,
    "lng": 76.6500,
    "radius_m": 2000,
    "area_sqm": 3500.0,
    "label": "Mysuru Saraswathipuram Parcel",
}


def _extract_pdf_text_streams(pdf_bytes: bytes) -> str:
    """Extract and decompress all text stream contents from ReportLab ASCII85/Flate PDF."""
    matches = re.findall(rb"stream\r?\n(.*?)\r?~>endstream", pdf_bytes, re.DOTALL)
    extracted = ""
    for s in matches:
        payload = s.strip() + b"~>"
        decoded = base64.a85decode(payload, adobe=True)
        decomp = zlib.decompress(decoded).decode("latin1", errors="ignore")
        extracted += decomp + "\n"
    return extracted


def test_report_prerequisites_enforcement():
    """Verify endpoint rejects missing sessions or incomplete workflow stages."""
    # 1. Non-existent session
    res = client.post(
        "/api/report",
        json={"session_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "SESSION_NOT_FOUND"

    # 2. Session created with analyze, but simulate not run
    ana_res = client.post("/api/analyze", json=MYSURU_PLOT)
    assert ana_res.status_code == 200
    session_id = ana_res.json()["data"]["session_id"]

    res_missing_sim = client.post(
        "/api/report",
        json={"session_id": session_id},
    )
    assert res_missing_sim.status_code == 400
    assert res_missing_sim.json()["error"]["code"] == "MISSING_PREREQUISITE"
    assert res_missing_sim.json()["error"]["details"]["missing_field"] == "score_matrix"


def test_report_generation_with_deterministic_fallback():
    """Verify PDF generates cleanly with deterministic fallback (include_narrative=False)."""
    # 1. Analyze
    ana_res = client.post("/api/analyze", json=MYSURU_PLOT)
    assert ana_res.status_code == 200
    session_id = ana_res.json()["data"]["session_id"]

    # 2. Simulate
    sim_res = client.post("/api/simulate", json={"session_id": session_id})
    assert sim_res.status_code == 200

    # 3. Rank
    rank_res = client.post(
        "/api/rank",
        json={
            "session_id": session_id,
            "weights": {
                "traffic": 1.0,
                "cost": 1.0,
                "environmental": 2.0,
                "accessibility": 1.0,
                "gap_improvement": 2.0,
                "social_utility": 1.5,
            },
        },
    )
    assert rank_res.status_code == 200
    ranking = rank_res.json()["data"]["ranking"]
    assert len(ranking) == 7
    top_scenario = ranking[0]

    # 4. Generate report without AI narrative
    rep_res = client.post(
        "/api/report",
        json={"session_id": session_id, "include_narrative": False},
    )
    assert rep_res.status_code == 200
    assert rep_res.headers["content-type"] == "application/pdf"
    assert "inline; filename=" in rep_res.headers["content-disposition"]

    pdf_bytes = rep_res.content
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 10000

    # Check that exactly 6 pages were compiled
    raw_pdf = pdf_bytes.decode("latin1", errors="ignore")
    page_counts = re.findall(r"/Count\s+(\d+)", raw_pdf)
    assert "6" in page_counts, f"Expected 6 pages, found: {page_counts}"

    # Extract decompressed stream text
    extracted_text = _extract_pdf_text_streams(pdf_bytes)
    assert "CIVICFORK" in extracted_text
    assert "EXECUTIVE URBAN POLICY ASSESSMENT" in extracted_text
    assert "URBAN CONTEXT" in extracted_text
    assert "INFRASTRUCTURE GAP ANALYSIS" in extracted_text
    assert "POLICY SCENARIO COMPARISON" in extracted_text
    assert "COUNTERFACTUAL POLICY DECISION" in extracted_text
    assert "METHODOLOGY" in extracted_text

    # Check top scenario name appears in PDF
    assert top_scenario["scenario_name"] in extracted_text


def test_report_generation_end_to_end_with_narrative():
    """Verify full end-to-end report generation with AI narrative enabled."""
    # 1. Analyze
    ana_res = client.post("/api/analyze", json=MYSURU_PLOT)
    assert ana_res.status_code == 200
    session_id = ana_res.json()["data"]["session_id"]

    # 2. Simulate
    sim_res = client.post("/api/simulate", json={"session_id": session_id})
    assert sim_res.status_code == 200

    # 3. Feasibility check
    feas_res = client.post("/api/feasibility", json={"session_id": session_id})
    assert feas_res.status_code == 200

    # 4. Counterfactual comparison
    cf_res = client.post(
        "/api/counterfactual",
        json={
            "session_id": session_id,
            "scenario_a_id": "park",
            "scenario_b_id": "healthcare",
        },
    )
    assert cf_res.status_code == 200

    # 5. Rank
    rank_res = client.post(
        "/api/rank",
        json={
            "session_id": session_id,
            "weights": {
                "traffic": 1.0,
                "cost": 1.0,
                "environmental": 1.0,
                "accessibility": 1.0,
                "gap_improvement": 1.0,
                "social_utility": 1.0,
            },
        },
    )
    assert rank_res.status_code == 200

    # 6. Generate report with narrative enabled
    rep_res = client.post(
        "/api/report",
        json={"session_id": session_id, "include_narrative": True},
    )
    assert rep_res.status_code == 200
    assert rep_res.headers["content-type"] == "application/pdf"

    pdf_bytes = rep_res.content
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 10000

    raw_pdf = pdf_bytes.decode("latin1", errors="ignore")
    page_counts = re.findall(r"/Count\s+(\d+)", raw_pdf)
    assert "6" in page_counts, f"Expected 6 pages, found: {page_counts}"
