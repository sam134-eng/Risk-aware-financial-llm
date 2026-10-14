# Research Log — Risk-Aware Financial LLM

## 2026-10-07

### Time
9 am

### Work completed
- Created the initial financial benchmark dataset.
- Added 16 financial reasoning cases (F_001–F_016).
- Structured each case with evidence, question, gold answer, reasoning, risk type, severity, error types, and numerical tolerance.
- Added cases covering financial statement consistency, compound interest, ratios, EPS/P-E, profitability, DuPont analysis, present/future value, Rule of 72, perpetuity, annuity, loan amortisation, and effective annual rate.
- Reviewed and validated the JSON structure.
- Prepared the dataset for the next stage of benchmark evaluation.

### Time
10 pm

### Research decisions
-I read the FinanceBench paper regarding financial QA benchmarks. FinanceBench focuses on observing model errors, but my paper provides an active verification solution.
- I will combine 20 hand-crafted gold cases(I read the book Priniciples of finance for taking idea and corporate finance internet documnets for understanding loan amortisation, 72 Rule etc) and I will adapt 30 cases from FinQA/ConvFinQA.

### Next step
- Validate the benchmark JSON using Python.
- Run a small pilot evaluation before running the full benchmark.
- Record model outputs and judge results separately.
### 08-10-2026
### Evaluation methodology exploration
9 AM-Time

Reviewed established LLM benchmarking concepts, including:
- HELM-style benchmark evaluation
- ARC-style reasoning benchmarks
- Hugging Face evaluation/leaderboard ecosystem
- LLM evaluation and observability tools such as LangSmith and RAGAS

Research decision:
The project will develop a domain-specific financial benchmark rather than directly
using a general-purpose benchmark. Evaluation willtry to cover numerical correctness,
reasoning, evidence support, risk severity, calibration, and human deferral.
Time- 11.45 pm
Completed the reading of  FinanceBench archive paper.
### 09/10/26-Dataset
FINQA: A Dataset of Numerical Reasoning over Financial Data(Paper reading)
Authors propose a new large scale data set of question answers pairing by experts and they aim to automate the analysis of large corpus data.
### 10/10/26 -Z3 solver 
https://colab.research.google.com/github/philzook58/z3_tutorial/blob/master/Z3%20Tutorial.ipynb#scrollTo=od9YqkQmeJIx- I took some idea and learn in detail how to solve verification problems by using z3 solver. This tutorial is excellent.I can use it in project also like to make some function and check z3 whether LLM is follow the logic or not.
### 12/10/26-FINQA: A Dataset of Numerical Reasoning over Financial Data
In this paper -They use DSL and hire annotators for making FinQA questions. In this paper the use retrieving text and sliding window as their baseline system. Also Avg. # tokens in input text is 628.If without using the retriever-generator pipeline, but directly applying an end-to-end pre-trained Longformer model,b the perfirmance get failed.
They make DSL to understand how Ai is unswering. For example,
How much Revenue has increased?
subtract(130, 100), divide(#0, 100), multiply(#1, 100)- This is python Dsl language.
Financial Annotators make the numerical reasoning program of the questions and add the supporting fact from table and text. But the autor did not use independenct veriifcation in each step , Also they did not check in each step whether input came from actual row or not.
### New Idea
I pan to use a Z3-based verifier for explicitly represented financial constraints, together with split conformal prediction and a risk-aware deferral policy as it can help identify unreliable financial LLM outputs and route uncertain or high-risk cases for further review.
### 13/10/26
Revise the documentation of Python, patlib module,Relative paths etc..

# Work Log — 2026-10-14

## Completed
- Prepared a 134-example subset from FinQA.
- Source records: 1,147.
- Usable candidates: 1,133.
- Sampling seed: 2025.
- Project IDs: F_017 to F_150.
- JSON syntax check completed.
- Validator script executed; validation details still to be inspected.

## Next
- Inspect schema and validator checks.
- Define leakage-free development, calibration, and test splits.
- Implement Answer Model and independent Judge.
- Implement deterministic arithmetic verification using Z3.
- Implement split conformal calibration.
- Implement risk-aware human deferral.
- Compare methods on held-out examples.
"@ | Set-Content research_logs/2026-10-14.md


### Files changed
- data/pilot_cases.json
- research_log.md