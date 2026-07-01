#!/usr/bin/env python3
"""Terminal entrypoint for the merged translational-agent framework.

A single Planner inspects the input, determines whether it is sequencing
data (WES/scRNA) or a GWAS summary-statistics file, presents a detailed
analysis plan, waits for your approval, then runs the appropriate pipeline
and generates a Markdown + HTML report.

Examples:
    python run_pipeline.py --input data/bio/demo_multimodal --run-id kang-demo
    python run_pipeline.py --input data/bio/demo/pbmc3k.h5ad --run-id pbmc-demo
    python run_pipeline.py --input smoketest/MASLD_chr1_slice.ma --trait MASLD --run-id masld-run1
    python run_pipeline.py --provider gemini --input /path/to/wes_fastqs --run-id wes1

--data and --gwas-file are accepted as deprecated aliases for --input.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Force UTF-8 on stdout/stderr regardless of the OS locale (e.g. cp950 on
# Traditional Chinese Windows) so LLM output with ≥ β → etc. never crashes.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from agentcore import state
from agentcore.agents.planner import run
from agentcore.providers import (
    ANTHROPIC_MODEL_DEFAULT,
    GEMINI_MODEL_DEFAULT,
    GROK_MODEL_DEFAULT,
    OPENAI_MODEL_DEFAULT,
)

_PROVIDER_DEFAULTS = {
    "anthropic": ANTHROPIC_MODEL_DEFAULT,
    "gemini":    GEMINI_MODEL_DEFAULT,
    "grok":      GROK_MODEL_DEFAULT,
    "openai":    OPENAI_MODEL_DEFAULT,
}

_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini":    "GEMINI_API_KEY",
    "grok":      "GROK_API_KEY",
    "openai":    "OPENAI_API_KEY",
}

DEFAULT_GOAL = (
    "Inspect the given input, determine whether it is sequencing data (WES/scRNA) "
    "or a GWAS summary-statistics file, and run the appropriate pipeline."
)

_DIVIDER = "─" * 64


def _prompt() -> str:
    """Read a line from the terminal, return empty string on Ctrl-C / EOF."""
    print(_DIVIDER)
    try:
        return input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", default=None,
                        help="Path to the input: a data file/directory (WES/scRNA) or a "
                             "GWAS summary-statistics file. Required (or use --data/--gwas-file).")
    parser.add_argument("--data", default=None,
                        help="Deprecated alias for --input (bio-flavored name, from agent1poc).")
    parser.add_argument("--gwas-file", default=None,
                        help="Deprecated alias for --input (gwas-flavored name, from AgentGWAS).")
    parser.add_argument("--trait", default=None,
                        help="Short trait name for GWAS runs (e.g. MASLD, T2D). Ignored for bio runs.")
    parser.add_argument("--run-id", default=None,
                        help="Run identifier. Results go to results/<run-id>/. "
                             "Defaults to --trait if given, else 'cli-run'.")
    parser.add_argument("--goal", default=None,
                        help="High-level instruction for the agent. Defaults to an auto-detect goal.")
    parser.add_argument("--provider", default="anthropic",
                        choices=list(_PROVIDER_DEFAULTS),
                        help="LLM provider (default: anthropic).")
    parser.add_argument("--api-key", default="",
                        help="API key. Falls back to the provider's env var if omitted.")
    parser.add_argument("--model", default=None,
                        help="Model name. Uses the provider default if omitted.")
    parser.add_argument("--base-url", default=None,
                        help="Custom base URL (for OpenAI-compatible endpoints).")
    parser.add_argument("--effort", default="high",
                        choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--max-iterations", type=int, default=40)
    parser.add_argument("--no-interactive", action="store_true",
                        help="Disable interactive prompts (plan approval will auto-proceed).")
    args = parser.parse_args()

    input_path = args.input or args.data or args.gwas_file
    if not input_path:
        parser.error("--input is required (or one of the deprecated aliases --data / --gwas-file).")

    domain_hint = None
    if args.gwas_file or args.trait:
        domain_hint = "gwas"
    elif args.data:
        domain_hint = "bio"

    # Resolve API key
    api_key = args.api_key or os.environ.get(_ENV_VARS.get(args.provider, ""), "")
    if not api_key:
        env_var = _ENV_VARS.get(args.provider, "<PROVIDER>_API_KEY")
        print(f"Error: no API key provided. Pass --api-key or set {env_var}.", file=sys.stderr)
        sys.exit(1)

    model = args.model or _PROVIDER_DEFAULTS[args.provider]
    run_id = args.run_id or (args.trait.replace(" ", "_") if args.trait else "cli-run")
    goal = args.goal or DEFAULT_GOAL

    print(_DIVIDER)
    print("  Merged translational-agent framework — terminal mode")
    print(f"  run-id  : {run_id}")
    print(f"  input   : {input_path}")
    if args.trait:
        print(f"  trait   : {args.trait}")
    print(f"  provider: {args.provider}  model: {model}")
    print(f"  effort  : {args.effort}")
    print(_DIVIDER)
    print()

    run(
        run_id=run_id,
        goal=goal,
        input_path=input_path,
        domain_hint=domain_hint,
        provider_name=args.provider,
        api_key=api_key,
        model=model,
        base_url=args.base_url,
        effort=args.effort,
        auto_approve=True,
        max_iterations=args.max_iterations,
        input_fn=None if args.no_interactive else _prompt,
    )

    checkpoint = state.load_state(run_id)
    domain = checkpoint.get("domain") or "unknown"
    rdir = f"results/{run_id}"

    print()
    print(_DIVIDER)
    print(f"Run complete (domain: {domain}). Results in {rdir}/")
    print(f"  report : {rdir}/report/report.html")
    print(f"  state  : {rdir}/state.json")
    print(f"  log    : {rdir}/agent_log.jsonl")
    if domain == "bio":
        print(f"  methods  : {rdir}/methods.md")
        print(f"  reproduce: {rdir}/reproduce.sh")
    elif domain == "gwas":
        print(f"  network: {rdir}/report/network.html")
    print(_DIVIDER)


if __name__ == "__main__":
    main()
