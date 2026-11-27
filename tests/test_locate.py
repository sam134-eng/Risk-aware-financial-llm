from src.grounding.locate import locate_number


def test_locate_classes(bench):
    c = bench["F_026"]
    assert locate_number("997", c).match_class == "EVIDENCE_EXACT"
    assert locate_number("7000", c).match_class == "EVIDENCE_RESCALED"        # $ 7.0 billion as millions
    c = bench["F_183"]
    r = locate_number("0.03", c)
    assert r.match_class == "DERIVED_FROM_EVIDENCE" and "1.11" in r.note
    assert locate_number("123456.7", c).match_class == "NOT_FOUND"
    assert locate_number("100000", bench["F_151"]).match_class == "QUESTION"
    assert locate_number("0.05", bench["F_277"]).match_class == "EVIDENCE_PERCENT_AS_RATIO"
    assert locate_number("16.769", bench["F_278"], earlier_values=["16.769"]).match_class == "MODEL_INTERMEDIATE"
