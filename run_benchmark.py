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
from datetime import datetime
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
    parser.add_argument("--n-run", type=int, default=1)
    parser.add_argument("--out-dir", default="results")
    args = parser.parse_args()

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
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = args.model.replace("/", "-").replace(":", "-")
    fname = out_dir / f"{ts}_{safe_model}_{args.fmt}_seed{args.seed}.json"
    fname.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved to {fname}")


if __name__ == "__main__":
    main()
