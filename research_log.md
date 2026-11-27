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
# Work Log — 2026-10-21 &22
Read the research paper-Human-AI Complementarity(Rishub Jain,)
They combine Human rater and Ai raters and according to this paper Human and AI can leverage complementarity by two steps i Hybridization 1)By ensamblong or aggregating human and AI prediction 2) Defer some task to the human based on Ai confidence. In this confidence based Routingt also what is interesting here they don't consider human as some static object. A human's performancemay improved by using Ai rater's assistance.
# PROJECT-
In this project we will try to see whether confidence based delegation improve finance llm performance.
Date: 24 October 2026

Status: Completed.

The benchmark merge script combines two datasets: 16 manually prepared financial reasoning cases and 134 FinQA-derived cases, producing 150 cases in total. The script checks for missing or duplicate case identifiers, missing questions, and missing reference answers before saving the combined dataset.

Output: data/processed/combined_benchmark_v1.json
The original input files are preserved. The merged benchmark is intended for subsequent baseline evaluation and experiments involving numerical correctness, evidence support, verification, and risk-aware deferral.
## Next
- Inspect schema and validator checks.
- Define leakage-free development, calibration, and test splits.
- Implement Answer Model and independent Judge.
- Implement deterministic arithmetic verification using Z3.
- Implement split conformal calibration.
- Implement risk-aware human deferral.
- Compare methods on held-out examples.
### Z3 Resource-25/10/26

I identified the official Microsoft Z3 Guide repository:

https://github.com/microsoft/z3guide

The repository contains tutorials and learning resources for Z3, an SMT (Satisfiability Modulo Theories) solver. The documentation includes an SMT-LIB tutorial programming examples, and material on using the Z3 API in Python.

 Key observations:

Z3 can determine whether a collection of logical and mathematical constraints is satisfiable.

Z3 supports mathematical representations, including real-valued arithmetic.

The Python API (Z3Py) allows constraints to be defined and checked programmatically.

The solver can return sat, unsat, or unknown, depending on the constraints and solver outcome.

Z3 is intended to be used as a component within a larger verification or analysis system.

Relevance to my project:

My project investigates whether formal verification can help identify arithmetic inconsistencies in financial question-answering systems.

The initial implementation uses Z3 to check simple-interest calculations against explicitly supplied inputs and a specified tolerance. This is a limited prototype: it checks arithmetic consistency under a particular formula and does not establish that the financial assumptions themselves are correct.

The planned next steps are to test the verifier systematically, investigate conformal uncertainty estimation for suitable numerical predictions, and integrate the verification results into a risk-aware routing mechanism.
### Date- 26 October 2026

## Combined Benchmark — 500 Cases
### Date- 29 October 2026-Experiment design
I made an Evidence-aware LLM baseline by run_baseline.py script. In our dataset there is table, gold answer,gold-reasoning and evidence context.
B0 — Evidence-aware LLM baseline

Question + financial evidence → model answer. On this first model I won't share gold reasoning or gold answer only evidence context so that I can check how the model is performing without verification.


##Status:## Benchmark generation completed successfully.

- Manually prepared cases: 16
- FinQA-derived cases: 484
- Total cases: 500
- Output: `data/processed/combined_benchmark_500.json`

The merge script combines both sources and checks for missing or duplicate case identifiers, missing questions, and missing reference answers before saving the output. The original input datasets remain separate.
### 01-11-2026
I was checking baseline_v2, there is some difference on case 21 of gold answer and gold-numeric. I did the calculation by myself and saw that the logic is fine and gold-numeric is fine. There must be some typo in the gold-answer data.
025	Model −9.03%, reference −5%
the question does not specify years, and the model's 2014–2015 calculation is plausible given the evidence.Model use 2014-15 while gold refrence use 2013 and 2014.
Today read the paper-"LOGIC-LM: Empowering Large Language Models with
Symbolic Solvers for Faithful Logical Reasoning"


## Next milestone: 
Implement a cached baseline evaluator, run a small pilot, and measure numerical answer correctness before integrating Z3 verification and risk-aware deferral.

## Caveat: 
Successful generation does not independently establish reference-answer correctness, annotation quality, or permission to redistribute the derived dataset
### 13-11-2026
Programming Z3
Nikolaj Bjørner, Leonardo de Moura, Lev Nachmanson, and Christoph Wintersteiger
Microsoft Research (Reading this z3 documentation)
Z3 is an efficient SMT solver with specialised algorithms for solving background theories like arithmetic, bit-vector, uninterpreted functions. 
Section 3 -Theories
Equality and Uninterpreted Functions- -
EUF is basic ingredient for first order predicate logic. Before there are theories, there are constants, functions, predicate symbols and relations.
Arithmatic-3.2(Important for Finance)
from z3 import *

revenue, cost, profit = Reals(
    'revenue cost profit'
)

s = Solver()

s.add(revenue == 1000)
s.add(cost == 300)
s.add(profit == revenue - cost)

s.add(profit != 700)

print(s.check()) 
Answer will be unsatisfiable as profit must be 700.
