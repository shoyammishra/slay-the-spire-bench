"""
Entry point for running the benchmark harness.

Usage:
    python run_benchmark.py --model llama-3.1-8b-instant --provider groq --seed 42
    python run_benchmark.py --model mock --provider mock   # dry-run with no API calls
    python run_benchmark.py --character silent --acts 3 --temperature 0.7
    python run_benchmark.py --seeds 42 1042 2042 3042 4042   # multi-seed run
    (space base seeds >=1000 apart: per-sample seeds are contiguous from the
     base, so adjacent bases like 42,43 share 19/20 samples -> fake std)
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Force UTF-8 stdout/stderr so the report's box-drawing chars don't crash on
# Windows consoles (Python defaults to cp1252 there, which can't encode them).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()


def build_llm(provider: str, model: str, base_url: str = None):
    from slay_bench.benchmark import GroqLLM, OpenRouterLLM, LocalLLM, MockLLM
    if provider == "mock":
        responses = [
            '{"plays": [0], "reasoning": "mock"}',
            '{"action": "end_turn", "reasoning": "mock"}',
            '{"archetype": "Aggro", "best_card_index": 0, "worst_card_name": "Strike"}',
            '{"pick": 0, "reasoning": "mock"}',
            '{"choice": "rest", "reasoning": "mock"}',
            '{"path": 0, "reasoning": "mock"}',
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
    elif provider == "local":
        # Self-hosted OpenAI-compatible server (vLLM / TGI / Ollama). No key
        # needed by default; LOCAL_API_KEY is honoured if the server sets one.
        url = base_url or os.environ.get("LOCAL_BASE_URL") or "http://localhost:8000/v1"
        key = os.environ.get("LOCAL_API_KEY")
        # A reasoning model (qwen3) emits a long <think> per call; at ~21 tok/s an
        # 8000-token response needs ~380s, past the 300s default -> every long call
        # times out, then re-sends the same prompt and times out again. Bump via
        # $LOCAL_TIMEOUT (seconds) from the sbatch for self-hosted reasoning models.
        timeout = float(os.environ.get("LOCAL_TIMEOUT", "300"))
        return LocalLLM(model=model, base_url=url, api_key=key, timeout=timeout)
    else:
        sys.exit(f"Unknown provider: {provider}")


def _tagged_stem(stem: str, run_tag: str) -> str:
    """Append `_<run_tag>` to an output-file stem when a tag is set. Empty tag
    (the default) returns the stem unchanged — byte-identical to current
    filenames. Used to keep k-sampling / repeated-seed runs from overwriting
    each other (results/<model>_<fmt>_seed<N>.json collides otherwise)."""
    tag = (run_tag or "").strip()
    return f"{stem}_{tag}" if tag else stem


def _merge_existing(fname: Path, summary: dict) -> dict:
    """Merge skipped dimensions (null) from a previous run on disk."""
    if not fname.exists():
        return summary
    try:
        prev = json.loads(fname.read_text())
        for dim in ("turn", "combat", "synergy", "run"):
            if summary.get(dim) is None and prev.get(dim) is not None:
                summary[dim] = prev[dim]
                print(f"  (kept existing '{dim}' results from previous run)")
    except (json.JSONDecodeError, OSError):
        pass
    return summary


def main():
    parser = argparse.ArgumentParser(description="slay-bench: LLM planning benchmark")
    parser.add_argument("--model", default="llama-3.1-8b-instant")
    parser.add_argument("--provider", default="groq",
                        choices=["groq", "openrouter", "local", "mock"])
    parser.add_argument("--base-url", default=None,
                        help="Base URL for --provider local (OpenAI-compatible "
                             "endpoint, e.g. http://localhost:8000/v1 for vLLM, "
                             "http://localhost:11434/v1 for Ollama). Falls back to "
                             "$LOCAL_BASE_URL then http://localhost:8000/v1.")
    parser.add_argument("--format", dest="fmt", default="structured",
                        choices=["structured", "raw"])
    # Seed / multi-seed
    parser.add_argument("--seed", type=int, default=42,
                        help="Primary seed (used for single-seed runs and as filename stem).")
    parser.add_argument("--seeds", type=int, nargs="+", default=None,
                        metavar="SEED",
                        help="Run with multiple seeds and aggregate mean±std. "
                             "Overrides --seed. Space base seeds >=1000 apart "
                             "(per-sample seeds are contiguous from each base, "
                             "so close bases share samples and understate std). "
                             "E.g. --seeds 42 1042 2042 3042 4042")
    # Sample counts
    parser.add_argument("--n-turn", type=int, default=5)
    parser.add_argument("--n-combat", type=int, default=3)
    parser.add_argument("--n-synergy", type=int, default=3)
    parser.add_argument("--n-run", type=int, default=5)
    # Dimension filter
    parser.add_argument("--only", nargs="+", choices=["turn", "combat", "synergy", "run"],
                        metavar="DIM",
                        help="Run only these dimensions (e.g. --only synergy run). "
                             "Previous results for skipped dims are merged from disk.")
    # Character & acts
    parser.add_argument("--character", default="ironclad", choices=["ironclad", "silent"],
                        help="Which character to benchmark (default: ironclad).")
    parser.add_argument("--acts", type=int, default=1, choices=[1, 2, 3],
                        help="Number of acts to run in run-level evaluation (default: 1).")
    # Sampling temperature
    parser.add_argument("--temperature", type=float, default=0.0,
                        help="LLM sampling temperature (default: 0.0 = greedy). "
                             "Use >0 (e.g. 0.7) to get sampling variance / error bars.")
    # LLM routing
    parser.add_argument("--llm-routing", action="store_true", default=False,
                        help="Use LLM for path, rest-site, and boss-relic choices in "
                             "run-level eval (default: greedy heuristics).")
    parser.add_argument("--run-tag", default="",
                        help="Optional suffix appended to every output file stem "
                             "(e.g. --run-tag rep1). Default empty = current "
                             "filenames. Lets k-sampling / repeated-seed runs avoid "
                             "overwriting results/<model>_<fmt>_seed<N>.* .")
    parser.add_argument("--out-dir", default="results")
    args = parser.parse_args()

    if args.only:
        only = set(args.only)
        if "turn"    not in only: args.n_turn    = 0
        if "combat"  not in only: args.n_combat  = 0
        if "synergy" not in only: args.n_synergy = 0
        if "run"     not in only: args.n_run     = 0

    seeds = args.seeds if args.seeds else [args.seed]
    primary_seed = seeds[0]

    llm = build_llm(args.provider, args.model, base_url=args.base_url)

    from slay_bench.benchmark import BenchmarkHarness
    harness = BenchmarkHarness(
        llm,
        model_name=args.model,
        prompt_format=args.fmt,
        character=args.character,
        temperature=args.temperature,
        n_acts=args.acts,
        llm_routing=args.llm_routing,
    )

    print(f"Running benchmark: model={args.model} provider={args.provider} "
          f"format={args.fmt} character={args.character}")
    print(f"  seeds={seeds}  acts={args.acts}  temperature={args.temperature}  "
          f"llm_routing={args.llm_routing}")
    print(f"  n_turn={args.n_turn}  n_combat={args.n_combat}  "
          f"n_synergy={args.n_synergy}  n_run={args.n_run}")
    print()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    safe_model = args.model.replace("/", "-").replace(":", "-")
    # Character tag keeps Silent results from overwriting Ironclad files (and
    # from cross-merging dimensions between characters). Ironclad stays untagged
    # for backwards compatibility with existing result files.
    if args.character != "ironclad":
        safe_model = f"{safe_model}_{args.character}"

    if len(seeds) == 1:
        # Single-seed path (backwards-compatible)
        result = harness.run_all(
            seed=primary_seed,
            n_turn=args.n_turn,
            n_combat=args.n_combat,
            n_synergy=args.n_synergy,
            n_run=args.n_run,
        )
        summary = result.summary()
        print(json.dumps(summary, indent=2))

        stem = _tagged_stem(f"{safe_model}_{args.fmt}_seed{primary_seed}", args.run_tag)
        fname = out_dir / f"{stem}.json"
        summary = _merge_existing(fname, summary)
        fname.write_text(json.dumps(summary, indent=2))
        print(f"\nSaved JSON  -> {fname}")

        from slay_bench.visualize import save_all
        save_all(summary, stem, out_dir)

    else:
        # Multi-seed path: run once per seed, then aggregate mean±std
        per_seed_summaries = []
        for seed in seeds:
            print(f"\n{'='*50}")
            print(f"Seed {seed}")
            print('='*50)
            result = harness.run_all(
                seed=seed,
                n_turn=args.n_turn,
                n_combat=args.n_combat,
                n_synergy=args.n_synergy,
                n_run=args.n_run,
            )
            summary = result.summary()
            stem = _tagged_stem(f"{safe_model}_{args.fmt}_seed{seed}", args.run_tag)
            fname = out_dir / f"{stem}.json"
            summary = _merge_existing(fname, summary)
            fname.write_text(json.dumps(summary, indent=2))
            print(f"  Saved -> {fname}")
            from slay_bench.visualize import save_all
            save_all(summary, stem, out_dir)
            per_seed_summaries.append(summary)

        # Aggregate
        agg = _aggregate_summaries(per_seed_summaries, args.model, args.fmt, args.character, seeds)
        agg_stem = _tagged_stem(
            f"{safe_model}_{args.fmt}_seeds{'_'.join(str(s) for s in seeds)}", args.run_tag)
        agg_fname = out_dir / f"{agg_stem}.json"
        agg_fname.write_text(json.dumps(agg, indent=2))
        print(f"\nAggregated results ({len(seeds)} seeds) -> {agg_fname}")
        print(json.dumps(agg, indent=2))
        print("  (per-seed charts/text already saved alongside each seed JSON)")


def _aggregate_summaries(summaries: list, model: str, fmt: str,
                         character: str, seeds: list) -> dict:
    """Compute mean ± std across per-seed summaries for each metric."""
    import statistics

    def _mean_std(values):
        vals = [v for v in values if v is not None]
        if not vals:
            return None, None
        mean = statistics.mean(vals)
        std = statistics.stdev(vals) if len(vals) > 1 else 0.0
        return round(mean, 4), round(std, 4)

    def _agg_dim(key, metric_keys):
        dim_dicts = [s.get(key) for s in summaries if s.get(key) is not None]
        if not dim_dicts:
            return None
        out = {}
        for mk in metric_keys:
            vals = [d.get(mk) for d in dim_dicts]
            m, sd = _mean_std(vals)
            out[f"{mk}_mean"] = m
            out[f"{mk}_std"] = sd
        out["n_seeds"] = len(dim_dicts)
        return out

    # Metric keys MUST match BenchmarkResult.summary() exactly, or every
    # aggregated mean silently comes out None.
    turn = _agg_dim("turn", ["avg_damage_ratio", "legal_rate", "parse_ok_rate",
                             "parse_fail_n", "parse_fail_truncated"])
    combat = _agg_dim("combat", ["win_rate", "avg_hp_ratio", "avg_parse_errors",
                                 "avg_json_parse_errors", "avg_illegal_action_errors",
                                 "avg_truncation_errors"])
    synergy = _agg_dim("synergy", [
        "archetype_acc", "card_pick_acc", "removal_acc", "parse_ok_rate",
        "archetype_n_scored", "archetype_n_ambiguous",
        "card_pick_n_scored", "removal_n_scored",
    ])
    run = _agg_dim("run", ["survival_rate", "avg_hp_fraction",
                            "avg_draft_coherence", "avg_floors_reached", "avg_progress"])

    return {
        "model": model,
        "prompt_format": fmt,
        "character": character,
        "seeds": seeds,
        "n_seeds": len(seeds),
        "turn": turn,
        "combat": combat,
        "synergy": synergy,
        "run": run,
    }


if __name__ == "__main__":
    main()
