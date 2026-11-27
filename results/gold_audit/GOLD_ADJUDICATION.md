# Adjudication of the 30 FinQA gold-audit inconsistencies

The 30 cases are flagged automatically when a FinQA gold answer disagrees with the value of its own reference program
(beyond rounding). Each case was then checked by hand against its supporting evidence (manual review, 27 Nov 2026).
Source: `src/evaluation/gold_adjudication.py`; table: `gold_adjudication_30.csv`.

| Verdict | Cases | Case IDs |
|---|---|---|
| Gold answer wrong (program right) | 11 | F_021, F_036, F_110, F_112, F_151, F_195, F_241, F_369, F_394, F_415, F_488 |
| Program wrong (gold answer right) | 13 | F_049, F_068, F_155, F_183, F_222, F_316, F_332, F_368, F_379, F_410, F_440, F_442, F_474 |
| Both wrong | 5 | F_147, F_156, F_270, F_418, F_430 |
| Ambiguous question | 1 | F_141 |

**Implication for evaluation.** The 13 PROGRAM_WRONG cases have a correct gold answer and can stay in
answer-based scoring. The 11 ANSWER_WRONG cases are scoreable against the program value. The 6 BOTH_WRONG or
AMBIGUOUS cases have no reliable reference and should be excluded. F_036 and F_369 differ from the program only by
sign; F_183 and F_415 only by truncation or rounding.

**Correction to the 27 Nov chat message.** On re-checking, F_147 and F_430 are BOTH_WRONG, not 'program wrong' and
'gold answer wrong': F_147's gold answer uses the wrong years too, and F_430 needs 1.7/0.25% = $680M.

## Per case

| Case | Verdict | Gold | Program | From evidence | Explanation |
|---|---|---|---|---|---|
| F_021 | ANSWER_WRONG | 63458 | 33458 | 33458 | Balance 28,524 without the -4,934 FX adjustment = 33,458 (program); gold 63458 has a wrong digit. |
| F_036 | ANSWER_WRONG | 30.4% | -0.304348 | -30.4% | Expense fell 2.3 -> 1.6, i.e. -30.4% (program); gold 30.4% drops the sign (magnitude correct). |
| F_110 | ANSWER_WRONG | 566808000 | 5.66808e+07 | 56680800 | $760,000K x 7.458% = $56,680,800 (program); gold 566808000 is 10x too large. |
| F_112 | ANSWER_WRONG | 5.38% | 0.0585035 | 5.85% | 3.87% x (3.87/2.56) = 5.85% (program); gold 5.38% transposes digits. |
| F_151 | ANSWER_WRONG | 3829 | 38290 | 38290 | Gain on $100,000 at 100 -> 138.29 is 38,290 (program); gold 3829 drops a digit. |
| F_195 | ANSWER_WRONG | 6.6 | 6.5 | 6.5 | 1.6 + 2.7 + 2.2 = 6.5 (program); gold 6.6 is an addition slip. |
| F_241 | ANSWER_WRONG | 27% | 0.465134 | 46.5% | 43,510/93,543 = 46.5% (program); gold 27% matches no evidence value. |
| F_369 | ANSWER_WRONG | 530 | -530 | -530 | Balance fell 1,701 -> 1,171 in 2014, a change of -530 (program); gold 530 drops the sign (magnitude correct). |
| F_394 | ANSWER_WRONG | 2.9% | 0.0272644 | 2.73% | 14.9/546.5 = 2.73% (program); gold 2.9% matches neither gross (2.73%) nor net (2.80%) receivables. |
| F_415 | ANSWER_WRONG | 4.8% | 0.0472973 | 4.73% | (155-148)/148 = 4.73% (program); gold 4.8% is mis-rounded. |
| F_488 | ANSWER_WRONG | 29% | 0.272727 | 27.27% | (11.2-8.8)/8.8 = 27.27% (program); gold 29% is wrong. |
| F_049 | PROGRAM_WRONG | 13.0% | 5.08 | 13.0% | 44.11/39.03 - 1 = 13.0% = gold; program stops at the difference 5.08. |
| F_068 | PROGRAM_WRONG | 2.25% | 721.3 | 2.25% | (703.1+18.2-705.4)/705.4 = 2.25% = gold; program stops at 721.3 and never compares with 2016. |
| F_155 | PROGRAM_WRONG | 17.3% | -125.06 | 17.3% | 177.26/151.16 - 1 = 17.3% = gold; program subtracts twice (-125.06). |
| F_183 | PROGRAM_WRONG | 2.7% | 2.02778 | 2.78% | (1.11-1.08)/1.08 = 2.78%; program adds instead of subtracting (202.8%); gold 2.7% is the correct value truncated. |
| F_222 | PROGRAM_WRONG | 34551 | 658.13 | 34551 | 707K shares x $48.87 = 34,551 = gold; program subtracts instead of multiplying (658.13). |
| F_316 | PROGRAM_WRONG | 79.3 | 61 | 79.3 | (104+61+73)/3 = 79.3 = gold; program adds, halves, adds 3 and halves (61). |
| F_332 | PROGRAM_WRONG | 10.7% | 9.3 | 10.71% | (9.3-8.4)/8.4 = 10.7% = gold; program adds the change back and returns 9.3. |
| F_368 | PROGRAM_WRONG | 37079.75 | 74161.5 | 37079.75 | Average of 23,596, 63,003, 50,131 and 11,589 = 37,079.75 = gold; program adds 4 and divides by 2. Question does not say 'average'. |
| F_379 | PROGRAM_WRONG | 50.0% | -99.4997 | 50.0% | (217,692-145,095)/145,095 = 50.0% = gold; program subtracts 100 from a fraction (-99.5). |
| F_410 | PROGRAM_WRONG | 0.15% | 1.48936 | 0.15% | $7M/$4.7B = 0.149% = gold; program ignores million vs billion (1.49). |
| F_440 | PROGRAM_WRONG | 28.16% | 1.2816 | 28.16% | 128.16/100 - 1 = 28.16% = gold; program returns the ratio 1.2816. |
| F_442 | PROGRAM_WRONG | 0.69% | 6.85714 | 0.69% | $48M/$7.0B = 0.69% = gold; program ignores million vs billion (6.86). |
| F_474 | PROGRAM_WRONG | 29.63% | 349 | 29.63% | (126+111+112)/1,178 = 29.63% = gold; program stops at the sum 349 (table is lease commitments, not notes). |
| F_147 | BOTH_WRONG | -32.4% | -1.32432 | -5.7% | 2005->2006 change is (-3.7 - -3.5)/3.5 = -5.7%; gold -32.4% is the 2006->2007 change and the program uses those years and divides the wrong step (-132%). |
| F_156 | BOTH_WRONG | 81.6% | 0.761 | 65.1% | The ratio improved (fell) 5.5 points to 70.6%; the same improvement gives 65.1%. Program adds (76.1%), gold adds twice (81.6%). |
| F_270 | BOTH_WRONG | 3.2 | 0.560667 | 1.78 | Feb-2014 notes vs 2011 term loan: 750.0/420.5 = 1.78 (or 329.5 difference); program inverts the ratio (0.56) and gold 3.2 has no support. |
| F_418 | BOTH_WRONG | 145.97 | 640.9 | 218.53 | (231.1+203.4+221.1)/3 = 218.53; program adds 203.4 twice and adds 3 (640.9); gold 145.97 has no support. |
| F_430 | BOTH_WRONG | 219.35 | 21.9355 | 680 | A 25 bp change moves expected return by $1.7M, so assets = 1.7/0.0025 = $680M; program computes 1.7*100/7.75 = 21.94 and gold 219.35 is that x10. |
| F_141 | AMBIGUOUS | 1.9 | -1.9 | - | The question (client payments vs revenue recorded) matches no row cleanly; program uses accrued warranty (17.0-18.9 = -1.9), gold gives 1.9, deferred subscription revenue would give 1.8. |
