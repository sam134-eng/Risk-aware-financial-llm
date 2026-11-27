# **Neuro-Symbolic Verification for Financial Question Answering**

**This repository contains the codebase, evaluation benchmarks, and verification scripts for our work on neuro-symbolic financial reasoning. Instead of relying solely on large language models to generate final numbers, our pipeline separates reasoning into structured autoformalization, deterministic evidence grounding, and formal mathematical verification via the Z3 SMT solver.**

## **Overview**

**Financial numerical reasoning requires strict consistency across document tables, units, signs, and multi-step arithmetic. Even when an LLM retrieves the right figures from an SEC filing, subtle arithmetic errors, scale mismatches (× 1000 vs. raw units), or incorrect denominators frequently slip through.**
