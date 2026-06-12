# Running slay-bench on the CSIS Cluster (BITS Pilani)

Self-hosting the open-source models (M3a phase) on the department's GPU cluster.
The cluster is a **shared Slurm system** — you never run the benchmark directly;
you submit a *job* that (1) serves a model with vLLM on a GPU node and (2) runs
the benchmark against it over `localhost`, using the repo's `--provider local`
adapter. Full cluster policy is in the department's CSIS cluster SOP (internal
doc, not committed to this public repo — keep your copy locally).

> **Login IP, support email, and room are intentionally omitted** — this is a
> public repo. Get the real login-node IP and support contact from the
> department's CSIS cluster SOP (the internal PDF the professor shared), and
> substitute `<login-node-ip>` below with it. Do not commit those values.

## Cluster facts (from the SOP)
- **Login node:** `ssh <username>@<login-node-ip>` (campus network or institute VPN required).
- **Compute nodes:** 2× **NVIDIA A100 80 GB** per node — one A100 comfortably serves a 32B model.
- **Storage:** 300 GB home quota; `~/scratch` (1 TB shared, **auto-deleted after 30 days**) — put model weights here via `HF_HOME`.
- **GPU partitions:** `gpu-short` (8 h), `gpu-long` (12 h), `gpu-1day` (24 h, up to 2 GPUs), `gpu-3day` (72 h).
- **Don't** run anything heavy (or `nvidia-smi`) on the login node — GPUs live only on compute nodes via Slurm.
- **Support:** see the SOP for the support email + lab room (include job ID + the `.out` tail on errors).

## One-time setup
From your Windows machine (MobaXterm or PowerShell), on the campus network:

```bash
ssh <username>@<login-node-ip>            # accept fingerprint, enter password (+2FA)
git clone https://github.com/shoyammishra/slay-the-spire-bench.git
cd slay-the-spire-bench
bash cluster/setup.sh                   # creates conda env 'slaybench' + installs vLLM
```

`.env` (the Groq/OpenRouter keys) is gitignored and is **not** needed here —
`--provider local` talks to vLLM with no API key.

**If the compute nodes have no internet** (test inside a job: `curl -I https://huggingface.co`),
pre-download weights on the login node first, then the jobs read them offline:

```bash
bash cluster/prefetch_model.sh Qwen/Qwen3-32B
# then add `export HF_HUB_OFFLINE=1` to cluster/lib.sh
```

## Run order (cheapest -> most expensive)
Submit each from the repo root; each prints its result paths at the end.

```bash
sbatch cluster/smoke.sbatch        # 1. tiny pass — PROVE pipeline + measure tok/s
sbatch cluster/turn_combat.sbatch  # 2. re-baseline turn+combat (n=20, 5 seeds, both formats)
sbatch cluster/synergy.sbatch      # 3. synergy, both characters + formats, 5 seeds
sbatch cluster/run_level.sbatch    # 4. run-level (LAST — biggest spend; scale up per smoke tok/s)
```

**Always run `smoke` first** and read its `time` output. A 32B model at ~50–100
tok/s makes one full run take 30–60+ min; size `--n-run` and pick the partition
from that measurement before launching `run_level`.

## Choosing / changing the model
All jobs default to **`Qwen/Qwen3-32B`** (one A100; revives the reasoning-model
slot that free tiers couldn't run). Override per submission without editing files:

```bash
# llama-3.1-8b baseline (provider-robustness check vs the old Groq numbers)
HF_REPO=meta-llama/Llama-3.1-8B-Instruct SERVED_NAME=llama-3.1-8b sbatch --export=ALL cluster/smoke.sbatch

# a 70B over both A100s (gpu-1day gives 2 GPUs)
HF_REPO=meta-llama/Llama-3.1-70B-Instruct SERVED_NAME=llama70b TP_SIZE=2 sbatch --export=ALL cluster/turn_combat.sbatch
```

`SERVED_NAME` is the clean alias used for both the API call and the result
filenames (`results/<SERVED_NAME>_<format>_seed<N>.*`). Defaults live at the top
of `cluster/lib.sh`.

## Monitor & retrieve
```bash
squeue -u $USER                         # is it pending / running?
tail -f slay_smoke_<jobid>.out          # live benchmark progress
tail -f vllm_<jobid>.log                # the model server's own log
sacct -u $USER                          # history after it finishes
seff <jobid>                            # efficiency report (right-size next request)
```

Pull results back to Windows (run in PowerShell on your PC, not the cluster):

```powershell
scp -r <username>@<login-node-ip>:slay-the-spire-bench/results ./cluster_results
```
(Or just use MobaXterm's left-hand SFTP pane to drag `results/` over.)

## Gotchas
- **Submit from the repo root** — the jobs `cd "$SLURM_SUBMIT_DIR"` and source `cluster/lib.sh` by relative path.
- **vLLM startup is slow** the first time (weights load); `wait_for_vllm` allows 20 min and tails the server log if it fails.
- **Conda path:** if `module avail` shows a different miniconda location than `/nfs_home/software/miniconda/`, update `CONDA_SH` in `setup.sh` and the `source ...conda.sh` line in each sbatch.
- **Time limits matter** (backfill scheduler): if a job is killed at the wall-clock limit, partial results are still saved on disk (the harness partial-saves on any error), and `--only`/merge logic fills the rest from previous JSON on a re-run.
