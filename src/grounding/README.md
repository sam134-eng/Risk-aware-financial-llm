# Evidence grounding checker

Deterministic check that every number in a FinVerify-SMT JSON IR comes from
the case's evidence. No LLM calls.

```python
from src.grounding import check_grounding
result = check_grounding(ir, case)          # case = one record of combined_benchmark_500.json
result.grounding_status                     # PASS | PARTIAL | FAIL | NOT_APPLICABLE
result.to_dict()                            # full trace, JSON-serialisable
```

## What it checks

| Check | How | Error code |
|---|---|---|
| Source existence | reference resolves to a real cell / text item / evidence field | `INVALID_SOURCE` |
| Numerical match | IR value equals a number in the referenced evidence; commas, `$ £ €`, `%`, decimals, minus signs, accounting parentheses, FinQA duplicates `-1.7 ( 1.7 )` handled | `VALUE_MISMATCH`, `SIGN_MISMATCH`, `NO_NUMBER_IN_SOURCE` |
| Unit consistency | IR unit parsed (`million_usd`, `usd`, `percent`, `ratio`, `bp`, `thousand_shares` …); source scale read from "( in millions )" headers or a scale word after the number ("$ 7.0 billion"); conversions applied when deterministic | `UNIT_ERROR`, `UNKNOWN_UNIT` |
| Completeness | every non-derived, non-constant variable has a source; names used in equations are defined; literal numbers in equations are standard constants (0–5, 12, 100, 360, 365, 1e3, 1e4, 1e6, 1e9, −1) | `MISSING_SOURCE`, `UNDEFINED_VARIABLE`, `UNSUPPORTED_CONSTANT` |
| Traceability | per variable: reference, evidence text, original string, IR value, normalised value, units, character span, notes | – |

Statuses: **FAIL** if any mismatch, invalid reference or unit error;
otherwise **PARTIAL** if anything is unsourced; otherwise **PASS**.
**NOT_APPLICABLE** for malformed IR or IR with nothing to ground.

Options: `sign_policy="strict"` (default; opposite sign = FAIL) or `"warn"`
(accept the magnitude, add a `SIGN_DIFFERS` note); `rel_tolerance` guards
float noise only (default 1e-12). Rounded values are **not** accepted as
grounded.

## Source reference convention (to confirm with Chaewon / PR #1)

| Reference | Meaning |
|---|---|
| `table_row_R_col_C` | one cell; R, C 0-based; row 0 = first stored row |
| `table_R` | whole row (FinQA `gold_inds` convention) |
| `text_N` | item N of `pre_text + post_text` (FinQA convention; verified on all 811 gold references) |
| `pre_text_N`, `post_text_N` | item N of that list |
| `question` | numbers stated in the question |
| `evidence.NAME` | structured evidence of the manual cases |

Variables may set `"kind": "constant"` or `"kind": "derived"`; equation
left-hand sides are treated as derived automatically.

## Evaluation (snapshot eb65d01, benchmark SHA-256 bb79a6db…)

`python -m src.experiments.run_grounding_evaluation` builds a reference IR
from each FinQA gold program (`gold_ir.py`; testing only, never a system
input) and injects one error into the first sourced variable.

| Condition | Expected | As expected |
|---|---|---|
| Reference IR (no error) | PASS | 463 / 468 (98.9%) |
| Value × 1000 | FAIL | 468 / 468 |
| Sign flipped | FAIL | 468 / 468 |
| Last digit changed | FAIL | 466 / 468 |
| Points to another evidence item | FAIL | 468 / 468 |
| Source removed | PARTIAL | 468 / 468 |
| Neighbouring cell used *and* cited | PASS (by design) | 253 / 254 |

16 FinQA cases use table operations (`table_max` etc.) and 16 manual cases
are not converted. The 5 reference-IR cases that are PARTIAL are real: the
FinQA gold program writes a document fact as a constant (e.g. F_026 uses
`const_7` for "$ 7.0 billion"), which has no source.

## Limitations

* **Grounding ≠ correctness.** The last row above shows it: a model that takes
  the 2010 value instead of 2011 *and cites the 2010 cell* passes grounding.
  Metric, numerator/denominator, period and direction need the separate
  financial-semantic check.
* **Text-span references are coarse.** The 2 missed digit changes (F_154,
  F_481) changed a value into another number in the same sentence. Cell
  references avoid this; for text, character offsets would.
* **Scale is found in 289 of 484 FinQA cases** (214 millions, 67 thousands,
  8 billions). Elsewhere the unit is reported as unverified, not as an error,
  except when the value is off from the source by a power of 1000.
* The error-injection results use simple, synthetic errors on reference IR;
  they show the checks work but are not an estimate of real LLM error rates.
  Unit logic is tested with unit tests and three real cases, not at scale.
* Currency conversion (USD↔EUR) is never assumed.
