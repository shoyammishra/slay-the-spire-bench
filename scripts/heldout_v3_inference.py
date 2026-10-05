#!/usr/bin/env python
"""Confirmatory controlled-H v3 inference on the held-out release (Qwen3-8B/14B).

Stages: preflight | server | run | status | analyze. Reuses the audited v2 prompt,
scoring and replay code; only the fixture source, schedule (H1/H8, counterbalanced),
concurrency and the sensitive-minus-control analysis are new. Config:
configs/controlled_h_v3_inference.json (frozen digest below). Deliberately NOT named
controlled_horizon*.py: that glob is hashed by the frozen v2 code receipt.

Integrity rules: one response per query, never retried. Each row is an immutable file;
a query that was in flight when a job died is recorded as `ambiguous_query` on resume.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import controlled_horizon_confirmatory as c
from scripts.controlled_horizon_model_pilot import _package_version, score_precomputed_oracle
from scripts.controlled_horizon_pilot import _atomic_write_json
from slay_bench.controlled_horizon import ControlledFixture, load_fixture, legal_actions

CONFIG = ROOT / 'configs/controlled_h_v3_inference.json'
FROZEN_DIGEST = '697011782709a76095ea705dab1ee1e862891b9bd7f717a4f0221075c28b8ef2'
# Versioned amendments that add models (path -> frozen digest). Each must amend the base
# digest above and may only ADD models; prompts, scoring, gates and analysis are unchanged.
AMENDMENTS = {'configs/controlled_h_v3_inference_amendment1.json': 'bac116c3e1d7f4a4c2227df2e5b73466ae2935df1cd7a5ec3407e810b3b36993',
              'configs/controlled_h_v3_inference_amendment3.json': '6eb87256470c742db1174706480ddc6f65b17e21ac5f6f9960e5819b7a8c19d4',
              'configs/controlled_h_v3_inference_amendment4.json': '899adb8313cbba0228fe79f10d9b256f80d0a0b0a09456e65e4a0e9cd18abf86',
              'configs/controlled_h_v3_inference_amendment5.json': '6b212296a3dde6c498bae73510e354d7255c941a0728b1d0a7af19a41149f49e',
              'configs/controlled_h_v3_inference_amendment7.json': 'eaa20e7d6a2bc304ae40109835f5b3e80d3b8e28cfc5a3405adca61aa201ed16',
              'configs/controlled_h_v3_inference_amendment8.json': '33d68bddaccecce61ddc9e56e4206597f1e1c19085217ab630472aae660a068d'}
# Prompt conditions beyond the base protocol (name -> (amendment path, frozen digest)).
CONDITIONS = {'defined': ('configs/controlled_h_v3_inference_amendment2.json',
                          'eadf64f3cea0c40497855b24b9547deca57adeb89de4aa9a79fa55ad89378e67')}
OUT = ROOT / 'results/controlled_h_v3_inference'


def condition_config(cfg, digest, condition):
    """Derived config for a prompt condition; 'base' returns cfg unchanged."""
    if condition == 'base':
        return cfg
    rel, frozen = CONDITIONS[condition]
    am = json.loads((ROOT / rel).read_text(encoding='utf-8'))
    if c.digest_json(am) != frozen or am['amends_protocol_digest'] != digest:
        raise ValueError('condition amendment differs from its freeze or amends another protocol')
    out = json.loads(json.dumps(cfg))
    out['protocol_id'] = am['amendment_id']
    out['inference']['horizons'] = am['horizons']
    out['inference']['authorized_models'] = [m for m in am['models']
                                             if m in cfg['inference']['authorized_models']]
    out['_condition'] = dict(name=condition, amendment_id=am['amendment_id'], digest=frozen,
                             anchor=am['prompt_change']['anchor'],
                             insert=am['prompt_change']['inserted_after_anchor'])
    return out


def apply_condition(cfg, horizon, user):
    cond = cfg.get('_condition')
    if not cond:
        return user
    anchor = cond['anchor'].replace('{H}', str(horizon))
    if user.count(anchor) != 1:
        raise ValueError('condition anchor not found exactly once in the user prompt')
    return user.replace(anchor, anchor + cond['insert'])


def load_config(path=CONFIG, require_frozen=True):
    cfg = json.loads(path.read_text(encoding='utf-8'))
    digest = c.digest_json(cfg)
    if require_frozen and digest != FROZEN_DIGEST:
        raise ValueError('inference config differs from the registered freeze')
    cfg['_amendments'] = {}
    for rel, frozen in AMENDMENTS.items():
        am = json.loads((ROOT / rel).read_text(encoding='utf-8'))
        if c.digest_json(am) != frozen or am['amends_protocol_digest'] != digest:
            raise ValueError(f'amendment {rel} differs from its freeze or amends another protocol')
        for name, spec in am['add_models'].items():
            if name in cfg['inference']['models']:
                raise ValueError(f'amendment may only add models: {name}')
            cfg['inference']['models'][name] = spec
            cfg['inference']['authorized_models'].append(name)
            cfg['_amendments'][name] = dict(amendment_id=am['amendment_id'], digest=frozen)
    return cfg, digest


# ---------------------------------------------------------------- context / schedule
def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_context(cfg, source_dir=ROOT / 'results'):
    src = {}
    for key, spec in cfg['sources'].items():
        path = source_dir / spec['filename']
        if _sha(path) != spec['sha256']:
            raise ValueError(f'source {key} hash mismatch')
        src[key] = json.loads(path.read_text(encoding='utf-8'))
    audit, recipes, full = src['release_audit'], src['release_fixtures'], src['full']
    if audit['protocol_digest'] != cfg['fixture_protocol_digest'] or \
            full['protocol_digest'] != cfg['fixture_protocol_digest']:
        raise ValueError('release/audit built under a different fixture protocol')
    if not audit['selection']['release_gate_passed']:
        raise ValueError('fixture release gate did not pass')
    ids = [f['fixture_id'] for f in recipes]
    if len(ids) != len(set(ids)) or set(ids) != set(audit['selection']['selected_fixture_ids']):
        raise ValueError('release fixtures differ from the selection')
    sensitivity = {d['fixture_id']: d['h1_h8_sensitive']
                   for d in audit['selection']['dispositions'] if d['released']}
    rows = {r['fixture']['fixture_id']: r for r in full['rows']}
    fixtures, oracles, prompts = {}, {}, {}
    prompt_protocol = {'inference': {'horizons': cfg['inference']['horizons'],
                                     'prompt_format': cfg['inference']['prompt_format']}}
    for recipe in recipes:
        fid = recipe['fixture_id']
        row = rows[fid]
        if row['fixture'] != recipe:
            raise ValueError('oracle recipe mismatch')
        fixture = ControlledFixture.from_dict(recipe)
        state = load_fixture(fixture)
        vocab = {f'{a.action}:{a.card_index}:{a.target_index}' for a in legal_actions(state)}
        for h in cfg['inference']['horizons']:
            o = row['oracles'][str(h)]
            if not o['exact'] or set(o['action_values']) != vocab:
                raise ValueError('oracle exactness/action vocabulary mismatch')
            values = list(o['action_values'].values())
            if max(values) != o['best_value'] or min(values) != o['worst_value']:
                raise ValueError('oracle extrema mismatch')
        fixtures[fid], oracles[fid] = fixture, row
        prompts[fid] = {h: (sy, apply_condition(cfg, h, us))
                        for h, (sy, us) in c.prompt_contract(fixture, prompt_protocol).items()}
    for char in cfg['release']['characters']:
        for tag, quota in ((True, cfg['release']['sensitive_per_character']),
                           (False, cfg['release']['control_per_character'])):
            if sum(f.character == char and sensitivity[fid] is tag for fid, f in fixtures.items()) != quota:
                raise ValueError('release stratum quota mismatch')
    return fixtures, oracles, sensitivity, prompts


def horizon_orders(horizons):
    """Cyclic Latin square: every H appears once in every within-fixture position."""
    h = list(horizons)
    return [tuple(h[i:] + h[:i]) for i in range(len(h))]


def schedule(cfg, fixtures, sensitivity):
    """All H per fixture; Latin-square order cycled within character x sensitivity."""
    ns = cfg['protocol_id']
    rank = lambda tag, fid: hashlib.sha256(f'{ns}:{tag}:{fid}'.encode()).hexdigest()
    latin = horizon_orders(cfg['inference']['horizons'])
    orders = {}
    for char in cfg['release']['characters']:
        for tag in (True, False):
            ids = sorted((fid for fid, f in fixtures.items()
                          if f.character == char and sensitivity[fid] is tag),
                         key=lambda fid: rank('order', fid))
            orders.update({fid: latin[i % len(latin)] for i, fid in enumerate(ids)})
    out = []
    for fid in sorted(fixtures, key=lambda fid: rank('fixture', fid)):
        for pos, horizon in enumerate(orders[fid]):
            out.append(dict(index=len(out), fixture_id=fid, character=fixtures[fid].character,
                            h1_h8_sensitive=sensitivity[fid], horizon=horizon,
                            query_order_within_fixture=pos))
    return out


# ---------------------------------------------------------------- serving contract
def model_spec(cfg, model):
    return cfg['inference']['models'][model]


def stack_versions(cfg, model):
    """Pinned serving versions; an amendment may pin a different stack for one model."""
    m = model_spec(cfg, model)
    return {k: m.get(k + '_version', cfg['inference'][k + '_version']) for k in ('vllm', 'transformers')}


def server_command(cfg, model, port):
    inf, m = cfg['inference'], model_spec(cfg, model)
    return ['-m', 'vllm.entrypoints.openai.api_server', '--model', m['repository'],
            '--revision', m['revision'], '--tokenizer-revision', m['revision'],
            '--served-model-name', model, '--tensor-parallel-size', str(m.get('tensor_parallel_size', 1)),
            '--max-model-len', str(inf['max_model_len']),
            '--gpu-memory-utilization', str(inf['gpu_memory_utilization']),
            '--dtype', 'bfloat16', '--max-num-seqs', str(inf['max_num_seqs']),
            *(['--quantization', m['quantization']] if m.get('quantization') else []),
            *m.get('extra_server_args', []),  # amendment-pinned serving flags (e.g. Amendment 7)
            '--generation-config', 'vllm', '--host', '127.0.0.1', '--port', str(port)]


def contract(cfg, digest, model, mock):
    code = {p: hashlib.sha256((ROOT / p).read_text(encoding='utf-8').encode()).hexdigest()
            for p in ('scripts/heldout_v3_inference.py', 'cluster/sharanga_v3_inference.sbatch')}
    out = dict(protocol_digest=digest, model=model, mock=mock, code=code,
               frozen_v2_code_receipt=c.code_receipt())
    if model in cfg.get('_amendments', {}):
        out['amendment'] = cfg['_amendments'][model]
    if cfg.get('_condition'):
        out['condition'] = {k: cfg['_condition'][k] for k in ('name', 'amendment_id', 'digest')}
    return out


def contract_matches(saved, current, strict):
    """strict (writing rows): identical. Otherwise (status/analysis of finished evidence):
    everything but the runner's own code hash must match; scores are re-derived by replay
    with the frozen v2 scoring code, whose receipt is still compared."""
    if strict:
        return saved == current
    strip = lambda x: {k: v for k, v in x.items() if k != 'code'}
    return strip(saved) == strip(current)


def thinking(cfg, model):
    """enable_thinking for this model; an amendment may switch it off for one model (Amendment 8)."""
    return model_spec(cfg, model).get('enable_thinking', cfg['inference']['enable_thinking'])


def request_payload(cfg, model, messages):
    inf = cfg['inference']
    return dict(model=model, messages=messages, max_tokens=inf['max_tokens'],
                temperature=inf['temperature'], top_p=inf['top_p'], top_k=inf['top_k'],
                seed=inf['seed'], chat_template_kwargs={'enable_thinking': thinking(cfg, model)})


def messages(query, prompts):
    system, user = prompts[query['fixture_id']][query['horizon']]
    return [dict(role='system', content=system), dict(role='user', content=user)]


def http_json(url, payload=None, timeout=30):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as r:
        return json.load(r)


def receipt_ok(r, cfg, digest, model, port, strict=True):
    return (contract_matches(r['contract'], contract(cfg, digest, model, False), strict)
            and r['command'] == server_command(cfg, model, port) and r['port'] == port
            and r['runtime_versions'] == stack_versions(cfg, model))


# ---------------------------------------------------------------- evidence store
def model_dir(model, mock, cfg=None):
    cond = (cfg or {}).get('_condition')
    return OUT / ('mock' if mock else 'real') / (model + (f"__{cond['name']}" if cond else ''))


def row_file(d, index):
    return d / 'rows' / f'{index:05d}.json'


def pending_file(d, index):
    return d / 'rows' / f'{index:05d}.pending'


def load_rows(cfg, digest, model, mock, queries, ctx, strict=True):
    """Replay every saved row; convert orphaned in-flight markers to ambiguous failures."""
    d = model_dir(model, mock, cfg)
    _, oracles, _, prompts = ctx
    meta_path = d / 'contract.json'
    if meta_path.exists():
        if not contract_matches(json.loads(meta_path.read_text(encoding='utf-8')),
                                contract(cfg, digest, model, mock), strict):
            raise ValueError('contract drift; preserve evidence and review')
    rows = {}
    for q in queries:
        path, pend = row_file(d, q['index']), pending_file(d, q['index'])
        if pend.exists() and not path.exists():
            row = c.make_row(q, prompts[q['fixture_id']], oracles[q['fixture_id']],
                             {'error': 'ambiguous_query'}, None, None, 'ambiguous_query')
            evidence = dict(error_type='lost_in_flight', server_receipt=None, received_response=None,
                            request=json.loads(pend.read_text(encoding='utf-8')))
            _atomic_write_json(path, dict(row=row, evidence=evidence,
                                          evidence_sha256=c.digest_json(evidence)))
        if pend.exists():
            pend.unlink()
        if not path.exists():
            continue
        entry = json.loads(path.read_text(encoding='utf-8'))
        c.validate_row(entry['row'], q, prompts[q['fixture_id']], oracles[q['fixture_id']])
        if c.digest_json(entry['evidence']) != entry['evidence_sha256']:
            raise ValueError(f'evidence checksum mismatch at {q["index"]}')
        if entry['evidence']['request'] != request_payload(cfg, model, messages(q, prompts)):
            raise ValueError(f'saved request differs from the protocol at {q["index"]}')
        rec = entry['evidence'].get('server_receipt')
        if mock and rec is not None:
            raise ValueError('mock evidence carries real provenance')
        if not mock and rec is not None and not receipt_ok(rec, cfg, digest, model, rec['port'], strict):
            raise ValueError(f'row {q["index"]} was produced by a non-protocol server')
        if not mock and rec is None and entry['evidence'].get('error_type') != 'lost_in_flight':
            raise ValueError(f'row {q["index"]} lacks server provenance')
        rows[q['index']] = entry
    return rows


def clean(row):
    return (all(row['score'].get(k) is True for k in ('parse_ok', 'schema_ok', 'legal'))
            and not row['diagnostics']['truncated'] and row['diagnostics']['execution_failure'] is None)


# ---------------------------------------------------------------- run
def ask(cfg, model, q, ctx, base, receipt, mock, tokens):
    """One request, never retried. Returns (row, evidence)."""
    _, oracles, _, prompts = ctx
    payload = request_payload(cfg, model, messages(q, prompts))
    started, response, failure = time.monotonic(), None, None
    try:
        response = ({'choices': [{'message': {'content': '{"action":"end_turn"}'},
                                  'finish_reason': 'stop'}], 'usage': {}} if mock else
                    http_json(base + '/v1/chat/completions', payload, cfg['inference']['timeout_seconds']))
        raw = response['choices'][0]['message']['content']
        finish = response['choices'][0]['finish_reason']
        if raw is None and finish == 'length':
            raw = ''  # budget exhausted inside a separate reasoning channel: a truncation, not a failure
        if not isinstance(raw, str):
            raise ValueError('missing response text')
        replay = c.Replay(); replay.raw = raw; replay.last_finish_reason = finish
        parsed = replay.complete_json('', '')
        evidence = dict(response=response, request=payload, server_receipt=receipt,
                        elapsed_seconds=time.monotonic() - started, tokenized_prompt_tokens=tokens)
    except Exception as exc:  # noqa: BLE001 - every failure is recorded, never retried
        failure = 'transport_failure' if response is None else 'ambiguous_query'
        raw, finish, parsed = None, None, {'error': failure}
        evidence = dict(error_type=type(exc).__name__, elapsed_seconds=time.monotonic() - started,
                        server_receipt=receipt, received_response=response, request=payload)
    row = c.make_row(q, prompts[q['fixture_id']], oracles[q['fixture_id']], parsed, raw, finish, failure)
    return row, evidence


def smoke_gate(cfg, rows):
    """Automatic gate on the first smoke_queries rows: no execution failure, <=1 truncation."""
    n = cfg['inference']['smoke_queries']
    first = [rows[i]['row'] for i in range(n) if i in rows]
    if len(first) < n:
        return None
    ok = (all(r['diagnostics']['execution_failure'] is None for r in first)
          and sum(r['diagnostics']['truncated'] for r in first) <= 1)
    return ok


def run(args, cfg, digest):
    ctx = load_context(cfg)
    queries = schedule(cfg, ctx[0], ctx[2])
    d = model_dir(args.model, args.mock, cfg)
    (d / 'rows').mkdir(parents=True, exist_ok=True)
    with c.exclusive_writer(d / 'run'):
        meta = d / 'contract.json'
        if not meta.exists():
            _atomic_write_json(meta, contract(cfg, digest, args.model, args.mock))
        rows = load_rows(cfg, digest, args.model, args.mock, queries, ctx)
        if any(r['row']['diagnostics']['execution_failure'] for r in rows.values()):
            raise ValueError('an execution failure exists; inspect before spending more compute')
        receipt, base, tokens = None, None, {}
        inf = cfg['inference']
        if not args.mock:
            if not (args.authorize_model_inference and args.receipt and args.stop_at_unix):
                raise ValueError('real inference needs authorization, receipt and deadline')
            receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
            if not receipt_ok(receipt, cfg, digest, args.model, args.port):
                raise ValueError('server receipt does not match the protocol')
            base = f'http://localhost:{args.port}'
            live = http_json(base + '/v1/models')['data']
            if not any(m['id'] == args.model and m.get('max_model_len') == inf['max_model_len'] for m in live):
                raise ValueError('live model/context mismatch')
            for q in queries:
                if q['index'] in rows:
                    continue
                v = http_json(base + '/tokenize', dict(model=args.model, messages=messages(q, ctx[3]),
                              add_generation_prompt=True,
                              chat_template_kwargs={'enable_thinking': thinking(cfg, args.model)}))
                if v['count'] + inf['max_tokens'] > inf['max_model_len']:
                    raise ValueError('prompt plus output allowance exceeds context')
                tokens[q['index']] = v['count']
        gate = smoke_gate(cfg, rows)
        if gate is False:
            raise ValueError('smoke gate failed; inspect before further inference')
        todo = [q for q in queries if q['index'] not in rows]
        if gate is None:  # smoke first: only the first smoke_queries indices this round
            todo = [q for q in todo if q['index'] < inf['smoke_queries']]
        if args.max_new:
            todo = todo[:args.max_new]
        lock, stop = threading.Lock(), threading.Event()
        workers = 1 if args.mock else inf['concurrency']

        def deadline_ok():
            return args.mock or time.time() + inf['timeout_seconds'] + inf['deadline_headroom_seconds'] < args.stop_at_unix

        def save(q, row, evidence):
            with lock:
                _atomic_write_json(row_file(d, q['index']),
                                   dict(row=row, evidence=evidence, evidence_sha256=c.digest_json(evidence)))
                pending_file(d, q['index']).unlink(missing_ok=True)
                rows[q['index']] = dict(row=row)
                print(json.dumps(dict(index=q['index'], done=len(rows), total=len(queries), H=q['horizon'],
                                      clean=clean(row), s=round(evidence['elapsed_seconds'], 1))), flush=True)
                if row['diagnostics']['execution_failure']:
                    stop.set()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            it, inflight = iter(todo), {}
            while True:
                while len(inflight) < workers and not stop.is_set() and deadline_ok():
                    q = next(it, None)
                    if q is None:
                        break
                    _atomic_write_json(pending_file(d, q['index']),
                                       request_payload(cfg, args.model, messages(q, ctx[3])))
                    inflight[pool.submit(ask, cfg, args.model, q, ctx, base, receipt,
                                         args.mock, tokens.get(q['index']))] = q
                if not inflight:
                    break
                finished, _ = wait(inflight, return_when=FIRST_COMPLETED)
                for f in finished:
                    save(inflight.pop(f), *f.result())
        gate = smoke_gate(cfg, rows)
        print(json.dumps(dict(completed=len(rows), total=len(queries), smoke_gate=gate,
                              stopped_on_failure=stop.is_set())), flush=True)
        if gate is True and len(rows) < len(queries) and not stop.is_set() and deadline_ok() and not args.max_new:
            return 'continue'
        return 'done'


# ---------------------------------------------------------------- analysis
def _optimal(oracle_row, h):
    return {f"{a['action']}:{a['card_index']}:{a['target_index']}"
            for a in oracle_row['oracles'][str(h)]['optimal_actions']}


def _key(score):
    a = score.get('scored_action')
    return None if not a else f"{a['action']}:{a['card_index']}:{a['target_index']}"


def cf_gain(oracle_row, h, row_h, row_1):
    """EQ_H(a_H) - EQ_H(a_1): both answers scored under the SAME H oracle.

    An H-blind model gives the same answer at H and H1, so its gain is exactly 0. The raw
    q_H - q_1 is NOT H-blind invariant: the same action's normalized quality changes with H
    (caught by the constant-action mock, 2026-09-30)."""
    s1 = score_precomputed_oracle(oracle_row, h, row_1['response_parsed'])
    return row_h['effective_quality'] - c.effective_quality(s1, row_1['diagnostics']['truncated'])


def did_bootstrap(sens, ctrl, reps, seed, alpha):
    obs = statistics.fmean(sens) - statistics.fmean(ctrl)
    rng = random.Random(seed)
    boots = sorted(statistics.fmean(rng.choices(sens, k=len(sens))) -
                   statistics.fmean(rng.choices(ctrl, k=len(ctrl))) for _ in range(reps))
    lo, hi = boots[int(alpha / 2 * reps)], boots[int((1 - alpha / 2) * reps) - 1]
    p = sum(abs(b - obs) >= abs(obs) for b in boots) / reps
    return dict(estimate=obs, ci_low=lo, ci_high=hi, ci_level=1 - alpha, p_two_sided=p,
                bootstrap_sd=statistics.stdev(boots), sensitive_n=len(sens), control_n=len(ctrl),
                sensitive_mean_dH=statistics.fmean(sens), control_mean_dH=statistics.fmean(ctrl))


def analyze(cfg, digest, model, mock=False, rows=None, ctx=None):
    ctx = ctx or load_context(cfg)
    queries = schedule(cfg, ctx[0], ctx[2])
    rows = rows if rows is not None else load_rows(cfg, digest, model, mock, queries, ctx, strict=False)
    a, inf = cfg['analysis'], cfg['inference']
    by_fixture = {}
    for q in queries:
        if q['index'] in rows:
            by_fixture.setdefault(q['fixture_id'], {})[q['horizon']] = rows[q['index']]['row']
    total = len(queries)
    done = sum(q['index'] in rows for q in queries)
    trunc = sum(r['row']['diagnostics']['truncated'] for r in rows.values())
    exec_fail = {fid for fid, hs in by_fixture.items()
                 if any(r['diagnostics']['execution_failure'] for r in hs.values())}
    complete_pairs = {fid: hs for fid, hs in by_fixture.items()
                      if set(hs) == set(inf['horizons']) and fid not in exec_fail}
    n_fix = len(ctx[0])
    gates = dict(complete=done == total,
                 truncation_rate=trunc / max(done, 1),
                 truncation_ok=trunc / max(done, 1) <= a['max_truncation_rate'],
                 excluded_pair_rate=(n_fix - len(complete_pairs)) / n_fix,
                 excluded_pairs_ok=(n_fix - len(complete_pairs)) / n_fix <= a['max_excluded_pair_rate'])
    valid = all(gates[k] for k in ('complete', 'truncation_ok', 'excluded_pairs_ok'))
    out = dict(model=model, protocol_digest=digest, completed_queries=done, total_queries=total,
               gates=gates, valid_for_primary_inference=valid, by_character={})
    alpha = a['alpha_per_character']
    for char in cfg['release']['characters']:
        dh, raw = {True: [], False: []}, {True: [], False: []}
        switch = {'h8_picks_h8_opt': 0, 'h8_picks_h1_opt_only': 0, 'h8_other': 0,
                  'h1_picks_h8_opt': 0, 'discordant_h8_only': 0, 'discordant_h1_only': 0, 'n': 0}
        for fid, hs in complete_pairs.items():
            if ctx[0][fid].character != char:
                continue
            tag = ctx[2][fid]
            dh[tag].append(cf_gain(ctx[1][fid], 8, hs[8], hs[1]))
            raw[tag].append(hs[8]['effective_quality'] - hs[1]['effective_quality'])
            if tag:
                o = ctx[1][fid]
                o1, o8 = _optimal(o, 1), _optimal(o, 8)
                k8, k1 = _key(hs[8]['score']), _key(hs[1]['score'])
                switch['n'] += 1
                if k8 in o8:
                    switch['h8_picks_h8_opt'] += 1
                elif k8 in o1:
                    switch['h8_picks_h1_opt_only'] += 1
                else:
                    switch['h8_other'] += 1
                h1_hit, h8_hit = k1 in o8, k8 in o8
                switch['h1_picks_h8_opt'] += h1_hit
                switch['discordant_h8_only'] += h8_hit and not h1_hit
                switch['discordant_h1_only'] += h1_hit and not h8_hit
        res = dict(primary=did_bootstrap(dh[True], dh[False], a['bootstrap_replicates'],
                                         a['bootstrap_seed_by_character'][char], alpha)
                   if min(len(dh[True]), len(dh[False])) >= 2 else None,
                   action_switch=switch,
                   legacy_mixture=(a['legacy_mixture_weights'][0] * statistics.fmean(raw[True]) +
                                   a['legacy_mixture_weights'][1] * statistics.fmean(raw[False]))
                   if raw[True] and raw[False] else None,
                   raw_dH_descriptive={'sensitive': statistics.fmean(raw[True]) if raw[True] else None,
                                       'control': statistics.fmean(raw[False]) if raw[False] else None,
                                       'note': 'q8-q1 on own oracles; not H-blind invariant'})
        b, m = switch['discordant_h8_only'], switch['discordant_h1_only']
        res['action_switch']['mcnemar_exact_p'] = _binom_two_sided(b, b + m) if b + m else None
        res['lookahead_curve'] = lookahead_curve(
            {fid: hs for fid, hs in complete_pairs.items() if ctx[0][fid].character == char},
            ctx[1], inf['horizons'])
        if res['primary']:
            pr = res['primary']
            pr['reject_null'] = bool(valid and pr['p_two_sided'] < alpha)
            pr['ci_excludes_sei'] = dict(
                benefit=bool(valid and pr['ci_low'] >= a['smallest_effect_of_interest']),
                harm=bool(valid and pr['ci_high'] <= -a['smallest_effect_of_interest']))
        out['by_character'][char] = res
    return out


def lookahead_curve(sets, oracles, horizons):
    """Per H>1, on fixtures whose H-optimal set is disjoint from the H1-optimal set:
    use = response at H is H-optimal; myopic = response at H is H1-optimal only;
    ignore_baseline = the H1 response is H-optimal (what an H-blind model would score);
    McNemar pairs (response at H hits H-opt) with (response at H1 hits H-opt).
    Also the per-H difference-in-differences with per-H sensitivity labels."""
    out = {}
    for h in horizons[1:]:
        use = myopic = base = b = m = 0
        sens_dq, ctrl_dq = [], []
        for fid, hs in sets.items():
            o1, oh = _optimal(oracles[fid], 1), _optimal(oracles[fid], h)
            dq = cf_gain(oracles[fid], h, hs[h], hs[1])
            if not o1.isdisjoint(oh):
                ctrl_dq.append(dq)
                continue
            sens_dq.append(dq)
            kh, k1 = _key(hs[h]['score']), _key(hs[1]['score'])
            hit_h, hit_1 = kh in oh, k1 in oh
            use += hit_h
            myopic += (kh in o1)
            base += hit_1
            b += hit_h and not hit_1
            m += hit_1 and not hit_h
        n = len(sens_dq)
        out[str(h)] = dict(
            sensitive_n=n, control_n=len(ctrl_dq),
            lookahead_use_rate=use / n if n else None,
            myopic_rate=myopic / n if n else None,
            ignore_baseline_rate=base / n if n else None,
            mcnemar_exact_p=_binom_two_sided(b, b + m) if b + m else None,
            did=(statistics.fmean(sens_dq) - statistics.fmean(ctrl_dq)) if n and ctrl_dq else None)
    return out


def _paired_sets(cfg, digest, model, ctx):
    queries = schedule(cfg, ctx[0], ctx[2])
    rows = load_rows(cfg, digest, model, False, queries, ctx, strict=False)
    if len(rows) != len(queries):
        return None
    sets = {}
    for q in queries:
        sets.setdefault(q['fixture_id'], {})[q['horizon']] = rows[q['index']]['row']
    return sets


def ablation(base_cfg, cond_cfg, digest):
    """Pre-registered Amendment 2 contrast: DiD_defined - DiD_original at H8, paired by fixture."""
    a = base_cfg['analysis']
    ctx_b, ctx_d = load_context(base_cfg), load_context(cond_cfg)
    oracles, sens, fixtures = ctx_b[1], ctx_b[2], ctx_b[0]
    tests, out = [], {}
    for model in cond_cfg['inference']['authorized_models']:
        sb, sd = _paired_sets(base_cfg, digest, model, ctx_b), _paired_sets(cond_cfg, digest, model, ctx_d)
        if sb is None or sd is None:
            out[model] = dict(status='incomplete: needs both conditions complete')
            continue
        base_valid = analyze(base_cfg, digest, model, ctx=ctx_b)['valid_for_primary_inference']
        cond_valid = analyze(cond_cfg, digest, model, ctx=ctx_d)['valid_for_primary_inference']
        out[model] = dict(original_condition_valid=base_valid, defined_condition_valid=cond_valid,
                          by_character={})
        for char in base_cfg['release']['characters']:
            diff = {True: [], False: []}
            b = m = hit_b = hit_d = 0
            for fid in fixtures:
                if fixtures[fid].character != char:
                    continue
                o = oracles[fid]
                gb = cf_gain(o, 8, sb[fid][8], sb[fid][1])
                gd = cf_gain(o, 8, sd[fid][8], sd[fid][1])
                diff[sens[fid]].append(gd - gb)
                if sens[fid]:
                    o8 = _optimal(o, 8)
                    xb, xd = _key(sb[fid][8]['score']) in o8, _key(sd[fid][8]['score']) in o8
                    hit_b += xb; hit_d += xd; b += xd and not xb; m += xb and not xd
            r = did_bootstrap(diff[True], diff[False], a['bootstrap_replicates'],
                              a['bootstrap_seed_by_character'][char] + 100, 0.05)
            n = len(diff[True])
            res = dict(contrast=r, h8_use_original=hit_b / n, h8_use_defined=hit_d / n,
                       mcnemar_exact_p=_binom_two_sided(b, b + m) if b + m else None)
            out[model]['by_character'][char] = res
            tests.append((r['p_two_sided'], model, char))
    # Holm across all completed model x character contrasts (familywise .05).
    ordered = sorted(tests)
    k = len(ordered)
    running = 0.0
    for i, (p, model, char) in enumerate(ordered):
        running = max(running, min(1.0, (k - i) * p))
        valid = out[model]['original_condition_valid'] and out[model]['defined_condition_valid']
        out[model]['by_character'][char]['contrast']['holm_p'] = running
        out[model]['by_character'][char]['contrast']['reject_holm_05'] = bool(valid and running < .05)
    return dict(holm_family_size=k, family_complete=k == 2 * len(cond_cfg['inference']['authorized_models']),
                models=out)


def _binom_two_sided(k, n):
    """Exact two-sided binomial test at p=.5 (McNemar exact)."""
    probs = [math.comb(n, i) / 2 ** n for i in range(n + 1)]
    return min(1.0, sum(p for p in probs if p <= probs[k] + 1e-15))


# ---------------------------------------------------------------- CLI
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'server', 'run', 'status', 'analyze', 'ablation'))
    parser.add_argument('--model', required=True)
    parser.add_argument('--mock', action='store_true')
    parser.add_argument('--port', type=int, default=18900)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--stop-at-unix', type=float)
    parser.add_argument('--max-new', type=int)
    parser.add_argument('--authorize-model-inference', action='store_true')
    parser.add_argument('--condition', choices=('base',) + tuple(CONDITIONS), default='base')
    args = parser.parse_args()
    cfg, digest = load_config()
    cfg = condition_config(cfg, digest, args.condition)
    if args.model not in cfg['inference']['models']:
        parser.error('unknown model')
    if args.action in ('server', 'run') and not args.mock and \
            args.model not in cfg['inference']['authorized_models']:
        parser.error('model is pre-specified but not yet authorized; add it by versioned amendment')
    if args.action == 'server':
        if args.mock or not args.authorize_model_inference or sys.platform == 'win32':
            parser.error('server requires authorized Linux execution')
        if args.receipt is None or args.receipt.exists():
            parser.error('supply a new receipt path')
        for pkg in ('vllm', 'transformers'):
            if _package_version(pkg) != stack_versions(cfg, args.model)[pkg]:
                raise ValueError(f'{pkg} differs from the protocol')
        cmd = server_command(cfg, args.model, args.port)
        _atomic_write_json(args.receipt, dict(contract=contract(cfg, digest, args.model, False),
                                              command=cmd, port=args.port, pid=os.getpid(),
                                              runtime_versions={k: _package_version(k)
                                                                for k in ('vllm', 'transformers')}))
        os.execv(sys.executable, [sys.executable] + cmd)
    if args.action == 'run':
        while run(args, cfg, digest) == 'continue':
            pass  # smoke passed: continue to the full schedule in the same allocation
        return
    if args.action == 'ablation':
        if args.condition == 'base':
            parser.error('ablation compares a condition against base; pass --condition')
        base_cfg, _ = load_config()
        result = ablation(base_cfg, cfg, digest)
        path = OUT / 'real' / f'ablation_{args.condition}.json'
        _atomic_write_json(path, result)
        print(json.dumps(result, indent=1))
        return
    if args.action == 'analyze':
        result = analyze(cfg, digest, args.model, args.mock)
        path = model_dir(args.model, args.mock, cfg) / 'analysis.json'
        _atomic_write_json(path, result)
        print(json.dumps(result, indent=1))
        return
    ctx = load_context(cfg)
    queries = schedule(cfg, ctx[0], ctx[2])
    rows = load_rows(cfg, digest, args.model, args.mock, queries, ctx, strict=False)
    print(json.dumps(dict(completed=len(rows), total=len(queries), smoke_gate=smoke_gate(cfg, rows),
                          clean=sum(clean(r['row']) for r in rows.values()),
                          truncated=sum(r['row']['diagnostics']['truncated'] for r in rows.values()),
                          execution_failures=sum(bool(r['row']['diagnostics']['execution_failure'])
                                                 for r in rows.values()))))


if __name__ == '__main__':
    main()
