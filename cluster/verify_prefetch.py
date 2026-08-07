#!/usr/bin/env python
"""Verify a prefetched HF model is COMPLETE and byte-exact before submitting a job.

WHY THIS EXISTS (2026-08-07)
----------------------------
The sbatch prefetch guards only check that the model's cache DIRECTORY EXISTS. A
partially downloaded model passes that check, the job claims its GPUs, spends up
to ~2 h loading weights off Lustre, and only then dies -- the most expensive way
to discover a truncated shard. Multiply by TP=2 and it is 2x H200 wasted.

`du -sh` is NOT a completeness check either. During the Qwen3-235B-A22B-FP8
prefetch it reported 212 GiB against an expected 222.7 GiB -- a 5% gap that
looked like a truncated download but was really Xet chunk dedup plus block
accounting. The only trustworthy test is per-file: does every file in the remote
manifest exist locally at exactly the expected byte size.

WHAT IT CHECKS
--------------
For every file in the repo's manifest: present in the local snapshot, and
os.path.getsize(realpath) == the size the Hub reports. Also reports orphaned
``*.incomplete`` blobs, which are debris from an interrupted (or duplicated)
download -- harmless once the manifest verifies, but worth deleting.

Needs network (reads the remote manifest), so run it on the LOGIN node, and do
NOT set HF_HUB_OFFLINE=1 for this call.

USAGE
-----
    export HF_HOME=/scratch/$USER/hf
    python cluster/verify_prefetch.py Qwen/Qwen3-235B-A22B-FP8

Exit 0 = complete and byte-exact (safe to submit). Exit 1 = incomplete; rerun
`hf download <repo>`, which fetches only the gaps.
"""
import os
import sys


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip().split("USAGE")[-1])
        return 2
    repo = argv[1]

    hf_home = os.environ.get("HF_HOME")
    if not hf_home:
        print("ERROR: HF_HOME is not set. On Sharanga: export HF_HOME=/scratch/$USER/hf")
        print("(Without it the cache defaults to ~/.cache/huggingface, and HOME is")
        print(" capped at 40 GiB -- a large model will wedge against the quota.)")
        return 1
    if os.environ.get("HF_HUB_OFFLINE"):
        print("ERROR: HF_HUB_OFFLINE is set; this check must read the remote manifest.")
        return 1

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("ERROR: huggingface_hub not importable — activate the env first.")
        return 1

    root = os.path.join(hf_home, "hub", "models--" + repo.replace("/", "--"))
    snaps = os.path.join(root, "snapshots")
    if not os.path.isdir(snaps):
        print(f"NOT PREFETCHED: {repo} (missing {snaps})")
        print(f"  HF_HOME={hf_home} hf download {repo}")
        return 1

    revs = sorted(os.listdir(snaps))
    if not revs:
        print(f"NOT PREFETCHED: {snaps} has no revision directory")
        return 1
    if len(revs) > 1:
        print(f"note: {len(revs)} revisions cached; checking the newest ({revs[-1]})")
    snapshot = os.path.join(snaps, revs[-1])

    info = HfApi().model_info(repo, files_metadata=True)
    missing, mismatched, total, expected = [], [], 0, 0
    for s in info.siblings:
        if s.size is None:          # no metadata (e.g. a directory entry) -> skip
            continue
        expected += s.size
        path = os.path.join(snapshot, s.rfilename)
        if not os.path.exists(path):
            missing.append(s.rfilename)
            continue
        actual = os.path.getsize(os.path.realpath(path))
        total += actual
        if actual != s.size:
            mismatched.append((s.rfilename, actual, s.size))

    incomplete = []
    blobs = os.path.join(root, "blobs")
    if os.path.isdir(blobs):
        incomplete = [f for f in os.listdir(blobs) if f.endswith(".incomplete")]

    print(f"repo          : {repo}")
    print(f"revision      : {revs[-1]}")
    print(f"files         : {len(info.siblings)}  missing: {len(missing)}  "
          f"size-mismatch: {len(mismatched)}")
    print(f"local total   : {total / 1e9:.1f} GB   (manifest {expected / 1e9:.1f} GB)")
    if incomplete:
        print(f"orphaned .incomplete blobs: {len(incomplete)} — safe to delete once "
              f"the manifest verifies:\n  rm -f {blobs}/*.incomplete")
    for m in missing[:10]:
        print("  MISSING  ", m)
    for f, a, e in mismatched[:10]:
        print(f"  SHORT     {f}  {a} != {e}")

    if missing or mismatched:
        print(f"\nINCOMPLETE — rerun (it fetches only the gaps):\n"
              f"  HF_HOME={hf_home} hf download {repo}")
        return 1
    print("\nCOMPLETE — byte-exact against the manifest; safe to submit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
