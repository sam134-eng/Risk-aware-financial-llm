"""LLM-as-a-Judge baseline (Stage A: reasoning and evidence, WITHOUT the gold answer).

Design
------
* Stage A (this module): the judge sees the question, the evidence (table + text)
  and the model's answer. It never sees the gold answer or gold program.
  ``build_stage_a_prompt`` asserts this.
* Stage B: final answer vs gold is decided by the deterministic
  ``answer_evaluator`` – never by the judge.
* Output must be strict JSON with controlled labels; ``validate_judgement``
  rejects anything else. Invalid outputs are retried, then recorded as INVALID.
* The judge is a measured baseline, not ground truth (see judge_agreement.py).

Providers are pluggable (``JudgeClient``); API keys come from environment
variables only. Nothing here runs without a configured client.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

__all__ = ["LABELS", "DIMENSIONS", "PROMPT_VERSION", "build_stage_a_prompt", "validate_judgement",
           "JudgeClient", "judge_case", "JudgeRecord", "LeakageError", "OpenAIChatClient",
           "AnthropicClient", "FakeClient", "format_evidence"]

PROMPT_VERSION = "judge-stageA-v1"
LABELS = ("correct", "incorrect", "not_applicable", "cannot_determine")
DIMENSIONS = ("answer_correctness", "grounding_correctness", "equation_correctness", "metric_correctness",
              "numerator_denominator_correctness", "period_correctness", "unit_correctness")
ERROR_CODES = ("wrong_cell_or_span", "unsupported_number", "transcription_error", "unit_or_scale_error",
               "missing_evidence", "wrong_metric", "wrong_numerator", "wrong_denominator", "wrong_period",
               "wrong_direction", "percentage_error", "ratio_error", "average_error", "compounding_error",
               "arithmetic_error", "rounding_error", "answer_inconsistent_with_reasoning",
               "unjustified_refusal", "hallucination", "other")

SYSTEM = (
    "You are a meticulous financial analyst auditing an AI model's answer to a question about a company "
    "filing. Judge ONLY from the evidence given. You are not given a reference answer. Work out the "
    "correct calculation yourself from the evidence, then compare. Reply with one JSON object and nothing else."
)

TEMPLATE = """## Question
{question}

## Evidence from the filing
{evidence}

## Model answer to audit
{answer}

## Task
Evaluate the model answer on each dimension using exactly one label from
["correct", "incorrect", "not_applicable", "cannot_determine"]:
- answer_correctness: is the final answer right, given the evidence?
- grounding_correctness: are the numbers used actually in the evidence (right rows/years/spans)?
- equation_correctness: is the formula/arithmetic correct?
- metric_correctness: is it the financial metric the question asks for?
- numerator_denominator_correctness: are numerator and denominator the right quantities?
- period_correctness: are the right years/periods and comparison direction used?
- unit_correctness: are units and scale (thousands/millions/%) handled correctly?
Use "not_applicable" when a dimension does not apply (e.g. no division) and
"cannot_determine" when the evidence is insufficient to decide.

Return JSON with exactly these keys:
{{"question_id": "{qid}", "answer_correctness": "...", "grounding_correctness": "...",
"equation_correctness": "...", "metric_correctness": "...", "numerator_denominator_correctness": "...",
"period_correctness": "...", "unit_correctness": "...", "overall_reasoning_quality": <integer 1-5>,
"errors": [<zero or more of {codes}>], "explanation": "<at most 60 words>"}}"""


class LeakageError(ValueError):
    """Gold information would be exposed to the judge."""


def format_evidence(case: Dict[str, Any]) -> str:
    ec = case.get("evidence_context")
    if ec:
        parts = []
        if ec.get("pre_text"):
            parts.append("Text before table:\n" + "\n".join(f"[text_{i}] {t}" for i, t in enumerate(ec["pre_text"])))
        if ec.get("table"):
            parts.append("Table:\n" + "\n".join(f"[row {r}] " + " | ".join(str(c) for c in row)
                                                for r, row in enumerate(ec["table"])))
        if ec.get("post_text"):
            off = len(ec.get("pre_text") or [])
            parts.append("Text after table:\n" + "\n".join(f"[text_{off + i}] {t}" for i, t in enumerate(ec["post_text"])))
        return "\n\n".join(parts)
    ev = case.get("evidence") or {}
    return "\n".join(f"{k}: {v.get('value') if isinstance(v, dict) else v} {v.get('unit', '') if isinstance(v, dict) else ''}"
                     for k, v in ev.items())


_ALLOWED_KEYS = ("case_id", "question", "evidence_context", "evidence")


def build_stage_a_prompt(case: Dict[str, Any], model_answer: str) -> Dict[str, str]:
    """Return {"system", "user"} for Stage A.

    Leakage prevention is structural: the prompt is built from a copy of the case that
    holds ONLY question, evidence and id (no gold_* fields), so the gold answer can only
    appear if it is literally written in the evidence or the model answer.
    """
    safe = {k: case[k] for k in _ALLOWED_KEYS if k in case}
    if any(k.startswith("gold") for k in safe):
        raise LeakageError("gold field in judge input")
    user = TEMPLATE.format(question=safe.get("question", ""), evidence=format_evidence(safe),
                           answer=model_answer, qid=safe.get("case_id", ""), codes=", ".join(ERROR_CODES))
    return {"system": SYSTEM, "user": user}


def _extract_json(text: str) -> Optional[dict]:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def validate_judgement(obj: Any, question_id: Optional[str] = None) -> List[str]:
    """Return a list of schema violations (empty = valid)."""
    errs = []
    if not isinstance(obj, dict):
        return ["not a JSON object"]
    expected = {"question_id", *DIMENSIONS, "overall_reasoning_quality", "errors", "explanation"}
    missing = expected - set(obj)
    extra = set(obj) - expected
    if missing:
        errs.append(f"missing keys: {sorted(missing)}")
    if extra:
        errs.append(f"unexpected keys: {sorted(extra)}")
    for d in DIMENSIONS:
        if d in obj and obj[d] not in LABELS:
            errs.append(f"{d}: invalid label {obj[d]!r}")
    q = obj.get("overall_reasoning_quality")
    if "overall_reasoning_quality" in obj and (not isinstance(q, int) or isinstance(q, bool) or not 1 <= q <= 5):
        errs.append("overall_reasoning_quality must be an integer 1-5")
    if "errors" in obj:
        if not isinstance(obj["errors"], list) or any(e not in ERROR_CODES for e in obj["errors"]):
            errs.append("errors must be a list of allowed codes")
    if "explanation" in obj and not isinstance(obj["explanation"], str):
        errs.append("explanation must be a string")
    if question_id is not None and obj.get("question_id") != question_id:
        errs.append("question_id mismatch")
    return errs


class JudgeClient(Protocol):
    name: str

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int, seed: Optional[int]) -> Dict[str, Any]:
        """Return {"text": str, "input_tokens": int|None, "output_tokens": int|None}."""


@dataclass
class JudgeRecord:
    question_id: str
    judge_model: str
    prompt_version: str
    attempt_count: int
    valid: bool
    judgement: Optional[Dict[str, Any]]
    validation_errors: List[str] = field(default_factory=list)
    raw_outputs: List[str] = field(default_factory=list)
    latency_s: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    temperature: float = 0.0
    seed: Optional[int] = None


def judge_case(client: JudgeClient, case: Dict[str, Any], model_answer: str, *, temperature: float = 0.0,
               max_tokens: int = 600, seed: Optional[int] = 0, max_attempts: int = 3,
               backoff_s: float = 2.0) -> JudgeRecord:
    prompt = build_stage_a_prompt(case, model_answer)
    rec = JudgeRecord(case.get("case_id", ""), client.name, PROMPT_VERSION, 0, False, None,
                      temperature=temperature, seed=seed)
    t0 = time.time()
    user = prompt["user"]
    for attempt in range(1, max_attempts + 1):
        rec.attempt_count = attempt
        try:
            out = client.complete(prompt["system"], user, temperature=temperature, max_tokens=max_tokens, seed=seed)
        except Exception as exc:                       # API/network failure: retry with backoff
            rec.raw_outputs.append(f"<error: {type(exc).__name__}: {exc}>")
            rec.validation_errors = [f"api error: {exc}"]
            time.sleep(backoff_s * attempt)
            continue
        text = out.get("text", "")
        rec.raw_outputs.append(text)
        rec.input_tokens = out.get("input_tokens")
        rec.output_tokens = out.get("output_tokens")
        obj = _extract_json(text)
        errs = validate_judgement(obj, rec.question_id) if obj is not None else ["output is not valid JSON"]
        if not errs:
            rec.valid, rec.judgement, rec.validation_errors = True, obj, []
            break
        rec.validation_errors = errs
        user = prompt["user"] + "\n\nYour previous reply was invalid: " + "; ".join(errs) + \
            ". Reply again with ONLY the JSON object."
    rec.latency_s = round(time.time() - t0, 3)
    return rec


# ------------------------------------------------------------------ providers

class OpenAIChatClient:
    """OpenAI-compatible chat API. Needs ``pip install openai`` and OPENAI_API_KEY
    (or ``api_key_env``/``base_url`` for compatible providers)."""

    def __init__(self, model: str, api_key_env: Optional[str] = "OPENAI_API_KEY", base_url: Optional[str] = None,
                 extra: Optional[Dict[str, Any]] = None, token_param: str = "max_tokens",
                 send_temperature: bool = True):
        import openai  # noqa: import inside so the module works without the package
        key = os.environ.get(api_key_env) if api_key_env else "local"   # local servers (Ollama) need no key
        if not key:
            raise RuntimeError(f"environment variable {api_key_env} is not set")
        self.name = model
        self._extra = extra or {}      # e.g. {"reasoning_effort": "medium"} for gpt-oss / OpenAI reasoning models
        self._token_param = token_param          # newer OpenAI models need "max_completion_tokens"
        self._send_temperature = send_temperature  # some reasoning models reject temperature
        self._c = openai.OpenAI(api_key=key, base_url=base_url)

    def complete(self, system, user, *, temperature, max_tokens, seed):
        kw = {"model": self.name, self._token_param: max_tokens, "seed": seed,
              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if self._send_temperature and temperature is not None:
            kw["temperature"] = temperature
        if self._extra:
            kw["extra_body"] = self._extra
        r = self._c.chat.completions.create(**kw)
        u = getattr(r, "usage", None)
        return {"text": r.choices[0].message.content, "input_tokens": getattr(u, "prompt_tokens", None),
                "output_tokens": getattr(u, "completion_tokens", None)}


class AnthropicClient:
    """Anthropic Messages API. Needs ``pip install anthropic`` and FINVERIFY_ANTHROPIC_API_KEY."""

    def __init__(self, model: str, api_key_env: str = "FINVERIFY_ANTHROPIC_API_KEY"):
        import anthropic  # noqa
        key = os.environ.get(api_key_env)
        if not key:
            raise RuntimeError(f"environment variable {api_key_env} is not set")
        self.name = model
        self._c = anthropic.Anthropic(api_key=key)

    def complete(self, system, user, *, temperature, max_tokens, seed):
        r = self._c.messages.create(model=self.name, system=system, max_tokens=max_tokens, temperature=temperature,
                                    messages=[{"role": "user", "content": user}])
        return {"text": "".join(b.text for b in r.content if getattr(b, "type", "") == "text"),
                "input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens}


class FakeClient:
    """Deterministic stand-in for tests and dry runs. Returns scripted outputs in order."""

    def __init__(self, outputs: List[str], name: str = "fake-judge"):
        self.name = name
        self._outs = list(outputs)
        self.calls: List[Dict[str, str]] = []

    def complete(self, system, user, *, temperature, max_tokens, seed):
        self.calls.append({"system": system, "user": user})
        if not self._outs:
            raise RuntimeError("no scripted output left")
        o = self._outs.pop(0)
        if isinstance(o, Exception):
            raise o
        return {"text": o, "input_tokens": len(user) // 4, "output_tokens": len(o) // 4}
