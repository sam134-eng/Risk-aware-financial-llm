
# Risk-Aware Financial LLM

Code and data for my paper on making LLM answers to financial questions more reliable and safe. The project explores three verification components after answer generation: a Z3 solver to verify the mathematics, conformal prediction to estimate uncertainty, and a rule that sends risky cases to a human reviewer.

The paper is still in progress, and so is the code. The evidence-aware baseline works, but most of the verification and safety components are still under development.

## The idea

LLMs make arithmetic mistakes on financial questions, assume things the source text does not say, and sometimes misinterpret the evidence. I want to investigate how much of this can be caught automatically, and whether combining verification layers can reduce errors and make financial reasoning more reliable and trustworthy.

```text
Question + evidence -> LLM answer -> Z3 check -> conformal uncertainty -> deferral policy -> evaluation / human review
```

## Research questions

1. Can Z3 catch arithmetic and constraint errors in model outputs?

2. Can conformal prediction provide useful uncertainty bounds on numerical financial answers?

3. Can a risk-sensitive policy reduce serious errors by sending the riskiest cases to a human reviewer?

4. How much does each component contribute to the reliability of the overall framework?

## Proposed Methodology

The proposed pipeline consists of six stages:

1. **Question and Evidence Input:** Receive a financial question together with relevant tables and supporting text.

2. **LLM Answer Generation:** Generate an answer and its key calculation.

3. **Formal Verification:** Use Z3 to verify supported numerical claims against mathematical constraints.

4. **Uncertainty Estimation:** Apply conformal prediction to suitable numerical prediction tasks.

5. **Risk-Aware Decision:** Decide whether to provide an answer, flag it, or defer it for human review.

6. **Evaluation and Logging:** Record outputs, verification results, uncertainty estimates, and evaluation metrics.

## Dataset

The current benchmark preparation pipeline combines:

- 16 manually constructed financial reasoning cases.
- 484 selected examples from the FinQA dataset.

This produces a combined benchmark of 500 cases.

The benchmark includes financial questions, reference answers, and supporting evidence where available.

Some annotations and reference labels still require validation before the full evaluation.

Dataset licensing and redistribution permissions will be reviewed before publishing derived data.

## Current Implementation Status

| Component | Status |
|---|---|
| Initial financial benchmark | Implemented |
| FinQA subset preparation | Implemented |
| Benchmark merging (500 cases) | Implemented |
| Evidence-aware LLM baseline | Implemented |
| Result caching and incremental saving | Implemented |
| Initial pilot experiments | Completed |
| Reference-label validation | In progress |
| Numerical evaluation | Planned |
| Z3 pipeline integration | In progress |
| Conformal prediction | Planned |
| Risk-aware deferral | Planned |
| Full benchmark evaluation | Planned |

## Experimental Design

The planned evaluation will compare five configurations:

- B0: Evidence-aware LLM baseline.
- B1: LLM with Z3 verification.
- B2: LLM with conformal uncertainty estimation.
- B3: LLM with risk-aware deferral.
- B4: Combined verification and risk-aware framework.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/sam134-eng/Risk-aware-financial-llm.git
cd Risk-aware-financial-llm
```

### 2. Create a virtual environment

For Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

For Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the API key

To run the baseline, you need an OpenAI API key.

Create an API key from the OpenAI platform:

https://platform.openai.com/api-keys

Create a `.env` file in the root directory of the project and add your key:

```env
OPENAI_API_KEY=your_api_key_here
```

Replace `your_api_key_here` with your own API key.

Keep your `.env` file private. Never upload your API key to GitHub.

### 5. Run the baseline

After preparing the benchmark data, run:

```bash
python scripts/run_baseline.py
```

The current implementation runs an initial pilot using 10 cases. The generated responses are saved locally in the results directory.

## Repo layout

```text
Risk-aware-financial-llm/
├── data/
│   ├── pilot_cases.json
│   └── processed/
│       └── combined_benchmark_500.json
├── scripts/
│   ├── prepare_finqa_subset.py
│   ├── merge_benchmark.py
│   ├── run_baseline.py
│   └── z3_verifier.py        # initial implementation
├── results/                  # cached model outputs
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Reproducibility

Each run saves the model name and prompt version alongside its outputs. For the conformal prediction experiments, calibration and test data will be kept in separate splits.

The project aims to maintain a clear separation between model-generated answers, reference answers, and verification results to support reproducible evaluation and error analysis.

