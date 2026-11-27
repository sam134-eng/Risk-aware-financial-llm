### Table 1. Main benchmark (GPT-4o-mini, stored answers)

| Model | Cases | Answer acc. (lenient) | Answer acc. (strict) | Grounding: inputs supported | Equation (arithmetic) acc. | Metric acc. | Valid IR rate | Latency |
|---|---|---|---|---|---|---|---|---|
| gpt-4o-mini | 500 benchmark | 72.3% (349/483) | 57.8% (279/483) | not measured | not measured | not measured | n/a | not recorded |
| gpt-4o-mini | 80 selected | 58.7% (44/75) | 44.0% (33/75) | 70.6% (48/68) found in evidence; 94.1% (64/68) traced incl. derived/earlier steps | 76.5% (26/34) equations | not measured (needs judge/human) | n/a (free text); Stage 1 extraction 33.8% (27/80) cases | not recorded |

Denominators exclude cases whose gold is not a single value (manual multi-part cases, F_037). Lenient = correct at gold precision, within 1%, or sign stated in words. Grounding and arithmetic are on the equations Stage 1 v2 extracted (68 inputs, 34 equations, 27 cases). Other models were not run: no API access.


### Table 2. Error categories, 80 selected cases (GPT-4o-mini; multi-label)

| Group | Category | Cases | % of 80 | Detected by | Needs human review | Examples |
|---|---|---|---|---|---|---|
| Benchmark | gold_reference_issue | 13 | 16.2 | gold audit + manual review | False | F_048, F_147, F_151, F_162, F_183 |
| Evidence | unit_or_scale_error | 1 | 1.2 | answer evaluator | False | F_073 |
| Evidence | unsupported_number | 3 | 3.8 | grounding locator | True | F_071, F_011, F_015 |
| Arithmetic | arithmetic_error | 7 | 8.8 | Stage 1 v2 (Z3) | False | F_027, F_125, F_127, F_278, F_426 |
| Arithmetic | rounding_only | 7 | 8.8 | answer evaluator | False | F_017, F_027, F_076, F_131, F_160 |
| Financial reasoning | sign_or_direction_error | 2 | 2.5 | answer evaluator | False | F_067, F_292 |
| Financial reasoning | wrong_value_unexplained | 22 | 27.5 | answer evaluator | True | F_048, F_057, F_086, F_089, F_128 |
| LLM behaviour | refusal | 2 | 2.5 | answer evaluator | False | F_377, F_430 |
| LLM behaviour | no_final_answer | 3 | 3.8 | answer evaluator | False | F_174, F_370, F_434 |
| Formalization | not_formalizable_by_stage1 | 53 | 66.2 | Stage 1 v2 | False | F_037, F_048, F_057, F_067, F_073 |


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


### Table 4. GPT-4o-mini answer accuracy by reasoning pattern (500 cases)

| Pattern | Evaluated | Lenient accuracy |
|---|---|---|
| ratio_or_share | 162 | 80.2% |
| percentage_change | 116 | 82.8% |
| difference | 59 | 61.0% |
| multi_step | 37 | 46.0% |
| sum | 33 | 66.7% |
| product | 25 | 52.0% |
| other_two_step | 24 | 75.0% |
| table_aggregation | 16 | 43.8% |
| comparison_yes_no | 11 | 90.9% |

The 16 manual cases have multi-part gold answers and are not scored automatically.


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


### Table 6. FinQA gold answers vs their own reference programs (484 cases)

| Result | Cases |
|---|---|
| CONSISTENT | 364 |
| NOT_CHECKED | 76 |
| INCONSISTENT | 30 |
| ROUNDING_DIFFERENCE | 14 |

INCONSISTENT cases: F_021, F_036, F_049, F_068, F_110, F_112, F_141, F_147, F_151, F_155, F_156, F_183, F_195, F_222, F_241, F_270, F_316, F_332, F_368, F_369, F_379, F_394, F_410, F_415, F_418, F_430, F_440, F_442, F_474, F_488


### Table 7. Where the 68 equation inputs extracted from GPT-4o-mini answers come from

| Match class | Inputs |
|---|---|
| EVIDENCE_EXACT | 40 |
| DERIVED_FROM_EVIDENCE | 13 |
| NOT_FOUND | 4 |
| MODEL_INTERMEDIATE | 3 |
| EVIDENCE_SCALED | 3 |
| EVIDENCE_PERCENT_AS_RATIO | 2 |
| EVIDENCE_RESCALED | 1 |
| EVIDENCE_SIGN_DIFFERS | 1 |
| QUESTION | 1 |
