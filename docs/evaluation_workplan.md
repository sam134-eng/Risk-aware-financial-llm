# FinVerify-SMT – work plan (grounding and evaluation)

Date: 2026-11-25 · Author: grounding & evaluation workstream

## 1. Current project state

What this is based on: repository snapshot `eb65d01` (23 Nov 2026).
The repository has since become inaccessible from this workspace, so
**Update 25 Nov:** PR #1 (Chaewon, Stage 1 v2) has since been inspected and integrated – see
`docs/evaluation_report.md`. Everything below that touches the IR must be re-checked
against PR #1.

| Item | Status in `eb65d01` |
|---|---|
| Benchmark | `data/combined_benchmark_500.json`: 484 FinQA (test split) + 16 manual cases. SHA-256 `bb79a6db…d65d3`. |
| Evidence format (FinQA) | `evidence_context` = `pre_text` (list), `table` (list of rows), `post_text` (list). `gold_supporting_evidence` keys `table_N` = table row N (0-based, first row included); `text_N` = item N of `pre_text + post_text`. Checked: 811/811 keys resolve. |
| Evidence format (manual) | `evidence` = `{name: {value, unit}}`. No table or text. |
| Verifier | `src/z3_verifier.py`: 2-input operations only (add, subtract, multiply, divide, ratio, percentage_change, percentage_of), absolute tolerance. |
| Results | `results/verification_results.json`: GPT-4o-mini answers. PASS 126, FAIL 24, NOT_APPLICABLE 350. All 350 share one reason: no equation could be extracted from the model answer. |
| JSON IR schema | Not present in `eb65d01`. The work plan uses the IR example from the task brief (`variables[].source_grounding`, `equations[]`, `claimed_answer`). |
| Evidence extraction / grounding code | None. |
| Evaluation scripts, tests | None (no `tests/` folder). |
| LLM prompts / model integrations | None in the repo; the GPT-4o-mini answers are stored outputs only. |
| 80-case selection | Agreed list in `FinVerify_SMT_80_Case_Selection_Proposal.xlsx` (Chaewon); manual review added 23 Nov. |

## 2. Literature summary

| Paper | Main idea | Method | Verification | Evaluation | Ideas for FinVerify-SMT |
|---|---|---|---|---|---|
| Zhou et al., *Don't Trust: Verify* (ICLR 2024) | Keep only LLM solutions whose formal version is internally consistent, then majority-vote over those. | Sample many informal solutions; autoformalize the problem + candidate answer into an Isabelle statement and the solution into a formal sketch; gaps closed by automated provers. | Isabelle + Sledgehammer and standard tactics; a solution counts only if every step closes. Two filters: vacuous-hypothesis check (prove `False`) and LLM self-critique of statement faithfulness. | GSM8K, MultiArith, MATH subsets (number theory, algebra, prealgebra); solve rate vs. majority voting. | (a) Verification as a *filter* on sampled answers; (b) a vacuity / sanity check on the formalization itself; (c) their key failure is unfaithful formalization – the same gap our grounding checker targets for *inputs*. They check internal consistency only, not whether numbers come from a source. |
| Pan et al., *Logic-LM* (Findings EMNLP 2023) | Separate translation (LLM) from inference (deterministic solver). | LLM writes a task-specific symbolic program; solver executes; interpreter maps the result back. | Pyke, Prover9, python-constraint, Z3 depending on task. Self-refinement feeds solver error messages back to the LLM; fallback to chain-of-thought when not executable. | 5 logical-reasoning datasets; executable rate and execution accuracy reported separately. | (a) Report *validity rate* (valid IR) and *accuracy on valid IR* separately; (b) solver error messages fix syntax but not meaning – the authors observe accuracy plateaus after a few refinement rounds, which motivates a semantic (financial) check; (c) explicit fallback path. |

**Adopt directly:** separate formulation from execution; report valid-IR rate and conditional accuracy separately; deterministic checks before any LLM judgement.
**Needs adaptation:** both papers work on self-contained problems. FinQA answers depend on *external evidence* (tables, text, units, reporting periods), which neither paper grounds.
**Our gap / novelty:** cell- and span-level grounding of every input number, unit and scale checks, and a separate financial-semantic check (metric, numerator/denominator, period, direction), with the LLM judge measured against these deterministic signals rather than trusted.
**Limitations to state:** grounding shows a number exists in the source, not that it is the right number for the question; FinQA gold labels contain errors (see the 80-case review: e.g. F_151, F_376, F_430).

## 3. Prioritised task list

1. **Evidence grounding checker** (deterministic) – source resolver, number parser, unit normaliser, five checks, structured result. *Done 25 Nov: `src/grounding/`, 44 tests passing; see `src/grounding/README.md`.*
2. **Gold-IR builder + regression set** – derive IR from FinQA gold programs so the checker can be tested on real data, plus injected-error tests (wrong cell, ×1000, sign flip). *Done 25 Nov: `results/grounding/`.*
3. **Align with team IR** – reconcile field names with PR #1 once accessible.
4. **Deterministic answer evaluator** (Stage B) – numeric comparison with tolerance, %/fraction scale handling, yes/no answers.
5. **LLM-as-a-Judge baseline** (Stage A, no gold answer) – prompt, strict JSON schema, validator, retries.
6. **Judge validation** – agreement with deterministic evaluator and with human labels on the 80 cases; repeat-run consistency; perturbation probes.
7. **Multi-LLM comparison runner** – configurable model interface; raw + parsed outputs; latency and tokens.
8. **Error taxonomy + analysis**, tables and plots.
9. **Docs, progress report, contribution summary.**

## 4. Architecture

```
src/grounding/
  numbers.py              parse financial numbers ("$ -1.7 ( 1.7 )", "28.9%", "1,200")
  unit_normalizer.py      unit vocabulary, scale factors, scale detection in evidence
  source_resolver.py      resolve "table_row_R_col_C", "table_R", "text_N", "question", "evidence.<name>"
  evidence_grounding.py   check_grounding(ir, case) -> GroundingResult
  gold_ir.py              build IR from FinQA gold programs (testing / regression only)
src/evaluation/           answer_evaluator.py, llm_judge.py, error_taxonomy.py   (later)
src/experiments/          run_grounding_evaluation.py, run_model_comparison.py (later)
tests/                    pytest suites per module
```

Data flow: model output → IR (Chaewon's formaliser) → **grounding checker** → Z3 verifier (Sam) → answer evaluator; the LLM judge runs in parallel on the same output and is compared with the deterministic signals.

## 5. Dependencies and blockers

| Item | Status | Needed for |
|---|---|---|
| Repo access (PR #1, IR schema) | **Blocked** – repository no longer readable; GitHub access to be connected | Task 3 |
| Agreed IR field names and source-reference format | Open – propose `table_row_R_col_C` / `text_N` (see checker README) to Chaewon | Tasks 1, 3 |
| LLM API keys (OpenAI, others) and budget | Not available in this workspace | Tasks 5–7 |
| Human labels on the 80 cases | Not started (after case list was finalised) | Task 6 |
| Integrated Z3 pipeline (Sam) | Only the 2-input verifier exists | Experimental condition 4 |

## 6. Milestones

| By | Milestone |
|---|---|
| 27 Nov | Grounding checker + tests + gold-IR regression run; README; open PR |
| 29 Nov | IR aligned with PR #1; answer evaluator |
| 3 Dec | LLM judge baseline (Stage A/B) with schema validation |
| 6 Dec | Human labels on 80 cases; judge agreement study |
| 10 Dec | Multi-LLM runs (subject to API access); error taxonomy |
| 13 Dec | Tables, plots, contribution summary, progress report |
