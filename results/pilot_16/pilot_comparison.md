# 16-case autoformalization pilot: 3-shot vs 8-shot

Model `gpt-6.2-sol` (both runs) · run 25 Nov 2026 · runner `experiments/autoformalization/autoformalize.py` (branch `chaewon/finqa-autoformalization`) · Responses API, strict JSON schema; temperature, seed, reasoning effort and output limit left at API defaults (not a seeded / temperature-0 comparison).

## Side-by-side

| Measure | 3-shot | 8-shot |
|---|---|---|
| Validator: structurally valid | 11/16 | 10/16 |
| Validator: arithmetic mismatch | 4/16 | 5/16 |
| Abstained (empty IR) | 1/16 | 1/16 |
| Variables extracted | 32 | 36 |
| Grounding PASS (IRs) | 15/15 (100%) | 15/15 (100%) |
| Grounding errors / unsourced inputs | 0 / 0 | 0 / 0 |
| Equations give claimed value | 13/15 (2 after rounding) | 12/15 (2 after rounding) |
| Claim mismatches where the equations are right | 2/2 | 3/3 |
| **Formalization accuracy** (IR-computed value vs gold) | 11/15 (73%) | 12/15 (80%) |
| … excluding disputed gold answers | 9/10 (90%) | 10/10 (100%) |
| Wrong metric / denominator (answer error) | F_089 | none |
| Output scale used for ratios | fraction: 7, percent (×100): 8 | fraction: 11, percent (×100): 4 |

**Usage and cost (both runs together, OpenAI dashboard, project FinVerify-Benchmark-Eval):** 32 requests, 103,378 tokens, $0.37 (about $0.012 per IR; prompt-cache hit rate 0%). Cost = organization November spend after the runs ($0.51) minus before ($0.14). The output records hold response IDs but no token counts, so tokens are not split by run.

Formalization accuracy is scored on the 15 non-empty IRs per run. F_015 has a free-text gold answer; its IR value is compared with the amount stated there (£933.39). 'Excluding disputed gold' drops cases whose gold answer was flagged in review or disagrees with its own reference program (F_151, F_183, F_189, F_332, F_376).

## Where the runs differ

| Case | 3-shot | 8-shot | IR value 3-shot | IR value 8-shot |
|---|---|---|---|---|
| F_089 | ANSWER_ERROR | CLAIM_MISMATCH | 72.00 | 0.263415 |

F_089: 3-shot divides the 2019 estimate by 2017 *actual* expense (75), reproducing GPT-4o-mini's wrong denominator; 8-shot divides by the 2018–2022 schedule total (205) and gets the gold 26.3%. Its *claimed* value still copies the original answer (0.72), so the validator reports an arithmetic mismatch – the 8-shot IR is more correct, not less.

## Findings

1. **No grounding errors in either run.** Every one of the 32 (3-shot) and 36 (8-shot) input variables is found in the cited cell, sentence or question text, with consistent units.
2. **Validator arithmetic mismatches are mostly errors in the original answer, not in the IR.** The IR formalizes the recorded GPT-4o-mini answer; in F_015 (£916.35 vs £933.39), F_027 (251,375 vs 251,599.67) and F_089 (8-shot) the IR equations are right and the copied claim is wrong. F_127 and F_278 differ only by rounding/truncation and are not counted as errors here.
3. **8-shot fixes the one semantic error 3-shot keeps (F_089);** otherwise the runs agree case by case.
4. **Gold answers dispute 3 results in both runs** (F_151, F_183, F_376), matching the gold audit: the IR values are the financially correct ones for F_183 (2.78%) and F_376 (−88.64%); F_151 depends on whether 'total return' means ending value (IR: $138,290) or gain ($38,290).
5. **F_011 abstains in both runs because its inputs never reach the model:** the 16 manual cases keep their numbers in the benchmark's structured `evidence` field, which `prepare` does not pass on (the prompt shows an empty table and text). This should be fixed before scaling to all 500 cases.
6. **Scale conventions vary:** some IRs return ratios as fractions (0.2068) and others as percent (20.68), and 8-shot uses fractions more often. A fixed convention in the schema would simplify scoring.

Limitations: 16 cases, one model, one sample per configuration (API defaults, no seed), so the 3- vs 8-shot difference (one case) is not statistically meaningful. Grounding shows the numbers are in the evidence, not that they are the right numbers for the question.

## Files

Raw outputs (unchanged, as produced by the runner) in `results/pilot_16/raw/` – SHA-256 prefixes: `pilot_3shot.jsonl` eca202a3f18a1889, `pilot_8shot.jsonl` ebae2763faafb0d7, `pilot_inputs.jsonl` 8d7394a4ce2e768c, `python_packages.txt` a00acdc783f81453, `python_version.txt` a7575a0f59be8c73, `validation_3shot.json` 0b486aea5a0d9b5a, `validation_8shot.json` 540d8990b6c76331.
Per-IR results: `results/ir_grounding/3-shot_cases.csv`, `8-shot_cases.csv`; class table: `results/ir_grounding/comparison.md`.
## F_011 rerun after the evidence fix

Chaewon fixed `prepare` so the manual cases' structured evidence reaches the model (commit `dc8ce86 Add 16-case formalization error analysis`). F_011 was rerun alone (`--limit 1`) with the same model and settings, 26 Nov 2026; files in `results/pilot_16/rerun_F011/`. Inputs were grounded against the evidence the model saw (`pilot_inputs_v2.jsonl`).

| | 3-shot | 8-shot |
|---|---|---|
| Validator | ARITHMETIC_MISMATCH | ARITHMETIC_MISMATCH |
| Grounding | PASS | PASS |
| IR value (quarterly) | 9458.51 | 9458.51 |
| Claimed value | 9469.51 | 9469.51 |
| Class | CLAIM_MISMATCH | CLAIM_MISMATCH |
| IR value matches gold ($9,458.51) | yes | yes |

The abstention is resolved. Both IRs compute the gold values (annual $9,450.00, quarterly $9,458.51, monthly $9,460.46); the claimed $9,469.51 is GPT-4o-mini's quarterly error carried into the claim, the same pattern as F_015 and F_027. 8-shot also uses the 1-year duration in the exponent (frequency × duration); 3-shot hard-codes 4 and 12.

**With the rerun F_011 included**, formalization accuracy is 12/16 (3-shot) vs 13/16 (8-shot), and 10/11 vs 11/11 excluding disputed gold answers. No grounding errors in either run. F_015's input also changed with the fix (its evidence is now passed too); its pilot IR used the numbers in the question and was not rerun.

## Final 16-case set (all evidence handling on dc8ce86)

Reruns on `dc8ce86`: F_011, F_015 (the two manual cases whose inputs changed with the evidence fix); the other 14 records come from the pilot run on `7522e82`, whose prepared inputs are byte-identical on both commits. Grounding uses the inputs of the final commit.

| Measure | 3-shot | 8-shot |
|---|---|---|
| Abstained | 0/16 | 0/16 |
| Grounding errors / unsourced | 0 / 0 | 0 / 0 |
| Validator arithmetic mismatch | 5/16 | 6/16 |
| … where the IR equations are right | 3/3 | 4/4 |
| **Formalization accuracy** | 12/16 (75%) | 13/16 (81%) |
| … excluding disputed gold | 10/11 (91%) | 11/11 (100%) |
| Wrong metric / denominator | F_089 | none |

OpenAI usage for the pilot including both reruns: 36 requests, 115,336 tokens, $0.56 (project dashboard, November)
