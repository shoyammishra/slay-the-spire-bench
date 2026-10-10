"""Post hoc (2026-10-10): rerun the chess-pilot queries that hit the 16k output cap with a
32k budget, then compare three scorings side by side. Not part of Amendment 9; the frozen
pilot code in scripts/chess_pilot.py is imported, never changed.

  python scripts/chess_rerun_truncated.py run --model gpt-oss-120b --port P [--max-tokens 32000]
  python scripts/chess_rerun_truncated.py analyze --model gpt-oss-120b

Scorings (all with the pilot's analysis code):
  preregistered  rows as run, truncated answers score 0
  dropped        every state with a truncated answer removed from both horizons
  rerun          truncated rows replaced by their 32k rerun (still truncated -> 0)
"""
import argparse
import concurrent.futures as cf
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chess_pilot as cp  # noqa: E402

OUT = cp.OUT


def load_rows(model):
    return [json.loads(l) for l in (OUT / f'rows_{model}.jsonl').read_text(encoding='utf-8').splitlines()]


def run(args):
    by_id = {s['state_id']: s for s in json.loads((OUT / 'release.json').read_text(encoding='utf-8'))['states']}
    todo = [r for r in load_rows(args.model) if r['truncated']]
    out = OUT / f'rerun{args.max_tokens // 1000}k_{args.model}.jsonl'
    done = {(json.loads(l)['state_id'], json.loads(l)['horizon'])
            for l in out.read_text(encoding='utf-8').splitlines()} if out.exists() else set()
    todo = [r for r in todo if (r['state_id'], r['horizon']) not in done]
    base = f'http://localhost:{args.port}'
    print(f'{len(todo)} truncated queries to rerun at max_tokens={args.max_tokens}', flush=True)

    def one(r):
        s = by_id[r['state_id']]
        try:
            q = cp.query(base, args.model, s['fen'], r['horizon'], args.max_tokens, args.timeout)
            return dict(state_id=r['state_id'], horizon=r['horizon'], move=cp.parse_move(q['content'], s['fen']),
                        truncated=q['finish_reason'] == 'length', failure=None, max_tokens=args.max_tokens, **q)
        except Exception as e:  # recorded, never retried
            return dict(state_id=r['state_id'], horizon=r['horizon'], move=None, truncated=False,
                        failure=repr(e)[:300], max_tokens=args.max_tokens)

    with open(out, 'a', encoding='utf-8') as fh, cf.ThreadPoolExecutor(args.concurrency) as ex:
        for row in ex.map(one, todo):
            fh.write(json.dumps(row) + '\n'); fh.flush()
            print(json.dumps(dict(state=row['state_id'], h=row['horizon'], move=row['move'],
                                  trunc=row['truncated'], fail=row['failure'] is not None,
                                  tokens=(row.get('usage') or {}).get('completion_tokens'))), flush=True)


def analyze(args):
    rows = load_rows(args.model)
    path = OUT / f'rerun{args.max_tokens // 1000}k_{args.model}.jsonl'
    rerun = {(r['state_id'], r['horizon']): r
             for r in (json.loads(l) for l in path.read_text(encoding='utf-8').splitlines())}
    bad = {r['state_id'] for r in rows if r['truncated']}
    variants = {
        'preregistered': rows,
        'dropped': [r for r in rows if r['state_id'] not in bad],
        'rerun': [rerun.get((r['state_id'], r['horizon']), r) if r['truncated'] else r for r in rows],
    }
    summary = {}
    for name, vr in variants.items():
        tag = f'{args.model}__{name}'
        (OUT / f'rows_{tag}.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in vr), encoding='utf-8')
        a = cp.analyze(argparse.Namespace(model=tag)) or json.loads((OUT / f'analysis_{tag}.json').read_text())
        summary[name] = {k: a[k] for k in ('n_sensitive', 'n_control', 'answers_changed', 'use_at_H',
                                           'h_blind_baseline', 'mcnemar_p', 'sensitive_gain', 'control_gain',
                                           'primary', 'churn')}
        summary[name]['still_truncated'] = sum(r['truncated'] for r in vr)
    summary['rerun_detail'] = dict(n=len(rerun), still_truncated=sum(r['truncated'] for r in rerun.values()),
                                   failures=sum(r['failure'] is not None for r in rerun.values()),
                                   unparsed=sum(r['move'] is None for r in rerun.values()))
    (OUT / f'three_way_{args.model}.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
    print(json.dumps(summary, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('run', 'analyze'))
    ap.add_argument('--model', required=True)
    ap.add_argument('--port', type=int, default=18900)
    ap.add_argument('--max-tokens', type=int, default=32000)
    ap.add_argument('--concurrency', type=int, default=8)
    ap.add_argument('--timeout', type=int, default=3600)
    args = ap.parse_args()
    {'run': run, 'analyze': analyze}[args.action](args)


if __name__ == '__main__':
    main()
