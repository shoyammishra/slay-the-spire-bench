"""
Entry point for running the benchmark harness.

Usage:
    python run_benchmark.py --model llama-3.1-8b-instant --provider groq --seed 42
    python run_benchmark.py --model llama-4-scout-17b-16e-instruct --provider groq --format raw
    python run_benchmark.py --model mock --provider mock   # dry-run with no API calls
"""
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


def build_llm(provider: str, model: str):
    from slay_bench.benchmark import GroqLLM, OpenRouterLLM, MockLLM
    if provider == "mock":
        responses = [
            '{"plays": [0], "reasoning": "mock"}',
            '{"action": "end_turn", "reasoning": "mock"}',
            '{"archetype": "Aggro", "best_card_index": 0, "worst_card_name": "Defend"}',
            '{"pick": 0, "reasoning": "mock"}',
        ] * 2000
        return MockLLM(responses)
    elif provider == "groq":
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            sys.exit("GROQ_API_KEY not set. Add it to .env or export it.")
        return GroqLLM(model=model, api_key=key)
    elif provider == "openrouter":
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            sys.exit("OPENROUTER_API_KEY not set.")
        return OpenRouterLLM(model=model, api_key=key)
    else:
        sys.exit(f"Unknown provider: {provider}")


def main():
    parser = argparse.ArgumentParser(description="slay-bench: LLM planning benchmark")
    parser.add_argument("--model", default="llama-3.1-8b-instant")
    parser.add_argument("--provider", default="groq", choices=["groq", "openrouter", "mock"])
    parser.add_argument("--format", dest="fmt", default="structured",
                        choices=["structured", "raw"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-turn", type=int, default=5)
    parser.add_argument("--n-combat", type=int, default=3)
    parser.add_argument("--n-synergy", type=int, default=3)
    parser.add_argument("--n-run", type=int, default=5)
    parser.add_argument("--only", nargs="+", choices=["turn", "combat", "synergy", "run"],
                        metavar="DIM",
                        help="Run only these dimensions (e.g. --only synergy run). "
                             "Previous results for skipped dims are merged from disk.")
    parser.add_argument("--out-dir", default="results")
    args = parser.parse_args()

    if args.only:
        only = set(args.only)
        if "turn"    not in only: args.n_turn    = 0
        if "combat"  not in only: args.n_combat  = 0
        if "synergy" not in only: args.n_synergy = 0
        if "run"     not in only: args.n_run     = 0

    llm = build_llm(args.provider, args.model)

    from slay_bench.benchmark import BenchmarkHarness
    harness = BenchmarkHarness(llm, model_name=args.model, prompt_format=args.fmt)

    print(f"Running benchmark: model={args.model} provider={args.provider} "
          f"format={args.fmt} seed={args.seed}")
    print(f"  n_turn={args.n_turn}  n_combat={args.n_combat}  "
          f"n_synergy={args.n_synergy}  n_run={args.n_run}")
    print()

    result = harness.run_all(
        seed=args.seed,
        n_turn=args.n_turn,
        n_combat=args.n_combat,
        n_synergy=args.n_synergy,
        n_run=args.n_run,
    )

    summary = result.summary()
    print(json.dumps(summary, indent=2))

    # Save to results/
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    safe_model = args.model.replace("/", "-").replace(":", "-")
    stem = f"{safe_model}_{args.fmt}_seed{args.seed}"
    fname = out_dir / f"{stem}.json"

    # Merge with any existing result: a dimension skipped this run (n=0 → null)
    # must NOT clobber valid data from a previous run with the same stem.
    if fname.exists():
        try:
            prev = json.loads(fname.read_text())
            for dim in ("turn", "combat", "synergy", "run"):
                if summary.get(dim) is None and prev.get(dim) is not None:
                    summary[dim] = prev[dim]
                    print(f"  (kept existing '{dim}' results from previous run)")
        except (json.JSONDecodeError, OSError):
            pass

    fname.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved JSON  -> {fname}")

    # Save text report + charts
    from slay_bench.visualize import save_all
    save_all(summary, stem, out_dir)


if __name__ == "__main__":
    main()
