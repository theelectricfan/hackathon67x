import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from skills.skill_content import run_skill_content


def _ctx(**kwargs):
    base = {
        "eto_ofr_title": "Need 50kg industrial grade cement bags",
        "eto_ofr_desc": "Looking for OPC 53 grade cement bags for construction project starting next month",
        "eto_ofr_quality": "H",
        "rag_score_total": 72,
        "isq_fill_rate": 0.75,
        "title_word_count": 8,
        "desc_word_count": 16,
        "ofr_quantity": "50",
        "ofr_unit": "Bag",
    }
    base.update(kwargs)
    return base


def test_good_content_low_confidence():
    r = run_skill_content(_ctx())
    assert r["confidence"] < 40


def test_low_isq_fill_flags_thin():
    r = run_skill_content(_ctx(isq_fill_rate=0.1, title_word_count=1))
    assert r["confidence"] >= 50
    assert "isq_fields" in " ".join(r.get("missing_fields", []))


def test_very_thin_returns_without_llm():
    r = run_skill_content(_ctx(
        isq_fill_rate=0.1, title_word_count=1,
        desc_word_count=2, eto_ofr_quality="L",
        rag_score_total=2, ofr_quantity=None, ofr_unit=None,
    ))
    assert r["confidence"] > 80
    assert r["bucket"] == "THIN_CONTENT"


def test_missing_quantity_flagged():
    r = run_skill_content(_ctx(ofr_quantity=None, ofr_unit=None))
    assert "ofr_quantity" in r.get("missing_fields", [])
