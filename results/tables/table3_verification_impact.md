### Table 3. What each verification step covers, and answer correctness of what it accepts

| Configuration (implemented) | Scope | Cases accepted | Of which answer correct (lenient) |
|---|---|---|---|
| Original Z3 verifier: PASS | 500 | 122 | 76.2% (93/122) |
| Original Z3 verifier: FAIL | 500 | 24 | 50.0% (12/24) |
| Original Z3 verifier: NOT_APPLICABLE | 500 | 337 | 72.4% (244/337) |
| Stage 1 v2: equations extracted | 80 | 27 | – |
| Stage 1 v2: all equations arithmetic PASS | 80 | 20 | – |
| + grounding: arithmetic PASS and inputs supported | 80 | 19 | 63.2% (12/19) |

Grounding+arithmetic does not certify the answer: of the 7 accepted-but-wrong cases, 5 have a questionable gold answer (F_147, F_151, F_183, F_376, F_488) and F_089 uses the wrong denominator.
