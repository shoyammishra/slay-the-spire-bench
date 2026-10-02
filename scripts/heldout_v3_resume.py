#!/usr/bin/env python
"""Resume a v3 run whose evidence holds infrastructure-caused lost-in-flight failures.

The frozen runner records a query that was in flight when a job died as an
`ambiguous_query` execution failure (never retried) and then refuses to send more queries
until a human has inspected the failure. It has no switch for "inspected: infrastructure
cause, continue", and editing it would change the code hash in the contract of rows already
written. This wrapper is that switch, and nothing else:

  * the runner's own `load_rows` still converts every orphaned `.pending` marker into a
    permanent `ambiguous_query` row exactly as frozen; nothing is re-asked;
  * only the row indices named in V3_ACCEPT_LOST (colon-separated) may be lost-in-flight
    failures, and each must carry `error_type == 'lost_in_flight'`; any other execution
    failure still stops the run;
  * the accepted failures stay in the evidence and are excluded pairs in `analyze`.

Usage (via cluster/sharanga_v3_resume.sbatch): V3_ACCEPT_LOST=5879:5881 python
scripts/heldout_v3_resume.py run --model qwen3-32b --port ... --receipt ... ...
"""
from __future__ import annotations

import os
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import heldout_v3_inference as inf

_ORIGINAL_LOAD_ROWS = inf.load_rows


def accepted_indices():
    # Colon-separated on the cluster: sbatch --export splits its value on commas.
    raw = os.environ.get('V3_ACCEPT_LOST', '')
    return frozenset(int(x) for x in re.split(r'[,:\s]+', raw) if x.strip())


def masked_rows(rows, accepted):
    """Copy of `rows` in which accepted lost-in-flight failures read as non-failures, so the
    runner's inline stop check passes. The entries stay in `rows`, so they are never re-asked."""
    out = {}
    for index, entry in rows.items():
        failure = entry['row']['diagnostics']['execution_failure']
        if failure is None:
            out[index] = entry
            continue
        if index not in accepted or entry.get('evidence', {}).get('error_type') != 'lost_in_flight':
            raise ValueError(f'row {index}: execution failure not accepted for resume ({failure})')
        row = dict(entry['row'], diagnostics=dict(entry['row']['diagnostics'], execution_failure=None))
        out[index] = dict(entry, row=row)
    unused = accepted - {i for i, e in rows.items() if e['row']['diagnostics']['execution_failure']}
    if unused:
        raise ValueError(f'accepted indices are not lost-in-flight failures: {sorted(unused)}')
    return out


def load_rows_for_resume(cfg, digest, model, mock, queries, ctx, strict=True):
    return masked_rows(_ORIGINAL_LOAD_ROWS(cfg, digest, model, mock, queries, ctx, strict), accepted_indices())


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] != 'run':
        sys.exit('only the run action is wrapped; use heldout_v3_inference.py for everything else')
    if not accepted_indices():
        sys.exit('set V3_ACCEPT_LOST to the inspected lost-in-flight row indices')
    inf.load_rows = load_rows_for_resume  # the runner resolves this global at call time
    inf.main()
