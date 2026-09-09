# Small-model development pilot

Established 2026-09-08. This is an outcome-informed development follow-up,
not the original confirmation and not a new confirmatory registration.
Proceeding under the stated Qwen3-8B/14B assumption, with 8B first; the user
said to continue after this recommendation. Later 32B and other models remain
future work.

## Scope and comparability

`configs/small_model_development.json` pins both model and tokenizer revisions, 16,000 output
tokens, 32,768 total context, BF16/TP1, one concurrent sequence, thinking enabled,
temperature 0, top-p 1, top-k disabled, seed 42, vLLM 0.8.5.post1 and
Transformers 4.51.3. Server generation defaults explicitly come from vLLM,
not differing model generation configurations. Runtime/receipt and source
contracts are recorded in each model's private checkpoint. These are development
settings, not a claim that greedy thinking is optimal or truncation-free.

The 16,000-token allowance includes thinking and the final answer. The live
tokenizer must fit every rendered prompt plus that allowance into context before
any inference. Requests have one attempt and an 1,800-second timeout, with 180
seconds additional allocation headroom. These resource settings need a real
smoke; more allowed output can increase latency and memory demand.

Selection uses only fixture identity and character/sensitivity tags within the
first 432 original schedule slots, reported exposed by the operator. Three
fixtures from each character/sensitivity stratum give 12 fixtures and 48 queries
per model. The common selection and four cyclic horizon orders do not use
response quality. H2/H4 remain in this diagnostic pilot because they caused most
observed failures. Every model starts with the same one-query H2 smoke.

This sample is for feasibility and trace diagnosis; it cannot precisely estimate
rare truncation rates or power a size comparison. A zero-failure pilot does not
certify a 1% population failure rate. A larger development sample/power analysis
and a justified validity policy must precede a fresh evaluation freeze.

The original 8,000-token 32B observations cannot be pooled with this condition.
The stopped experiment and its interim peeks must be disclosed. Keep both
characters. A later size claim requires a direct paired difference of H effects,
with multiplicity and power for that contrast; comparing individual significance
decisions is insufficient. Two sizes within one family do not establish a general
scaling law. Held-out fixtures and their oracle audit remain outstanding.

## Cluster commands: first 8B smoke

Keep the old autoqueue stopped. Check that its active batch has ended using its
exact job ID before starting a new GPU job. Preserve that batch and checkpoint;
do not delete pending markers. No automatic successor submission is provided.

On the login node, after these changes are available on the remote branch:

```bash
cd ~/slay-the-spire-bench
git pull --ff-only origin main
eval "$(conda shell.bash hook)"
conda activate slaybench08
export CONDA_SH="$(conda info --base)/etc/profile.d/conda.sh"
export HF_HOME="${HF_HOME:-${HOME}/scratch/hf_cache}"
mkdir -p results
python scripts/small_model_pilot.py preflight --model qwen3-8b
```

Prefetch the pinned 8B weights without allocating a GPU (network/disk use only):

```bash
env -u HF_HUB_OFFLINE -u TRANSFORMERS_OFFLINE python - <<'PY'
import json
from pathlib import Path
from huggingface_hub import snapshot_download
p = json.loads(Path("configs/small_model_development.json").read_text())
m = p["models"]["qwen3-8b"]
snapshot_download(repo_id=m["repository"], revision=m["revision"])
print("Pinned 8B cache ready")
PY
sbatch --export=PILOT_MODEL=qwen3-8b,PILOT_MAX_NEW=1,CONDA_SH,CONDA_ENV,HF_HOME,HOME,PATH cluster/csis_small_model_pilot.sbatch
```

For the returned job ID, follow `results/slay_small_pilot_<job-id>.out` and
`results/small_model_development_server_<job-id>.log`. At the end inspect:

```bash
python scripts/small_model_pilot.py status --model qwen3-8b
```

The first row must parse, be schema-valid and legal, be nontruncated and have no
execution failure before a subsequent batch is permitted. Inspect elapsed time,
usage and server logs too. After a satisfactory smoke, use the same sbatch command
with `PILOT_MAX_NEW=16`, inspect its result, then continue until 48 rows. The runner
caps the last batch at the remaining queries and stops on insufficient deadline.
Do not start with 16 or use an autoqueue. For 14B, change both the prefetch model
key and `PILOT_MODEL` to `qwen3-14b`, starting again at `PILOT_MAX_NEW=1`.

## Evidence and interruption handling

Canonical outputs are
`results/small_model_development/real/qwen3-8b.json` and `qwen3-14b.json`.
Mock outputs use a distinct `mock` subdirectory. A model report binds config,
script/launcher source hashes, the original source-validated context, and the
entire common query schedule. Each saved entry contains scored row, complete
API response, request, tokenized input length, elapsed time and server receipt.
Status replays scores, response parsing and request/evidence bindings.

Before each model request, the full pending query is atomically persisted. The
entire response and scored row then replace that pending state in one atomic
write. A crash leaves either the saved row or an unresolved pending marker;
restart never reissues that query automatically. A transport or malformed-response
failure consumes a zero-quality slot and stops. If a pending marker remains,
preserve all evidence for manual reconciliation. Do not delete the report or
change output paths to bypass the stop. Receipt paths are confined to ignored
`results/small_model_development_server_*.json` files.

No Linux/GPU inference or model download was run locally during implementation.
Local validation uses the existing audited source artifacts, fake HTTP and full
mock continuation. Server startup, live tokenizer compatibility, throughput,
GPU fit and real generation quality are established only by the cluster smoke.

Official model sources:
[Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) and
[Qwen3-14B](https://huggingface.co/Qwen/Qwen3-14B).
