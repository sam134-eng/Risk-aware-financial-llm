### Table 5. Grounding checker on reference IR with injected errors (FinQA, 468 cases)

| Condition | Expected | As expected | Rate |
|---|---|---|---|
| baseline | PASS | 463/468 | 98.9% |
| scale_x1000 | FAIL | 468/468 | 100.0% |
| sign_flip | FAIL | 468/468 | 100.0% |
| transcription | FAIL | 466/468 | 99.6% |
| wrong_reference | FAIL | 468/468 | 100.0% |
| missing_source | PARTIAL | 468/468 | 100.0% |
| wrong_period_cited | PASS | 253/254 | 99.6% |

Synthetic single errors; shows the checks work, not real model error rates. wrong_period_cited passing is the documented limitation (grounding cannot see period errors).
