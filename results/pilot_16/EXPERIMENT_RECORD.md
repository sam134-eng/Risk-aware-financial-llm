# Experiment record: 16-case autoformalization pilot (3-shot vs 8-shot)

| Item | Value |
|---|---|
| Run by | grounding & evaluation workstream |
| Date | 25 Nov 2026 (Africa/Nairobi, UTC+3) |
| Runner | `experiments/autoformalization/autoformalize.py`, branch `chaewon/finqa-autoformalization` (Chaewon's run guide) |
| Cases | the 16 IDs in `experiments/autoformalization/pilot_case_ids.json` (F_011, F_015, F_017, F_027, F_033, F_071, F_089, F_098, F_106, F_127, F_151, F_183, F_189, F_278, F_332, F_376) |
| Model | `gpt-6.2-sol` for both runs (response_model in every record). The proposed `gpt-5.4-mini-2026-03-17` was not available in the project; the guide allows another strict-JSON-schema model if the same ID is used for both runs. |
| API | OpenAI Responses API, strict JSON-schema output; project FinVerify-Benchmark-Eval (capped) |
| Generation settings | temperature, top_p, seed, reasoning effort and output-token limit **not set** (API defaults), so this is not a seeded or temperature-0 comparison |
| Only difference between runs | `--few-shot-count 3` vs `--few-shot-count 8` (and the output file) |
| Prompt inputs | question, financial evidence and the recorded GPT-4o-mini answer; gold answers and reference programs excluded (runner tests confirm) |
| Calls | 32 (16 per run), no API errors |
| Environment | Python 3.11.1, Windows; packages in `raw/python_packages.txt` (openai 3.59.0, python-dotenv 1.2.4) |
| Offline checks before the run | 17 unit tests OK, 8 synthetic fixtures OK, 16 inputs prepared |
| Tokens | **103,378** for both runs together (OpenAI dashboard, 24h, project FinVerify-Benchmark-Eval); not split by run because the records hold response IDs, not token counts; prompt-cache hit rate 0% |
| Requests | **32** (dashboard), matching 16 per run |
| Cost | **$0.37** = organization November spend after the runs ($0.51) − before ($0.14); about $0.012 per IR |

## Commands (run from the repository root, Windows PowerShell)

```
python -m unittest discover -s experiments/autoformalization/tests -v
python experiments/autoformalization/autoformalize.py test-fixtures
python experiments/autoformalization/autoformalize.py prepare --repository-zip . --output ../finqa_run_outputs/pilot_inputs.jsonl
python -m dotenv -f ../finverify.env run -- python experiments/autoformalization/autoformalize.py generate --repository-zip . --model gpt-6.2-sol --few-shot-count 3 --limit 16 --output ../finqa_run_outputs/pilot_3shot.jsonl
python -m dotenv -f ../finverify.env run -- python experiments/autoformalization/autoformalize.py generate --repository-zip . --model gpt-6.2-sol --few-shot-count 8 --limit 16 --output ../finqa_run_outputs/pilot_8shot.jsonl
python experiments/autoformalization/autoformalize.py validate --repository-zip . --input ../finqa_run_outputs/pilot_3shot.jsonl > ../finqa_run_outputs/validation_3shot.json
python experiments/autoformalization/autoformalize.py validate --repository-zip . --input ../finqa_run_outputs/pilot_8shot.jsonl > ../finqa_run_outputs/validation_8shot.json
python -m pip freeze > ../finqa_run_outputs/python_packages.txt
python --version > ../finqa_run_outputs/python_version.txt
```

## Analysis (this branch, no API calls)

```
python -m src.experiments.run_ir_grounding --input results/pilot_16/raw/pilot_3shot.jsonl --ir-field ir --label 3-shot
python -m src.experiments.run_ir_grounding --input results/pilot_16/raw/pilot_8shot.jsonl --ir-field ir --label 8-shot
python -m src.experiments.run_ir_grounding --compare 3-shot 8-shot
python -m src.experiments.report_pilot --tokens-total 103378 --requests 32 --cost-usd 0.37
```

Results: `results/pilot_16/pilot_comparison.md` (side-by-side), `results/ir_grounding/*` (per IR).
The API key was kept in `finverify.env` outside the repository and is not part of any file here.

## Rerun of F_011 after the evidence fix (26 Nov 2026)

Chaewon's commit `dc8ce86` (branch `chaewon/finqa-autoformalization`) passes the manual cases' structured
evidence to the model. After `git pull`: 21 unit tests OK, 8 fixtures OK, 16 inputs prepared
(`pilot_inputs_v2.jsonl`; only F_011 and F_015 differ from the first inputs). F_011 is first in the pilot
order, so it was rerun alone with `--limit 1`, same model and settings, into new files:

```
python -m dotenv -f ../finverify.env run -- python experiments/autoformalization/autoformalize.py generate --repository-zip . --model gpt-6.2-sol --few-shot-count 3 --limit 1 --output ../finqa_run_outputs/rerun_F011_3shot.jsonl
python -m dotenv -f ../finverify.env run -- python experiments/autoformalization/autoformalize.py generate --repository-zip . --model gpt-6.2-sol --few-shot-count 8 --limit 1 --output ../finqa_run_outputs/rerun_F011_8shot.jsonl
```

2 additional requests (cost not measured separately; at the pilot's average about $0.02). Files:
`results/pilot_16/rerun_F011/`. Analysis:
`python -m src.experiments.run_ir_grounding --input results/pilot_16/rerun_F011/rerun_F011_3shot.jsonl --ir-field ir --label F011-rerun-3shot --evidence-from results/pilot_16/rerun_F011/pilot_inputs_v2.jsonl` (and 8shot).

## F_015 rerun and final 16-case set on dc8ce86 (27 Nov 2026)

Requested by Sam and Chaewon so that all 16 pilot cases use the same runner commit.

| Field | Value |
|---|---|
| Runner | `experiments/autoformalization/autoformalize.py`, branch `chaewon/finqa-autoformalization`, commit `dc8ce86` |
| Model | `gpt-6.2-sol` (Responses API, strict JSON schema, API defaults: no temperature, seed or reasoning setting) |
| Python | 3.11.1; packages in `rerun_dc8ce86/python_packages.txt` (openai 3.59.0) |
| Command | `generate --few-shot-count {3,8} --limit 2` on a copy of the F_011 rerun file, so F_011 was resumed (identical record) and only F_015 called the API: 2 requests |
| Files | `results/pilot_16/rerun_dc8ce86/` (outputs + validation) |
| Validator | F_011 and F_015: ARITHMETIC_MISMATCH in both configurations |

F_015 grounding PASS in both runs (all inputs found in the structured evidence lines). The IR equations give
£933.39 = gold; the mismatch is the copied GPT-4o-mini claim £916.35 (its (1.005625)^36 is wrong).

Final set (`results/pilot_16/final/`, grounded with `run_ir_grounding --evidence-from pilot_inputs_v2.jsonl`;
summary `final_dc8ce86.json`): F_011 and F_015 from dc8ce86, the other 14 from the original pilot run, whose
prepared inputs are unchanged by the evidence fix. Formalization accuracy 12/16 (3-shot) vs 13/16 (8-shot);
10/11 vs 11/11 excluding disputed gold; 0 grounding errors. Rebuild:
`python -m src.experiments.assemble_pilot_final --rerun-3 results/pilot_16/rerun_dc8ce86/rerun_dc8ce86_3shot.jsonl --rerun-8 results/pilot_16/rerun_dc8ce86/rerun_dc8ce86_8shot.jsonl --commit dc8ce86`

Dashboard after both reruns (27 Nov): 36 requests (32 pilot + 2 F_011 + 2 F_015), 115,336 tokens, prompt-cache hit rate 0%, November spend $0.56.
