# FinVerify-SMT – Grounding & Evaluation: final report

Date: 25 Nov 2026 · Branch: `grounding-evaluation` (based on `b1ebbb5`, PR #1 merged)
Benchmark SHA-256 `bb79a6db…d65d3` (unchanged). Nothing in `data/`, `src/z3_verifier.py` or
`experiments/stage1_v2/` was modified.

## 1. Progress report for Sam and Chaewon

| Deliverable (brief §8) | Status | Where |
|---|---|---|
| 1. Fine-grained evidence grounding checker | Done, 44 tests | `src/grounding/evidence_grounding.py`, `README.md` |
| 2. Unit and source normalisation utilities | Done | `src/grounding/{numbers,unit_normalizer,source_resolver}.py` |
| – Grounding of Stage 1 v2 equations (fills Chaewon's `evidence_grounding: NOT_EVALUATED`) | Done, real data | `src/grounding/locate.py`, `results/grounding/stage1_v2_grounding_*` |
| 3. LLM-as-a-Judge baseline | Code done and tested with a fake client; **not run** (no API key) | `src/evaluation/llm_judge.py`, `judge_agreement.py`, `src/experiments/run_judge_evaluation.py` |
| 4. Multi-LLM benchmark script | Code done and tested; **not run** (no API keys) | `src/experiments/run_model_comparison.py`, `configs/models.example.json` |
| 5. Evaluation results for selected cases | Done for GPT-4o-mini (stored answers) | `results/evaluation/` |
| 6. Error taxonomy and failure analysis | Done (deterministic signals; 2 categories need human review) | `results/analysis/` |
| 7. Benchmark comparison tables | Done (single model) | `results/tables/all_tables.md` |
| 8. Publication-quality plots | 7 figures (PNG 300 dpi + PDF) | `results/plots/` |
| 9. Reproducibility documentation | Done | §5 below |
| 10–12. Contribution summary, this report, limitations | Done | §3, §1, §4 |
| Human labels on the 80 cases | **Template ready, not filled** | `results/evaluation/human_labels_80.csv` |

Tests: 65 passing (`python -m pytest`).

### Key results (all measured, GPT-4o-mini stored answers)

1. **Answer accuracy.** All 500 cases: 72.3% lenient (349/483), 57.8% strict (279/483).
   80 selected NOT_APPLICABLE cases: 58.7% lenient (44/75), 44.0% strict (33/75).
   Excluding cases with questionable gold answers: 75.6% (337/446) and 67.7% (42/62).
2. **The original Z3 verdict is a weak proxy for correctness.** Answers the verifier marked PASS
   match gold in 76.2% of cases (93/122) – barely above NOT_APPLICABLE answers (72.4%, 244/337).
   FAIL answers are correct 50.0% of the time (12/24).
3. **Grounding of Stage 1 v2 equations (80-case set).** Of 68 inputs in the 34 equations Chaewon
   extracted, 48 (70.6%) appear directly in the evidence, 13 are one step derived from numbers
   in the same row/sentence, 3 reuse the model's own earlier result, 4 are not found.
   19 of 27 cases have both all-PASS arithmetic and fully traced inputs.
4. **Grounding + arithmetic still does not certify the answer.** Of those 19, 12 match gold.
   Of the 7 that do not, 5 have questionable gold (F_147, F_151, F_183, F_376, F_488),
   F_089 uses the wrong denominator (75 instead of the schedule total 205), and F_162 depends on
   the endpoint convention. Only a financial-semantic check (judge or human) can catch F_089.
5. **Benchmark noise.** 30 of 484 FinQA gold answers disagree with their own reference program;
   14 more differ only by rounding/truncation (e.g. F_017 stores 57.65% for 57.656%).
6. **Error profile of the 80 cases** (multi-label): 22 wrong values with no arithmetic/grounding
   explanation (metric, denominator or period suspected – needs review), 13 gold/reference
   issues, 7 arithmetic errors, 7 rounding-only, 3 inputs not found, 3 no final answer,
   2 refusals, 2 sign/direction, 1 scale error; 53 not formalisable by Stage 1 v2.
7. **Grounding checker validation.** On reference IR from 468 FinQA programs it passes 463
   (the other 5 are FinQA programs that write a filing fact as a constant) and detects 100% of
   injected ×1000, sign and wrong-reference errors and 99.6% of digit changes. A model that uses
   the wrong year *and cites it* passes grounding (253/254) – by design.

Accuracy by pattern (Table 4): percentage change 82.8%, ratio/share 80.2%, difference 61.0%,
product 52.0%, multi-step 46.0%, table aggregation 43.8%.

## 2. What each component sees (leakage control)

| Component | Sees gold? | Purpose |
|---|---|---|
| Grounding checker / locator | No | Are the numbers in the evidence? |
| Stage 1 v2 (Chaewon) | No | Is the written arithmetic right? |
| LLM judge, Stage A | **No** – prompt built only from question, evidence, model answer (tested: changing gold fields leaves the prompt identical) | Metric, numerator/denominator, period, units, reasoning |
| Answer evaluator, Stage B | Yes | Final answer vs gold (deterministic) |
| Gold audit | Gold only | Is the gold consistent with its own program? |

## 3. Research contribution summary (for the paper)

* **Fine-grained financial evidence grounding.** A deterministic checker that ties every number
  in an IR to a table cell or text span, handles FinQA number formats, signs, percentages and
  stated scales, and separates source-derived values, constants and intermediates. For free-text
  answers, a locator classifies each number as found, rescaled, derived, intermediate or unsupported.
* **Separate measurement of three kinds of correctness.** Evidence (grounding), arithmetic
  (Stage 1 v2 / Z3) and final-answer correctness are measured independently; the data show they
  diverge (verifier PASS → 76% correct; grounded + arithmetic PASS → 63% correct, mostly due to
  gold noise and one denominator error).
* **Benchmark reliability audit.** Automatic detection of gold answers that contradict their own
  programs (30/484), so model errors are not confused with label errors.
* **Leakage-controlled LLM-judge protocol** with strict JSON labels, validation, retries and
  agreement statistics (κ, AC1, bootstrap CI, FP/FN, repeat consistency) – ready to run.
* Not claimed: that grounding proves an answer correct; any multi-model result; any judge result.

## 4. Limitations, open issues, next steps

* **Only one model (GPT-4o-mini) is evaluated.** Decoding settings for the stored answers are
  not recorded; latency/tokens are unavailable. Multi-model runs need API keys
  (`configs/models.example.json`).
* **LLM judge not yet run**; no judge agreement or bias numbers exist yet.
* **Human labels missing.** `human_labels_80.csv` must be filled (blind to automatic outcome –
  hide that column while labelling) before judge-vs-human agreement can be reported.
* **Answer extraction is heuristic** (bold value → "answer:" line → last number; yes/no rules).
  Spot-check: 40/40 correct on a random sample, but not exhaustively verified.
  "Lenient" accepts ≤1% error and sign stated in words; strict numbers are also reported.
* **Locator derived matches** are limited to one evidence item; multi-item derivations (e.g.
  F_071, 92.49 − 100 across table and text) are reported as not found.
* Text-span references are coarse; scale is detectable in 289/484 FinQA cases only.
* Gold flags are flags, not corrections – labels are unchanged pending team adjudication.
* **Plan agreed with Sam (25 Nov):** free-model sweep first (`configs/models.free*.json`), then one
  proprietary OpenAI baseline + frontier judge in a capped project (`configs/models.openai.json`,
  cost estimate with `src/experiments/estimate_cost.py`), and grounding of Chaewon's 3-/8-shot IRs
  (`src/experiments/run_ir_grounding.py`).
* **Next:** (1) fill human labels; (2) obtain API keys and run `run_model_comparison` (direct vs
  JSON IR) for 3–4 models; (3) run the judge with 3 repeats and two judge models; (4) agree the IR
  source-reference format with Chaewon and wire the grounding checker into her formaliser
  output; (5) team decision on the 30 inconsistent gold answers.

## 6. 16-case autoformalization pilot (25 Nov 2026)

Run with OpenAI `gpt-6.2-sol` (3-shot and 8-shot, same 16 cases, Chaewon's runner); details in
`results/pilot_16/pilot_comparison.md` and `results/pilot_16/EXPERIMENT_RECORD.md`.
No grounding errors in either run; formalization accuracy (IR-computed value vs gold) 11/15 (3-shot)
vs 12/15 (8-shot), 9/10 vs 10/10 when disputed gold answers are excluded. 8-shot corrects the F_089
denominator. Most validator "arithmetic mismatches" are errors in the recorded GPT-4o-mini answer that the
IR equations expose. F_011 abstains because manual-case evidence is not passed to the model by `prepare`.

## 5. Reproduce

```bash
pip install -r requirements-evaluation.txt
python -m pytest                                        # 65 tests
python -m src.experiments.run_grounding_evaluation      # checker validation  -> results/grounding/grounding_eval_*
python -m src.experiments.run_stage1_grounding          # Stage 1 v2 grounding -> results/grounding/stage1_v2_*
python -m src.experiments.run_answer_evaluation         # GPT-4o-mini answers  -> results/evaluation/
python -m src.experiments.run_error_analysis            # taxonomy             -> results/analysis/
python -m src.reporting.generate_tables                 # tables               -> results/tables/
python -m src.reporting.generate_plots                  # figures              -> results/plots/
# free models only (Ollama locally + free API keys): see configs/models.free.json
python -m src.experiments.run_model_comparison --config configs/models.free.json
# paid APIs:
python -m src.experiments.run_model_comparison --config configs/models.json
python -m src.experiments.run_judge_evaluation --config configs/models.json --repeats 3
```
All steps are deterministic (no sampling); summaries record input-file SHA-256 hashes.
Or run `bash scripts/run_evaluation_pipeline.sh`.
