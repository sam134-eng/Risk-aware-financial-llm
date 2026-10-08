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
2pm

### Research decisions
-I read the FinanceBench paper regarding financial QA benchmarks. FinanceBench focuses on observing model errors, but my paper provides an active verification solution.
- I will combine 20 hand-crafted gold cases(I read the book Priniciples of finance for taking idea and corporate finance internet documnets for understanding loan amortisation, 72 Rule etc) and I will adapt 30 cases from FinQA/ConvFinQA.

### Next step
- Validate the benchmark JSON using Python.
- Run a small pilot evaluation before running the full benchmark.
- Record model outputs and judge results separately.

### Files changed
- data/pilot_cases.json
- research_log.md