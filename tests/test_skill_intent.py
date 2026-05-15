import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from skills.skill_intent import run_skill_intent


def _ctx(**kwargs):
    base = {
        "is_auto_generated": False, "is_guest_login": False,
        "is_call_verified": True, "is_late_night": False,
        "posting_hour": 10, "products_viewed_before_posting": 5,
        "user_identifier_flag": 1, "posting_platform": "Desktop",
        "glusr_usr_listing_status": "active", "fcp_flag": 1,
    }
    base.update(kwargs)
    return base


def test_high_intent_buyer():
    r = run_skill_intent(_ctx())
    assert r["confidence"] <= 10
    assert r["intent_score"] == 100


def test_auto_generated_lowers_score():
    r = run_skill_intent(_ctx(is_auto_generated=True))
    assert r["intent_score"] == 70
    assert "auto_generated" in r["triggered_signals"][0]


def test_guest_login_lowers_score():
    r = run_skill_intent(_ctx(is_guest_login=True))
    assert r["intent_score"] == 80


def test_very_low_intent_all_signals():
    r = run_skill_intent(_ctx(
        is_auto_generated=True, is_guest_login=True,
        is_call_verified=False, is_late_night=True,
        products_viewed_before_posting=0,
        user_identifier_flag=0, posting_platform="Msite",
        glusr_usr_listing_status="inactive", fcp_flag=0,
    ))
    assert r["intent_score"] == 0
    assert r["confidence"] == 90


def test_msite_triggers():
    r = run_skill_intent(_ctx(posting_platform="Msite"))
    assert r["intent_score"] == 90
    assert any("Msite" in s for s in r["triggered_signals"])
