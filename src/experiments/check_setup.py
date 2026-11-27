"""Check that every model in a config is reachable before a long run (one tiny call each).

Usage
  python -m src.experiments.check_setup --config configs/models.free.json
  python -m src.experiments.check_setup --list groq          # print model IDs available on Groq
  python -m src.experiments.check_setup --list openrouter-free
  python -m src.experiments.check_setup --list ollama
"""
from __future__ import annotations

import argparse, json, os, sys
from pathlib import Path

from src.experiments.run_model_comparison import make_client

PROVIDERS = {"groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
             "openrouter-free": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
             "ollama": ("http://localhost:11434/v1", None),
             "google_ai_studio": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY")}


def list_models(which: str) -> int:
    import openai
    url, env = PROVIDERS[which]
    key = os.environ.get(env) if env else "local"
    if not key:
        print(f"[missing] set {env} first"); return 1
    try:
        ids = sorted(m.id for m in openai.OpenAI(api_key=key, base_url=url).models.list().data)
    except Exception as exc:
        print(f"[error] {type(exc).__name__}: {exc}"); return 1
    if which == "openrouter-free":
        ids = [i for i in ids if i.endswith(":free")]
    print(f"{len(ids)} models on {which}:")
    for i in ids:
        print("  ", i)
    return 0


def check(config: str) -> int:
    cfg = json.loads(Path(config).read_text())
    entries = [("model", m) for m in cfg["models"]] + ([("judge", cfg["judge"])] if "judge" in cfg else [])
    bad = 0
    for role, m in entries:
        label = f"{role:5s} {m['provider']:16s} {m['model']}"
        if "REPLACE" in m["model"]:
            print(f"[todo]  {label}  <- put the real model ID here"); bad += 1; continue
        try:
            c = make_client(m)
            out = c.complete("Reply with the single word OK.", "Say OK.", temperature=0.0,
                             max_tokens=int(m.get("check_max_tokens", 200)), seed=0)
            text = (out.get("text") or "").strip().replace("\n", " ")
            print(f"[ok]    {label}  -> {text[:40]!r}")
        except Exception as exc:
            msg = str(exc).replace("\n", " ")
            print(f"[error] {label}  -> {type(exc).__name__}: {msg[:160]}"); bad += 1
    print("\nAll models reachable." if not bad else f"\n{bad} problem(s) to fix before the full run.")
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/models.free.json")
    ap.add_argument("--list", choices=sorted(PROVIDERS))
    a = ap.parse_args()
    sys.exit(list_models(a.list) if a.list else check(a.config))
