#!/usr/bin/env python
"""Frozen controlled-H confirmation with immutable per-query checkpoints."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.controlled_horizon_model_pilot import (
    score_precomputed_oracle, validate_serving_stack,
    _package_version,
)
from scripts.controlled_horizon_pilot import _atomic_write_json, _git_value
from slay_bench.benchmark import LLMInterface, LocalLLM, MockLLM, RateLimitExhausted
from slay_bench.controlled_horizon import (
    CONTROLLED_ACTION_SCORING_VERSION, ControlledFixture, load_fixture, legal_actions, build_prompt,
)

PROTOCOL_PATH = ROOT / 'configs/controlled_h_v2_confirmatory.json'
FROZEN_DIGEST = '76bf7f917b46ffbe7d6deab859b961a28e4251e4cf875a17e12828d0795de1da'
LATIN = ((1, 2, 8, 4), (2, 4, 1, 8), (4, 8, 2, 1), (8, 1, 4, 2))


def prompt_contract(fixture, protocol):
    # Legal-action enumeration may refresh dynamic card costs in-place.
    # Reconstruct the identical fixture before every horizon's serialization.
    prompts = {}
    for h in protocol['inference']['horizons']:
        state = load_fixture(fixture)
        legal_actions(state)  # Refresh dynamic costs before the visible hand is serialized.
        prompts[h] = build_prompt(state, h, protocol['inference']['prompt_format'])
    systems = {s for s, _ in prompts.values()}
    normalized = {u.replace(f'after exactly {h} decision transitions',
                            'after exactly <H> decision transitions')
                  for h, (_, u) in prompts.items()}
    if len(systems) != 1 or len(normalized) != 1:
        raise ValueError('fixture prompts change beyond H')
    return prompts


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_protocol(path=PROTOCOL_PATH):
    protocol = json.loads(path.read_text(encoding='utf-8'))
    digest = digest_json(protocol)
    if digest != FROZEN_DIGEST:
        raise ValueError('confirmatory protocol differs from freeze')
    if protocol.get('implementation_sha256') != code_receipt():
        raise ValueError('implementation differs from frozen code receipt')
    return protocol, digest


def code_receipt():
    paths = sorted(set(ROOT.glob('slay_bench/*.py')) |
                   set(ROOT.glob('scripts/controlled_horizon*.py')))
    result = {}
    for path in paths:
        source = path.read_text(encoding='utf-8')
        if path.name == 'controlled_horizon_confirmatory.py':
            # Exclude only the self-referential protocol digest literal.
            source = re.sub(r"(?m)^FROZEN_DIGEST = '[0-9a-f]{64}'$", "FROZEN_DIGEST = '<protocol-digest>'", source)
        result[path.relative_to(ROOT).as_posix()] = hashlib.sha256(source.encode()).hexdigest()
    return result


def serving_receipt(protocol, path, base_url):
    """Bind the endpoint to the launcher's exact, locally attested command."""
    from scripts.controlled_horizon_confirmatory_server import server_command
    receipt = json.loads(path.read_text(encoding='utf-8'))
    endpoint = hashlib.sha256(base_url.rstrip('/').encode()).hexdigest()
    if (receipt.get('protocol_digest') != digest_json(protocol)
            or receipt.get('endpoint_sha256') != endpoint
            or receipt.get('command') != server_command(protocol, receipt.get('port'))
            or receipt.get('runtime_versions') != {
                k: protocol['inference']['serving_stack'][k+'_version']
                for k in ('vllm', 'transformers')}):
        raise ValueError('server launch receipt differs from frozen stack or endpoint')
    return dict(endpoint_sha256=endpoint, launch_receipt=receipt)


def verify_live_server(provenance):
    """Require the Linux launch process to still be running its attested command."""
    receipt = provenance['launch_receipt']
    command_path = Path('/proc') / str(int(receipt['pid'])) / 'cmdline'
    command = command_path.read_bytes().decode().rstrip('\0').split('\0')
    if command[1:] != receipt['command']:
        raise ValueError('live server command differs from launch receipt')


def load_context(protocol, source_dir):
    sources = {}
    for key, spec in protocol['sources'].items():
        path = (source_dir / spec['filename'] if spec['kind'] == 'result'
                else ROOT / spec['filename'])
        value = json.loads(path.read_text(encoding='utf-8'))
        actual_hash = (hashlib.sha256(path.read_bytes()).hexdigest()
                       if spec['kind'] == 'result' else digest_json(value))
        if actual_hash != spec['sha256']:
            raise ValueError(f'source {key} hash mismatch')
        sources[key] = value
    release = sources['release_audit']
    recipes = sources['release_fixtures']['fixtures']
    if not (release['release_gate_passed'] and
            sources['independent_audit']['release_gate_passed']):
        raise ValueError('source release not independently passed')
    if release['protocol_digest'] != protocol['release']['protocol_digest']:
        raise ValueError('release protocol mismatch')
    if len(recipes) != protocol['release']['fixture_count']:
        raise ValueError('release fixture count mismatch')
    pilot_ids = set(sources['pilot']['selection']['selected_fixture_ids'])
    ids = [f['fixture_id'] for f in recipes]
    if len(ids) != len(set(ids)) or set(ids).intersection(pilot_ids):
        raise ValueError('duplicate or pilot-exposed fixture')
    if set(ids) != set(release['selection']['selected_fixture_ids']):
        raise ValueError('release selection mismatch')
    all_rows = [r for key in ('base_full', 'extension_full', 'expansion_full')
                for r in sources[key]['rows']]
    oracles = {r['fixture']['fixture_id']: r for r in all_rows}
    if len(oracles) != len(all_rows):
        raise ValueError('oracle sources overlap')
    sensitivity = {r['fixture_id']: r['h1_h8_sensitive']
                   for r in release['selection']['dispositions'] if r['released']}
    fixtures = {f['fixture_id']: ControlledFixture.from_dict(f) for f in recipes}
    prompts = {}
    for fid, fixture in fixtures.items():
        row = oracles[fid]
        if row['fixture'] != next(f for f in recipes if f['fixture_id'] == fid):
            raise ValueError('oracle recipe mismatch')
        state = load_fixture(fixture)
        vocab = {f'{a.action}:{a.card_index}:{a.target_index}' for a in legal_actions(state)}
        for horizon in protocol['inference']['horizons']:
            o = row['oracles'][str(horizon)]
            if not o['exact'] or set(o['action_values']) != vocab:
                raise ValueError('oracle exactness/action vocabulary mismatch')
            values = list(o['action_values'].values())
            if max(values) != o['best_value'] or min(values) != o['worst_value']:
                raise ValueError('oracle extrema mismatch')
        prompts[fid] = prompt_contract(fixture, protocol)
    for char in protocol['release']['characters']:
        for sensitive, quota in ((True, 63), (False, 189)):
            if sum(f.character == char and sensitivity[fid] == sensitive
                   for fid, f in fixtures.items()) != quota:
                raise ValueError('release stratum quota mismatch')
    return fixtures, {fid: oracles[fid] for fid in fixtures}, sensitivity, prompts


def query_schedule(protocol, fixtures, sensitivity):
    namespace = protocol['protocol_id']
    rank = lambda tag, fid: hashlib.sha256(f'{namespace}:{tag}:{fid}'.encode()).hexdigest()
    orders = {}
    for char in protocol['release']['characters']:
        ids = sorted((fid for fid, f in fixtures.items() if f.character == char),
                     key=lambda fid: rank('latin-order', fid))
        orders.update({fid: LATIN[i % 4] for i, fid in enumerate(ids)})
    schedule = []
    for fid in sorted(fixtures, key=lambda fid: rank('fixture-order', fid)):
        for position, horizon in enumerate(orders[fid]):
            schedule.append(dict(index=len(schedule), fixture_id=fid,
                                 character=fixtures[fid].character,
                                 h1_h8_sensitive=sensitivity[fid], horizon=horizon,
                                 query_order_within_fixture=position))
    return schedule


def effective_quality(score, truncated=False):
    if truncated:
        return 0.0
    if not all(score.get(k) is True for k in ('parse_ok', 'schema_ok', 'legal')):
        return 0.0
    value = score.get('normalized_quality')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('legal score lacks finite quality')
    if not 0 <= value <= 1:
        raise ValueError('legal quality lies outside [0,1]')
    return float(value)


class Replay(LLMInterface):
    def complete(self, system, user, **kwargs):
        return self.raw


def make_row(query, prompts, oracle, parsed, raw, finish_reason, failure=None):
    system, user = prompts[query['horizon']]
    score = score_precomputed_oracle(oracle, query['horizon'], parsed)
    truncated = finish_reason == 'length' or bool(
        isinstance(parsed, dict) and parsed.get('truncated_think'))
    return dict(query, system_prompt=system, user_prompt=user,
                system_prompt_sha256=hashlib.sha256(system.encode()).hexdigest(),
                user_prompt_sha256=hashlib.sha256(user.encode()).hexdigest(),
                response_raw=raw, response_parsed=parsed, score=score,
                effective_quality=effective_quality(score, truncated),
                diagnostics=dict(finish_reason=finish_reason,
                                 truncated=truncated,
                                 execution_failure=failure))


def validate_row(row, query, prompts, oracle):
    if any(row.get(k) != v for k, v in query.items()):
        raise ValueError('row query identity differs from frozen schedule')
    failure = row['diagnostics']['execution_failure']
    if failure is None:
        if not isinstance(row['response_raw'], str):
            raise ValueError('completed response lacks raw text')
        replay = Replay()
        replay.raw = row['response_raw']
        replay.last_finish_reason = row['diagnostics']['finish_reason']
        parsed = replay.complete_json('', '')
    else:
        if failure not in ('transport_failure', 'ambiguous_query') or row['response_raw'] is not None:
            raise ValueError('invalid execution-failure trace')
        parsed = {'error': failure}
    expected = make_row(query, prompts, oracle, parsed, row['response_raw'],
                        row['diagnostics']['finish_reason'], failure)
    if row != expected:
        raise ValueError('saved prompt, parsed response, or score differs on replay')


def row_directory(output):
    return output.with_name(output.name + '.rows')


def row_path(output, index):
    return row_directory(output) / f'{index:06d}.json'


@contextmanager
def exclusive_writer(output):
    output.parent.mkdir(parents=True, exist_ok=True)
    path = output.with_name(output.name + '.lock')
    with path.open('a+b') as handle:
        if path.stat().st_size == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if sys.platform == 'win32':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def load_rows(report, output, schedule, context):
    _, oracles, _, prompts = context
    if len(report['completed_rows']) > len(schedule):
        raise ValueError('too many completed rows')
    rows = []
    for index, entry in enumerate(report['completed_rows']):
        path = row_path(output, index)
        if entry != dict(index=index, sha256=hashlib.sha256(path.read_bytes()).hexdigest()):
            raise ValueError('row checksum or order mismatch')
        row = json.loads(path.read_text(encoding='utf-8'))
        fid = schedule[index]['fixture_id']
        validate_row(row, schedule[index], prompts[fid], oracles[fid])
        rows.append(row)
    if report['complete'] != (len(rows) == len(schedule)):
        raise ValueError('completion metadata inconsistent')
    if report['complete'] and report.get('pending') is not None:
        raise ValueError('complete report has a pending query')
    allowed = {row_path(output, i).name for i in range(len(rows))}
    if report.get('pending') is not None:
        allowed.add(row_path(output, len(rows)).name)
    if any(path.name not in allowed for path in row_directory(output).glob('*.json')):
        raise ValueError('foreign response file outside checkpoint')
    return rows


def run(protocol, digest, context, output, llm=None, provider='mock', phase='smoke',
        authorize=False, max_new=None, cluster_compute=False, resolve_pending=False,
        server_provenance=None):
    if provider != 'mock' and not authorize and not resolve_pending:
        raise ValueError('real inference requires explicit authorization')
    if provider not in ('mock', 'local') or (provider == 'mock' and cluster_compute):
        raise ValueError('invalid provider/compute combination')
    if phase not in ('smoke', 'run') or (max_new is not None and max_new < 1):
        raise ValueError('invalid phase/query budget')
    fixtures, oracles, sensitivity, prompts = context
    schedule = query_schedule(protocol, fixtures, sensitivity)
    if len(schedule) != protocol['inference']['expected_query_count']:
        raise ValueError('unexpected schedule size')
    contract = dict(protocol_digest=digest, provider=provider, cluster_compute=cluster_compute,
                    schedule_sha256=digest_json(schedule), source_code_sha256=code_receipt(),
                    action_scoring_version=CONTROLLED_ACTION_SCORING_VERSION)
    if provider == 'local':
        canonical = ROOT / 'results' / 'controlled_h_v2_confirmatory_qwen3_32b.json'
        if output.resolve() != canonical.resolve():
            raise ValueError('real inference must use the canonical report path')
        if server_provenance is None:
            raise ValueError('real inference requires a server launch receipt')
        contract['server_provenance'] = server_provenance
    if resolve_pending and not output.exists():
        raise ValueError('no checkpoint exists to resolve')
    if provider == 'local' and not resolve_pending:
        if (getattr(llm, 'model', None) != protocol['inference']['served_model_name']
                or getattr(llm, 'timeout', None) != protocol['transport']['timeout_seconds']
                or getattr(llm, 'max_attempts', None) != 1):
            raise ValueError('client model or transport differs from freeze')
    with exclusive_writer(output):
        if output.exists():
            report = json.loads(output.read_text(encoding='utf-8'))
            if report.get('contract') != contract:
                raise ValueError('checkpoint execution contract changed')
            if (report.get('model') != protocol['inference']
                    or report.get('transport') != protocol['transport']
                    or report.get('expected_queries') != len(schedule)
                    or report.get('protocol_id') != protocol['protocol_id']
                    or report.get('model_inference') != (provider != 'mock')):
                raise ValueError('checkpoint model/protocol metadata differs')
        else:
            if any(row_directory(output).glob('*.json')):
                raise ValueError('orphan row directory without a manifest')
            report = dict(result_schema_version='2.1', run_kind='controlled-h-confirmatory',
                          protocol_id=protocol['protocol_id'], contract=contract,
                          created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                          model_inference=provider != 'mock', model=protocol['inference'],
                          transport=protocol['transport'],
                          initial_git_commit=_git_value('rev-parse', 'HEAD'),
                          runtime_versions={p: _package_version(p) for p in ('vllm', 'transformers', 'numpy')},
                          expected_queries=len(schedule), completed_rows=[], pending=None, complete=False)
        rows = load_rows(report, output, schedule, context)

        def save_row(row):
            index = len(rows)
            path = row_path(output, index)
            if path.exists():
                if json.loads(path.read_text(encoding='utf-8')) != row:
                    raise ValueError('refusing to overwrite an existing response')
            else:
                _atomic_write_json(path, row)
            report['completed_rows'].append(dict(index=index, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            rows.append(row)
            report['pending'] = None
            report['complete'] = len(rows) == len(schedule)
            _atomic_write_json(output, report)

        if report['pending'] is not None:
            index = len(rows)
            if index >= len(schedule) or report['pending'] != schedule[index]:
                raise ValueError('invalid pending query')
            query = schedule[index]
            fid = query['fixture_id']
            path = row_path(output, index)
            if path.exists():
                row = json.loads(path.read_text(encoding='utf-8'))
                validate_row(row, query, prompts[fid], oracles[fid])
                save_row(row)
            elif resolve_pending:
                save_row(make_row(query, prompts[fid], oracles[fid],
                                  {'error': 'ambiguous_query'}, None, None, 'ambiguous_query'))
            else:
                raise ValueError('ambiguous in-flight query; resolve without reinference before resuming')
        if resolve_pending:
            return report
        if phase == 'run' and provider != 'mock':
            if not rows or not rows[0]['score']['legal'] or rows[0]['diagnostics']['truncated']:
                raise ValueError('real one-query smoke did not pass')
        if phase == 'smoke' and rows:
            return report
        if llm is None:
            raise ValueError('missing inference client')
        limit = 1 if phase == 'smoke' else max_new
        added = 0
        for query in schedule[len(rows):]:
            index = query['index']
            if row_path(output, index).exists():
                raise ValueError('unexpected response outside checkpoint')
            fid = query['fixture_id']
            report['pending'] = query
            _atomic_write_json(output, report)
            llm.last_raw_response = None
            llm.last_finish_reason = None
            failure = None
            try:
                parsed = llm.complete_json(*prompts[fid][query['horizon']],
                                           temperature=protocol['inference']['temperature'],
                                           max_tokens=protocol['inference']['max_tokens'])
                raw, finish = llm.last_raw_response, llm.last_finish_reason
            except (RateLimitExhausted, TimeoutError, ConnectionError, OSError):
                parsed, raw, finish, failure = {'error': 'transport_failure'}, None, None, 'transport_failure'
            except RuntimeError as exc:
                if not isinstance(llm, LocalLLM) or not str(exc).startswith('Local server returned HTTP '):
                    raise
                parsed, raw, finish, failure = {'error': 'transport_failure'}, None, None, 'transport_failure'
            row = make_row(query, prompts[fid], oracles[fid], parsed, raw, finish, failure)
            validate_row(row, query, prompts[fid], oracles[fid])
            save_row(row)
            added += 1
            if failure or (limit is not None and added >= limit):
                break
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT/'results')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--provider', choices=('mock', 'local'), default='mock')
    parser.add_argument('--phase', choices=('smoke', 'run'), default='smoke')
    parser.add_argument('--base-url', default='http://localhost:8000/v1')
    parser.add_argument('--server-receipt', type=Path)
    parser.add_argument('--authorize-model-inference', action='store_true')
    parser.add_argument('--cluster-compute', action='store_true')
    parser.add_argument('--resolve-pending-as-failure', action='store_true')
    parser.add_argument('--max-new-queries', type=int)
    args = parser.parse_args()
    p, digest = load_protocol()
    if args.provider == 'local' and not args.authorize_model_inference and not args.resolve_pending_as_failure:
        parser.error('real inference requires --authorize-model-inference')
    protected = [PROTOCOL_PATH] + [(args.source_dir/s['filename'] if s['kind']=='result' else ROOT/s['filename'])
                                  for s in p['sources'].values()]
    if args.out.resolve() in {path.resolve() for path in protected}:
        parser.error('output would overwrite a source')
    context = load_context(p, args.source_dir)
    provenance = None
    if args.provider == 'local':
        if args.server_receipt is None:
            parser.error('local provider requires --server-receipt from the frozen launcher')
        provenance = serving_receipt(p, args.server_receipt, args.base_url)
    if args.resolve_pending_as_failure:
        llm = None
    elif args.provider == 'mock':
        llm = MockLLM(['{"action":"end_turn","card_index":-1,"target_index":-1,"reasoning":"mock"}'])
    else:
        validate_serving_stack(p)
        verify_live_server(provenance)
        llm = LocalLLM(p['inference']['served_model_name'], args.base_url,
                       timeout=p['transport']['timeout_seconds'], max_attempts=1)
    report = run(p, digest, context, args.out, llm, args.provider, args.phase,
                 args.authorize_model_inference, args.max_new_queries,
                 args.cluster_compute, args.resolve_pending_as_failure, provenance)
    print(json.dumps(dict(complete=report['complete'],completed=len(report['completed_rows']),
                         expected=report['expected_queries'],pending=report['pending'] is not None,
                         model_inference=report['model_inference'])))


if __name__ == '__main__':
    main()
