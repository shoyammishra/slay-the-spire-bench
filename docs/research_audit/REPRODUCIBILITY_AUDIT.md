# Reproducibility audit

## Current grade: C−

The source and deterministic seed discipline are strong; historical experimental
provenance and trace persistence are not paper-grade.

## What is reproducible now

- Direct test runners need no API.
- A mock end-to-end pipeline is documented.
- Base seeds are fixed and spaced to avoid overlapping per-sample ranges.
- Aggregate and per-seed result files are present locally for the seven-model matrix.
- Experiment and decision logs explain many recovery and reaggregation events.
- Greedy baselines and statistics have scripts.

## What is missing

The audit inventoried 181 model result JSONs:

- 0/181 record complete provenance or an instrument version;
- 46 contain turn samples;
- 46 contain combat samples;
- 147 contain synergy samples;
- 0 contain run samples;
- full raw successful completions are generally not persisted;
- early output traces cannot be reconstructed;
- dependencies are lower-bounded rather than locked;
- provider/server reasoning configuration is not controlled by the harness;
- ignored result/log directories are not a public artifact release.

Historical aggregates are therefore reproducible as files, not regenerable as exact
experiments from their own metadata.

## P0 changes implemented

New result schema 2.0 records provider, model, prompt format, character, base seeds,
per-dimension sample counts, temperature, max-token default, acts, routing flag, git
commit/dirty state, Python/platform/package versions, and explicit unknown reasoning
configuration. Endpoint URLs are intentionally excluded to prevent private cluster
leaks. Partial-dimension merges now preserve a per-dimension source marker and label
legacy provenance incomplete.

NumPy is now a declared direct dependency. This is not a lockfile; a lock or exact
environment export remains P1.

## Required release bundle

For every future paper-grade run, release:

1. immutable fixture IDs and serialized states;
2. exact prompt bytes or content hashes plus prompt templates;
3. parsed response, bounded raw response or secure full trace, finish reason, token
   counts, retries, and latency;
4. legal-action set, chosen action, oracle/reference values, and score;
5. complete run decision trace and scripted-versus-LLM controller tag;
6. result schema/instrument version and git commit;
7. container/environment lock and one-command analysis;
8. checksum manifest and data dictionary.

Private endpoints, account names, credentials, and cluster paths must never enter the
public bundle. Use placeholders and a pre-release secret scan.

## Exact reproduction commands

Current no-API checks:

```powershell
python tests/test_benchmark.py
python tests/test_combat.py
python tests/test_run.py
python tests/test_stats.py
python scripts/instrument_diagnostics.py --compact
python run_benchmark.py --provider mock --model mock --format structured --seed 42
```

The full historical model matrix cannot be exactly regenerated from JSON metadata
alone. That limitation must appear in the paper artifact statement.
