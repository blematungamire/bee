"""Unit tests for the flagged-fraud summary & reasoning generator."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest
import pandas as pd

from fraud_summary import build_fraud_summary, _split_rules


def _make_results(rows):
    """Build a minimal results DataFrame with the columns the summary uses."""
    return pd.DataFrame(rows)


def _row(tid, score, flagged, risk, amount, cat, channel, hour, rules,
         international=0, online=0):
    return {
        "transaction_id": tid,
        "fraud_score": score,
        "is_flagged": flagged,
        "risk_level": risk,
        "amount": amount,
        "merchant_category": cat,
        "channel": channel,
        "hour_of_day": hour,
        "is_international": international,
        "is_online": online,
        "rules_triggered": rules,
        "ai_reasoning": "",
    }


def _sample(n_clear=95, n_flag=5):
    rows = []
    for i in range(n_clear):
        rows.append(_row(f"c{i}", 0.05, 0, "MINIMAL", 100.0,
                         "grocery", "POS", 12, None))
    for i in range(n_flag):
        rows.append(_row(f"f{i}", 0.85, 1, "CRITICAL", 5000.0,
                         "electronics", "Online", 2,
                         "High-value transaction ($5,000); Unusual hour "
                         "(night, outside 06:00-22:00); Online + international "
                         "(typical fraud vector)", international=1, online=1))
    return _make_results(rows)


def test_split_rules():
    assert _split_rules("A; B ;C") == ["A", "B", "C"]
    assert _split_rules(None) == []
    assert _split_rules("") == []


def test_counts_match_input():
    s = build_fraud_summary(_sample())
    assert s["n_total"] == 100
    assert s["n_flagged"] == 5
    assert s["flag_rate"] == 0.05
    assert s["flagged_amount"] == pytest.approx(25000.0)


def test_risk_breakdown():
    s = build_fraud_summary(_sample())
    assert s["risk_breakdown"].get("CRITICAL") == 5


def test_no_flags_report():
    s = build_fraud_summary(_sample(n_clear=50, n_flag=0))
    assert s["n_flagged"] == 0
    assert s["n_total"] == 50
    assert "none" in s["narrative"].lower()


def test_top_rules_parsed():
    s = build_fraud_summary(_sample())
    names = [r for r, _ in s["top_rules"]]
    assert any("High-value" in n for n in names)
    assert any("Unusual hour" in n for n in names)


def test_behaviour_counts_from_rules():
    s = build_fraud_summary(_sample())
    assert s["high_amount_flags"] == 5
    assert s["night_flags"] == 5
    assert s["international_flags"] == 5
    assert s["online_flags"] == 5


def test_channel_stats_sorted_desc():
    s = build_fraud_summary(_sample())
    rates = [c["rate"] for c in s["channel_stats"]]
    assert rates == sorted(rates, reverse=True)
    online = next(c for c in s["channel_stats"] if c["channel"] == "Online")
    assert online["flagged"] == 5


def test_narrative_mentions_money_and_threshold():
    s = build_fraud_summary(_sample())
    assert "$25,000" in s["narrative"] or "25,000" in s["narrative"]
    assert "0.50" in s["narrative"]


def test_top_categories():
    s = build_fraud_summary(_sample())
    assert s["top_categories"][0]["category"] == "electronics"


def test_narrative_mentions_reasoning_rules():
    s = build_fraud_summary(_sample())
    assert "High-value" in s["narrative"] or "high-value" in s["narrative"]
    assert "rules" in s["narrative"].lower()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])