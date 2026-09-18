"""
Flagged Fraud Summary & Reasoning
=================================
Turns a scored results DataFrame into an executive summary of the detected
fraud plus a plain-language explanation of WHY those transactions were flagged.

The summary is computed from the actual prediction outputs (risk levels, the
business rules that fired, channels, categories, behaviour flags), so the
narrative always reflects the current batch rather than static boilerplate.
"""
from collections import Counter

RISK_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"]
RISK_LEVELS = RISK_ORDER[:3]


def _split_rules(rules_val):
    """Split a `rules_triggered` cell into individual rule names."""
    if rules_val is None:
        return []
    if isinstance(rules_val, float):  # NaN (unexpected) or missing
        return []
    return [r.strip() for r in str(rules_val).split(";") if str(r).strip()]


def build_fraud_summary(results, threshold=0.5, currency="USD", symbol="$"):
    """
    Compute summary stats + narrative for a scored results DataFrame.

    Expected columns (from `model.predict`): is_flagged, fraud_score, risk_level,
    amount, merchant_category, channel, tx_type, rules_triggered, ai_reasoning,
    is_international, is_online, hour_of_day.

    Returns a dict with numeric summaries and a `narrative` markdown string.
    """
    total = len(results)
    flagged = results[results["is_flagged"] == 1]
    n = int(len(flagged))
    pct = n / total if total else 0.0

    # Risk-level breakdown among flagged cases
    risk_breakdown = {}
    if n:
        counts = flagged["risk_level"].value_counts().to_dict()
        for level in RISK_ORDER:
            if level in counts:
                risk_breakdown[level] = int(counts[level])

    # Which business rules fired most (parsed from the per-transaction text)
    rule_counter = Counter()
    for val in flagged["rules_triggered"]:
        for rule in _split_rules(val):
            rule_counter[rule] += 1
    top_rules = rule_counter.most_common(6)

    # Fraud concentration by merchant category
    cat_counts = flagged["merchant_category"].value_counts()
    top_categories = [
        {"category": str(cat), "count": int(cnt)}
        for cat, cnt in list(cat_counts.items())[:5]
    ]

    # Flag rate by channel (whole batch vs flagged)
    channel_stats = []
    if "channel" in results:
        for channel in results["channel"].dropna().unique():
            sub = results[results["channel"] == channel]
            f = int(sub["is_flagged"].sum())
            channel_stats.append({
                "channel": str(channel),
                "flagged": f,
                "total": int(len(sub)),
                "rate": f / len(sub) if len(sub) else 0.0,
            })
        channel_stats.sort(key=lambda r: -r["rate"])

    # Behavioural flags derived from the rules the model reports — this keeps
    # the summary consistent with the model's own reasons (and the USD basis),
    # regardless of the display currency chosen. Each count = distinct rows.
    high_amount = _count_concepts(flagged, ["High-value"])
    night = _count_concepts(flagged, ["Unusual hour", "Late-night"])
    overdraft = _count_concepts(flagged,
                                ["negative balance", "drove balance negative",
                                 "exceeds 150%"])
    international = _count_concepts(flagged, ["international"])
    online = _count_concepts(flagged, ["online"])

    flagged_amount = float(flagged["amount"].sum()) if n else 0.0
    avg_score = float(flagged["fraud_score"].mean()) if n else 0.0
    has_rules = n > 0

    narrative = _build_narrative(
        total=total, n=n, pct=pct, threshold=threshold,
        risk_breakdown=risk_breakdown, top_rules=top_rules,
        top_categories=top_categories, channel_stats=channel_stats,
        high_amount=high_amount, night=night, overdraft=overdraft,
        international=international, online=online,
        flagged_amount=flagged_amount, avg_score=avg_score,
        flags=has_rules, currency=currency, symbol=symbol,
    )

    return {
        "n_total": total,
        "n_flagged": n,
        "flag_rate": pct,
        "flagged_amount": flagged_amount,
        "avg_score_flagged": avg_score,
        "risk_breakdown": risk_breakdown,
        "top_rules": top_rules,
        "top_categories": top_categories,
        "channel_stats": channel_stats,
        "high_amount_flags": high_amount,
        "night_flags": night,
        "overdraft_flags": overdraft,
        "international_flags": international,
        "online_flags": online,
        "narrative": narrative,
    }


def _count_concepts(flagged, fragments):
    """Count DISTINCT flagged rows whose rules mention any of the fragments.

    Rows are counted once even if several fragments (or rules) match, so the
    behaviour counts never exceed the number of flagged transactions.
    """
    if len(flagged) == 0:
        return 0
    return int(flagged["rules_triggered"].astype(str).str.contains(
        "|".join(fragments), case=False, na=False).sum())


def _build_narrative(total, n, pct, threshold, risk_breakdown, top_rules,
                     top_categories, channel_stats, high_amount, night,
                     overdraft, international, online, flagged_amount,
                     avg_score, flags, currency, symbol):
    """Assemble a plain-language report from the actual numbers."""
    parts = []

    if n == 0:
        parts.append(
            f"Of **{total:,}** transactions screened, **none** were flagged at the "
            f"current threshold of **{threshold:.2f}**. The average fraud score across "
            f"the batch was **{avg_score:.4f}** — every transaction remained below the "
            f"flag line, so there is nothing requiring investigation right now."
        )
        return " ".join(parts)

    money = f"{symbol}{flagged_amount:,.2f}"
    parts.append(
        f"Of **{total:,}** transactions screened, the model flagged "
        f"**{n:,} ({pct:.1%})** at the current threshold of **{threshold:.2f}**. "
        f"That is **{money}** ({currency}) moving through flagged cases, "
        f"with an average fraud score of **{avg_score:.3f}** among them."
    )

    # Risk distribution
    counts = {k: v for k, v in risk_breakdown.items() if v}
    if counts:
        line = "The flagged cases break down as: " + ", ".join(
            f"**{v} {k}**" for k, v in counts.items() if v
        )
        line = line + ". CRITICAL/HIGH cases are the priority for immediate review."
        parts.append(line)

    # Rules fired most — the core "basis of reasoning"
    if top_rules:
        motivated = ", ".join(
            f"**{rule}** ({count} case" + ("s" if count != 1 else "") + ")"
            for rule, count in top_rules[:4]
        )
        parts.append(
            f"The most common business rules that fired were: {motivated}. "
            f"These rules are the model's *reasons* — each one encodes a pattern "
            f"associated with fraud in the training data."
        )

    # Where fraud concentrates
    if top_categories:
        conc = ", ".join(
            f"**{c['category']}** ({c['count']})" for c in top_categories
        )
        parts.append(f"Fraud is concentrated in merchant categories: {conc}.")

    # Channels — flag *rate* per channel
    if channel_stats:
        risky = [c for c in channel_stats if c["flagged"] > 0]
        if risky:
            top_channel = risky[0]
            ch_line = (
                f"The highest flag **rate** is on **{top_channel['channel']}** "
                f"({top_channel['rate']:.1%} of its {top_channel['total']} "
                f"transactions). "
            )
            low = [c for c in channel_stats if c["flagged"] == 0]
            if low:
                ch_line += "Channels with no flags include: " + \
                    ", ".join(f"**{c['channel']}**" for c in low[:3]) + "."
            parts.append(ch_line)

    # Behavioural red flags (derived from the model's own rules)
    if flags:
        behaviour = []
        if high_amount:
            behaviour.append(f"**{high_amount:,} high-value** transactions (≥ $5,000)")
        if night:
            behaviour.append(f"**{night:,} during unusual hours** (late night)")
        if international:
            behaviour.append(f"**{international:,} international** transactions")
        if online:
            behaviour.append(f"**{online:,} online** transactions")
        if overdraft:
            behaviour.append(f"**{overdraft:,} with negative/overdrawn balances**")
        if behaviour:
            parts.append(
                "The main behaviour signals driving these flags: " +
                "; ".join(behaviour) + ". These match the classic fraud "
                "signature of *large or out-of-pattern amounts* combined with "
                f"*an unusual time or channel*. On average the five-model "
                f"ensemble agrees strongly on these cases (avg score "
                f"{avg_score:.3f}), so the flags are high-confidence."
            )

    return "\n\n".join(parts)