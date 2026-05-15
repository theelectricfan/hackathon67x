"""Smoke tests for orchestrator — uses mock to avoid real API calls."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
from core.orchestrator import run_rca
from core.bl_context_builder import build_bl_context


SAMPLE_ROW = {
    "eto_ofr_display_id": "BL-TEST-001",
    "eto_ofr_mcat_id": "3291",
    "eto_ofr_title": "Need cement",
    "eto_ofr_desc": "need it",
    "eto_ofr_quality": "L",
    "rag_score_total": 2,
    "eto_ofr_date": "2024-01-15 23:30:00",
    "total_filled_isq_approval": 1,
    "available_isq_at_approval": 8,
    "mcat_id_at_genration": "3291",
    "glcat_mcat_is_generic": 1,
    "eto_enq_typ": 3,
    "user_identifier_flag": 0,
    "fcp_flag": 0,
    "glusr_usr_listing_status": "inactive",
    "eto_ofr_login_mode": 0,
    "eto_ofr_call_verified": 0,
    "ni_count": 6,
    "sellers_received_count": 7,
    "time_to_first_response_hrs": 36,
    "products_viewed_before_posting": 0,
    "posting_platform": "Msite",
    "ni_reason_codes": "Wrong Cat,Spec Mis",
    "photo_mismatch_flag": 1,
}


def _make_mock_response(stop_reason="end_turn", tool_calls=None):
    resp = MagicMock()
    resp.stop_reason = stop_reason
    if tool_calls:
        blocks = []
        for name, tool_id in tool_calls:
            b = MagicMock()
            b.type = "tool_use"
            b.name = name
            b.id = tool_id
            b.input = {}
            blocks.append(b)
        resp.content = blocks
    else:
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "RCA complete."
        resp.content = [text_block]
    return resp


def test_rca_returns_required_keys():
    bl_ctx = build_bl_context(SAMPLE_ROW)
    with patch("core.orchestrator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        tool_resp = _make_mock_response("tool_use", [("run_skill_intent", "tid1")])
        end_resp = _make_mock_response("end_turn")
        instance.messages.create.side_effect = [tool_resp, end_resp]

        result = run_rca(bl_ctx)

    assert "bl_id" in result
    assert "primary_bucket" in result
    assert "primary_confidence" in result
    assert "primary_fix" in result
    assert result["bl_id"] == "BL-TEST-001"


def test_rca_bl_context_computed_fields():
    bl_ctx = build_bl_context(SAMPLE_ROW)
    assert bl_ctx["is_auto_generated"] is True
    assert bl_ctx["is_guest_login"] is True
    assert bl_ctx["is_late_night"] is True
    assert bl_ctx["isq_fill_rate"] == 0.125
    assert bl_ctx["title_word_count"] == 2
