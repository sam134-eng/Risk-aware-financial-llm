# Running the free-model comparison on Windows

Everything runs from PowerShell in the project folder:

```powershell
cd C:\path\to\repo
```

## 0. Once per PowerShell window: set your keys

```powershell
$env:GROQ_API_KEY="..."          # console.groq.com -> API Keys
$env:GEMINI_API_KEY="..."        # aistudio.google.com -> Get API key
$env:OPENROUTER_API_KEY="..."    # openrouter.ai/keys   (only for the full plan)
```
Never write keys into files or commit them.

## 1. Check the code
```powershell
python -m pytest -q                      # expect: 62 passed
```

## 2. Find the exact Groq model IDs
```powershell
python -m src.experiments.check_setup --list groq
```
Copy one **Qwen** ID and one **Llama** ID into `configs\models.free.quick.json`
(replace the two `REPLACE_WITH_...` texts). Do the same in `configs\models.free.json` if you use the full plan.

## 3. Check every model answers
```powershell
python -m src.experiments.check_setup --config configs\models.free.quick.json
```
Every line should start with `[ok]`. Fix any `[todo]`/`[error]` first (see Troubleshooting).

## 4. Test on 3 cases (writes to a separate test folder)
```powershell
python -m src.experiments.run_model_comparison --config configs\models.free.quick.json --cases F_017,F_026,F_151 --out results\test_run
```
At the end it prints one line per model and condition, e.g.
`openai/gpt-oss-120b | direct | {'CORRECT': 2, 'ROUNDING_ONLY': 1}`.
`API_ERROR` means the call failed - open `results\test_run\model_comparison_cases.csv`, column `error`.
`INVALID_IR` for `json_ir` means the model did not return valid JSON - fine to see sometimes; it is a result.

## 5. Full run (80 cases) - repeat once a day until nothing new is called
```powershell
python -m src.experiments.run_model_comparison --config configs\models.free.quick.json
```
Free limits stop each Groq model after 50 calls per run; the next run continues where it stopped.
To run one model only: add `--model gpt-oss` (any part of the model ID).

## 6. Human labels, then the judge
Fill `results\evaluation\human_labels_80.csv` first (hide the `automatic_outcome` column while labelling). Then:
```powershell
python -m src.experiments.run_judge_evaluation --config configs\models.free.quick.json --repeats 2
```

## 7. Send back
Zip `results\model_comparison`, `results\judge`, `results\evaluation` and share them.

## Troubleshooting
| Message | Fix |
|---|---|
| `environment variable ... is not set` | set the key again in this window (step 0) |
| `404` / `model not found` | wrong model ID - use step 2 to copy the exact ID |
| `429` / `rate limit` | free limit reached - wait (minute limit) or run again tomorrow (daily limit) |
| `Connection refused` (Ollama) | open the Ollama app or run `ollama serve` |
| `ollama` not recognized | `$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")` |

---

# Paid OpenAI run (after the free sweep)

Sam's plan: one proprietary baseline + a frontier judge, in a dedicated OpenAI project with an
**enforced hard spend limit** (Settings → Limits → turn on *Enforce a hard limit*; a plain budget only alerts).

1. Estimate the cost first (copy prices from the OpenAI pricing page on the day):
```powershell
python -m src.experiments.estimate_cost --models 1 --conditions 2 --judge-repeats 3 --model-price 2 10 --judge-price 10 50
```
2. Check model IDs in `configs\models.openai.json` against platform.openai.com/docs/models, then:
```powershell
$env:OPENAI_API_KEY="..."            # key from the dedicated project
python -m src.experiments.check_setup --config configs\models.openai.json
python -m src.experiments.run_model_comparison --config configs\models.openai.json --cases F_017,F_026,F_151 --out results\test_openai
python -m src.experiments.run_model_comparison --config configs\models.openai.json
python -m src.experiments.run_judge_evaluation --config configs\models.openai.json --repeats 3
```
The judge needs the filled `results\evaluation\human_labels_80.csv` for the human-agreement numbers.
A `429` with `project_spend_limit_exceeded` means the cap was reached - stop, don't retry.

# Grounding Chaewon's 3-shot / 8-shot IRs

```powershell
python -m src.experiments.run_ir_grounding --input <folder or file with 3-shot IRs> --label 3-shot
python -m src.experiments.run_ir_grounding --input <folder or file with 8-shot IRs> --label 8-shot
python -m src.experiments.run_ir_grounding --compare 3-shot 8-shot
```
If her field names differ, map them, e.g. `--source-field source --value-field val --id-field case_id`,
or `--ir-field ir` when each record wraps the IR. Output: `results\ir_grounding\` (per-IR CSV,
summary, and `comparison.md` splitting GROUNDING_ERROR / UNSOURCED_INPUT / LOGIC_ERROR / ANSWER_ERROR / CORRECT).
