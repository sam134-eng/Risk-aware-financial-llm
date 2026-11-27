"""Manual adjudication of the 30 FinQA cases whose gold answer disagrees with its own reference program.

Each case was checked against its supporting evidence (manual review, 27 Nov 2026). Verdicts:
  ANSWER_WRONG   - the reference program is right, the gold answer is not
  PROGRAM_WRONG  - the gold answer is right, the reference program is not
  BOTH_WRONG     - neither matches the value the evidence supports
  AMBIGUOUS      - the question does not determine a single answer from the evidence
`correct` is the value recomputed from the evidence (None when ambiguous).
"""

ADJUDICATION = {
    # ---- reviewed earlier (80-case review / Stage 1 v2 flags), re-checked 27 Nov ----
    "F_147": ("BOTH_WRONG", "-5.7%", "2005->2006 change is (-3.7 - -3.5)/3.5 = -5.7%; gold -32.4% is the 2006->2007 change and the program uses those years and divides the wrong step (-132%)."),
    "F_151": ("ANSWER_WRONG", "38290", "Gain on $100,000 at 100 -> 138.29 is 38,290 (program); gold 3829 drops a digit."),
    "F_183": ("PROGRAM_WRONG", "2.78%", "(1.11-1.08)/1.08 = 2.78%; program adds instead of subtracting (202.8%); gold 2.7% is the correct value truncated."),
    "F_332": ("PROGRAM_WRONG", "10.71%", "(9.3-8.4)/8.4 = 10.7% = gold; program adds the change back and returns 9.3."),
    "F_430": ("BOTH_WRONG", "680", "A 25 bp change moves expected return by $1.7M, so assets = 1.7/0.0025 = $680M; program computes 1.7*100/7.75 = 21.94 and gold 219.35 is that x10."),
    "F_488": ("ANSWER_WRONG", "27.27%", "(11.2-8.8)/8.8 = 27.27% (program); gold 29% is wrong."),
    # ---- adjudicated 27 Nov ----
    "F_021": ("ANSWER_WRONG", "33458", "Balance 28,524 without the -4,934 FX adjustment = 33,458 (program); gold 63458 has a wrong digit."),
    "F_036": ("ANSWER_WRONG", "-30.4%", "Expense fell 2.3 -> 1.6, i.e. -30.4% (program); gold 30.4% drops the sign (magnitude correct)."),
    "F_049": ("PROGRAM_WRONG", "13.0%", "44.11/39.03 - 1 = 13.0% = gold; program stops at the difference 5.08."),
    "F_068": ("PROGRAM_WRONG", "2.25%", "(703.1+18.2-705.4)/705.4 = 2.25% = gold; program stops at 721.3 and never compares with 2016."),
    "F_110": ("ANSWER_WRONG", "56680800", "$760,000K x 7.458% = $56,680,800 (program); gold 566808000 is 10x too large."),
    "F_112": ("ANSWER_WRONG", "5.85%", "3.87% x (3.87/2.56) = 5.85% (program); gold 5.38% transposes digits."),
    "F_141": ("AMBIGUOUS", None, "The question (client payments vs revenue recorded) matches no row cleanly; program uses accrued warranty (17.0-18.9 = -1.9), gold gives 1.9, deferred subscription revenue would give 1.8."),
    "F_155": ("PROGRAM_WRONG", "17.3%", "177.26/151.16 - 1 = 17.3% = gold; program subtracts twice (-125.06)."),
    "F_156": ("BOTH_WRONG", "65.1%", "The ratio improved (fell) 5.5 points to 70.6%; the same improvement gives 65.1%. Program adds (76.1%), gold adds twice (81.6%)."),
    "F_195": ("ANSWER_WRONG", "6.5", "1.6 + 2.7 + 2.2 = 6.5 (program); gold 6.6 is an addition slip."),
    "F_222": ("PROGRAM_WRONG", "34551", "707K shares x $48.87 = 34,551 = gold; program subtracts instead of multiplying (658.13)."),
    "F_241": ("ANSWER_WRONG", "46.5%", "43,510/93,543 = 46.5% (program); gold 27% matches no evidence value."),
    "F_270": ("BOTH_WRONG", "1.78", "Feb-2014 notes vs 2011 term loan: 750.0/420.5 = 1.78 (or 329.5 difference); program inverts the ratio (0.56) and gold 3.2 has no support."),
    "F_316": ("PROGRAM_WRONG", "79.3", "(104+61+73)/3 = 79.3 = gold; program adds, halves, adds 3 and halves (61)."),
    "F_368": ("PROGRAM_WRONG", "37079.75", "Average of 23,596, 63,003, 50,131 and 11,589 = 37,079.75 = gold; program adds 4 and divides by 2. Question does not say 'average'."),
    "F_369": ("ANSWER_WRONG", "-530", "Balance fell 1,701 -> 1,171 in 2014, a change of -530 (program); gold 530 drops the sign (magnitude correct)."),
    "F_379": ("PROGRAM_WRONG", "50.0%", "(217,692-145,095)/145,095 = 50.0% = gold; program subtracts 100 from a fraction (-99.5)."),
    "F_394": ("ANSWER_WRONG", "2.73%", "14.9/546.5 = 2.73% (program); gold 2.9% matches neither gross (2.73%) nor net (2.80%) receivables."),
    "F_410": ("PROGRAM_WRONG", "0.15%", "$7M/$4.7B = 0.149% = gold; program ignores million vs billion (1.49)."),
    "F_415": ("ANSWER_WRONG", "4.73%", "(155-148)/148 = 4.73% (program); gold 4.8% is mis-rounded."),
    "F_418": ("BOTH_WRONG", "218.53", "(231.1+203.4+221.1)/3 = 218.53; program adds 203.4 twice and adds 3 (640.9); gold 145.97 has no support."),
    "F_440": ("PROGRAM_WRONG", "28.16%", "128.16/100 - 1 = 28.16% = gold; program returns the ratio 1.2816."),
    "F_442": ("PROGRAM_WRONG", "0.69%", "$48M/$7.0B = 0.69% = gold; program ignores million vs billion (6.86)."),
    "F_474": ("PROGRAM_WRONG", "29.63%", "(126+111+112)/1,178 = 29.63% = gold; program stops at the sum 349 (table is lease commitments, not notes)."),
}
