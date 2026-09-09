#!/usr/bin/env python
"""Separate, bounded development pilot; never writes original confirmation files."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import controlled_horizon_confirmatory as c
from scripts.controlled_horizon_model_pilot import _package_version
from scripts.controlled_horizon_pilot import _atomic_write_json

CONFIG = ROOT / 'configs/small_model_development.json'


def spec():
    return json.loads(CONFIG.read_text(encoding='utf-8'))


def protocol(model):
    s = spec()
    m = s['models'][model]
    return dict(inference=dict(model_repository=m['repository'],
        model_revision=m['revision'], served_model_name=model,
        serving_stack=dict(tensor_parallel_size=1, max_model_len=s['max_model_len'],
                           gpu_memory_utilization=s['gpu_memory_utilization'])))


def command(model, port):
    from scripts.controlled_horizon_confirmatory_server import server_command
    return server_command(protocol(model), port) + [
        '--tokenizer-revision', spec()['models'][model]['revision'],
        '--dtype', 'bfloat16', '--max-num-seqs', '1', '--generation-config', 'vllm']


def contract(model, mock):
    return dict(spec=spec(), model=model, mock=mock,
                original_protocol=c.FROZEN_DIGEST,
                code={name: hashlib.sha256((ROOT/name).read_text(encoding='utf-8').encode()).hexdigest()
                      for name in ('scripts/small_model_pilot.py',
                                   'cluster/csis_small_model_pilot.sbatch')})


def prepare():
    p, _ = c.load_protocol()
    ctx = c.load_context(p, ROOT/'results')
    fixtures, _, tags, _ = ctx
    original = c.query_schedule(p, fixtures, tags)
    return ctx, select_queries(original, spec())


def select_queries(original, s):
    prefix = original[:s['exposed_prefix_queries']]
    buckets = {}
    by_id = {}
    for q in prefix:
        by_id.setdefault(q['fixture_id'], []).append(q)
    for fid, qs in by_id.items():
        if {q['horizon'] for q in qs} == {1, 2, 4, 8}:
            q = qs[0]
            buckets.setdefault((q['character'], q['h1_h8_sensitive']), []).append(fid)
    chosen = []
    for char in ('ironclad', 'silent'):
        for tag in (True, False):
            ids = sorted(buckets.get((char, tag), []), key=lambda fid:
                         c.digest_json([s['study_id'], fid]))
            n = s['fixtures_per_character_stratum']
            if len(ids) < n:
                raise ValueError('insufficient exposed fixtures in a stratum')
            chosen.extend(ids[:n])
    queries = []
    # Four cyclic H orders balance positions across the twelve development fixtures.
    for i, fid in enumerate(chosen):
        order = s['horizons'][i % 4:] + s['horizons'][:i % 4]
        for position, h in enumerate(order):
            q = next(q for q in by_id[fid] if q['horizon'] == h)
            queries.append(dict(q, original_index=q['index'], index=len(queries),
                                query_order_within_fixture=position))
    return queries


def output_path(model, mock=False):
    return ROOT/'results'/'small_model_development'/('mock' if mock else 'real')/(model+'.json')


def clean(row):
    return (all(row['score'].get(k) is True for k in ('parse_ok', 'schema_ok', 'legal'))
            and not row['diagnostics']['truncated']
            and row['diagnostics']['execution_failure'] is None)


def check_report(report, model, mock, queries, ctx):
    if report['contract'] != contract(model, mock) or report['schedule'] != queries:
        raise ValueError('pilot contract or schedule drift; preserve evidence')
    if len(report['rows']) > len(queries):
        raise ValueError('too many saved rows')
    for q, entry in zip(queries, report['rows']):
        c.validate_row(entry['row'], q, ctx[3][q['fixture_id']], ctx[1][q['fixture_id']])
        if c.digest_json(entry['evidence']) != entry['evidence_sha256']:
            raise ValueError('response evidence checksum mismatch')
        ev, row = entry['evidence'], entry['row']
        if ev['request'] != request_payload(model, q, ctx):
            raise ValueError('saved request differs from development specification')
        if not mock:
            validate_receipt(ev['server_receipt'], model, ev['server_receipt']['port'])
        elif ev['server_receipt'] is not None:
            raise ValueError('mock evidence contains real provenance')
        if row['diagnostics']['execution_failure'] is None:
            choice = ev['response']['choices'][0]
            if (choice['message']['content'] != row['response_raw'] or
                    choice['finish_reason'] != row['diagnostics']['finish_reason']):
                raise ValueError('raw response differs from scored evidence')
            if not mock:
                check_context(ev['tokenized_prompt_tokens'], spec())
        elif ((ev['received_response'] is None) !=
              (row['diagnostics']['execution_failure'] == 'transport_failure')):
            raise ValueError('failure disposition differs from received response evidence')
    if report.get('pending') is not None:
        raise ValueError('unresolved pending query: preserve report; no automatic retry')
    if any(r['row']['diagnostics']['execution_failure'] is not None for r in report['rows']):
        raise ValueError('execution failure: inspect before any further inference')


def get_report(path, model, mock, queries, ctx):
    if path.exists():
        r = json.loads(path.read_text(encoding='utf-8'))
        check_report(r, model, mock, queries, ctx)
        return r
    return dict(contract=contract(model, mock), schedule=queries, rows=[], pending=None,
                confirmatory=False, created_at_unix=time.time())


def http_json(url, payload=None, timeout=30):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    # Never retry a model request, and never use proxy environment for loopback traffic.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as r:
        return json.load(r)


def messages(query, ctx):
    system, user = ctx[3][query['fixture_id']][query['horizon']]
    return [dict(role='system', content=system), dict(role='user', content=user)]


def check_context(count, s):
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValueError('invalid tokenizer count')
    if count + s['max_tokens'] > s['max_model_len']:
        raise ValueError('prompt plus output allowance exceeds context')


def request_payload(model, query, ctx):
    s = spec()
    return dict(model=model, messages=messages(query, ctx), max_tokens=s['max_tokens'],
                temperature=s['temperature'], top_p=s['top_p'], top_k=s['top_k'], seed=s['seed'],
                chat_template_kwargs={'enable_thinking': s['enable_thinking']})


def check_ready(report, max_new, total):
    if not 1 <= max_new <= spec()['max_new_queries_per_job']:
        raise ValueError('invalid bounded query count')
    if len(report['rows']) == total:
        raise ValueError('development pilot already complete')
    if not report['rows'] and max_new != 1:
        raise ValueError('first job must be a one-query smoke')
    if report['rows'] and not clean(report['rows'][0]['row']):
        raise ValueError('first smoke failed; inspect before further spending')


def validate_receipt(r, model, port):
    if r['contract'] != contract(model, False) or r['command'] != command(model, port):
        raise ValueError('server receipt mismatch')
    if (r['port'] != port or r['endpoint_sha256'] != c.digest_json(f'http://localhost:{port}')
            or r['runtime_versions'] != {k: spec()[k+'_version'] for k in ('vllm', 'transformers')}):
        raise ValueError('server runtime or endpoint mismatch')


def receipt_path_ok(path):
    return (path.resolve().parent == (ROOT/'results').resolve()
            and path.name.startswith('small_model_development_server_')
            and path.suffix == '.json')


def live_receipt(path, model, port):
    if not receipt_path_ok(path):
        raise ValueError('receipt must be a private development receipt in results')
    r = json.loads(path.read_text(encoding='utf-8'))
    validate_receipt(r, model, port)
    c.verify_live_server({'launch_receipt': r})
    return r


def run(args):
    s = spec()
    ctx, queries = prepare()
    path = output_path(args.model, args.mock)
    with c.exclusive_writer(path):
        report = get_report(path, args.model, args.mock, queries, ctx)
        check_ready(report, args.max_new, len(queries))
        receipt, counts = None, {}
        if not args.mock:
            if not args.authorize_model_inference or args.receipt is None or args.stop_at_unix is None:
                raise ValueError('real pilot requires authorization, receipt and allocation deadline')
            receipt = live_receipt(args.receipt, args.model, args.port)
            base = f'http://localhost:{args.port}'
            models = http_json(base+'/v1/models')['data']
            if not any(m['id'] == args.model and m.get('max_model_len') == s['max_model_len'] for m in models):
                raise ValueError('live model/context mismatch')
            for q in queries:
                v = http_json(base+'/tokenize', dict(model=args.model, messages=messages(q, ctx),
                    add_generation_prompt=True, chat_template_kwargs={'enable_thinking': True}))
                check_context(v['count'], s)
                counts[q['index']] = v['count']
        start_count = len(report['rows'])
        for _ in range(args.max_new):
            index = len(report['rows'])
            if index == len(queries):
                break
            if not args.mock and time.time()+s['timeout_seconds']+s['deadline_headroom_seconds'] >= args.stop_at_unix:
                break
            q = queries[index]
            if not args.mock:
                live_receipt(args.receipt, args.model, args.port)
            report['pending'] = dict(query=q, started_at_unix=time.time())
            _atomic_write_json(path, report)
            started = time.monotonic()
            failure, raw, finish = None, None, None
            response = None
            try:
                payload = request_payload(args.model, q, ctx)
                response = ({'choices': [{'message': {'content': '{"action":"end_turn"}'},
                                          'finish_reason': 'stop'}], 'usage': {}} if args.mock else
                            http_json(base+'/v1/chat/completions', payload, s['timeout_seconds']))
                raw = response['choices'][0]['message']['content']
                finish = response['choices'][0]['finish_reason']
                if not isinstance(raw, str):
                    raise ValueError('missing response text')
                replay = c.Replay(); replay.raw = raw; replay.last_finish_reason = finish
                parsed = replay.complete_json('', '')
                evidence = dict(response=response, request=payload, server_receipt=receipt,
                    elapsed_seconds=time.monotonic()-started, tokenized_prompt_tokens=counts.get(index))
            except Exception as exc:
                failure = 'transport_failure' if response is None else 'ambiguous_query'
                raw, finish, parsed = None, None, {'error': failure}
                evidence = dict(error_type=type(exc).__name__, elapsed_seconds=time.monotonic()-started,
                                server_receipt=receipt, received_response=response, request=payload)
            row = c.make_row(q, ctx[3][q['fixture_id']], ctx[1][q['fixture_id']],
                             parsed, raw, finish, failure)
            report['rows'].append(dict(row=row, evidence=evidence,
                                       evidence_sha256=c.digest_json(evidence)))
            report['pending'] = None
            _atomic_write_json(path, report)
            print(json.dumps(dict(completed=len(report['rows']), expected=len(queries),
                horizon=q['horizon'], clean=clean(row), elapsed_seconds=evidence['elapsed_seconds'],
                usage=evidence.get('response', {}).get('usage'))), flush=True)
            if failure or (index == 0 and not clean(row)):
                raise ValueError('development smoke/execution failure; inspect preserved response')
        if len(report['rows']) == start_count:
            raise ValueError('no progress: insufficient allocation time for a guarded query')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'server', 'run', 'status'))
    parser.add_argument('--model', choices=tuple(spec()['models']), required=True)
    parser.add_argument('--mock', action='store_true')
    parser.add_argument('--port', type=int, default=18808)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--max-new', type=int, default=1)
    parser.add_argument('--stop-at-unix', type=float)
    parser.add_argument('--authorize-model-inference', action='store_true')
    args = parser.parse_args()
    if args.action == 'server':
        if args.mock or not args.authorize_model_inference or sys.platform == 'win32':
            parser.error('server requires authorized Linux execution')
        if args.receipt is None or args.receipt.exists():
            parser.error('supply a new private receipt path')
        if not receipt_path_ok(args.receipt):
            parser.error('receipt must use results/small_model_development_server_<job>.json')
        for package in ('vllm', 'transformers'):
            if _package_version(package) != spec()[package+'_version']:
                raise ValueError('serving package differs from development specification')
        cmd = command(args.model, args.port)
        receipt = dict(contract=contract(args.model, False), command=cmd, pid=os.getpid(), port=args.port,
                       endpoint_sha256=c.digest_json(f'http://localhost:{args.port}'),
                       runtime_versions={k: _package_version(k) for k in ('vllm', 'transformers')})
        _atomic_write_json(args.receipt, receipt)
        os.execv(sys.executable, [sys.executable]+cmd)
    elif args.action == 'run':
        run(args)
    else:
        ctx, queries = prepare()
        r = get_report(output_path(args.model, args.mock), args.model, args.mock, queries, ctx)
        if args.action == 'preflight':
            check_ready(r, args.max_new, len(queries))
        print(json.dumps(dict(completed=len(r['rows']), expected=len(queries), confirmatory=False,
            selected_fixture_ids=sorted({q['fixture_id'] for q in queries}),
            clean=sum(clean(e['row']) for e in r['rows']),
            truncated=sum(e['row']['diagnostics']['truncated'] for e in r['rows']))))


if __name__ == '__main__':
    main()
