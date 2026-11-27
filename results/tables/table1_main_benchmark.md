### Table 1. Main benchmark (GPT-4o-mini, stored answers)

| Model | Cases | Answer acc. (lenient) | Answer acc. (strict) | Grounding: inputs supported | Equation (arithmetic) acc. | Metric acc. | Valid IR rate | Latency |
|---|---|---|---|---|---|---|---|---|
| gpt-4o-mini | 500 benchmark | 72.3% (349/483) | 57.8% (279/483) | not measured | not measured | not measured | n/a | not recorded |
| gpt-4o-mini | 80 selected | 58.7% (44/75) | 44.0% (33/75) | 70.6% (48/68) found in evidence; 94.1% (64/68) traced incl. derived/earlier steps | 76.5% (26/34) equations | not measured (needs judge/human) | n/a (free text); Stage 1 extraction 33.8% (27/80) cases | not recorded |

Denominators exclude cases whose gold is not a single value (manual multi-part cases, F_037). Lenient = correct at gold precision, within 1%, or sign stated in words. Grounding and arithmetic are on the equations Stage 1 v2 extracted (68 inputs, 34 equations, 27 cases). Other models were not run: no API access.
