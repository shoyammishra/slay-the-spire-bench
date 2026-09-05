#!/usr/bin/env python
"""Model-free, source-bound follow-up fixture expansion after the pilot STOP."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.controlled_horizon_funnel import _base_report, _file_sha256
from scripts.controlled_horizon_pilot import (
    _atomic_write_json, audit_fixture, generate_frozen_candidates,
    load_frozen_protocol, select_frozen_advancements, select_frozen_release,
)
from slay_bench.controlled_horizon import ControlledFixture

PROTOCOL_PATH = ROOT / 'configs/controlled_h_v2_expansion.json'
FROZEN_DIGEST = 'bfe8c1306661fb28eb336ec0e3306e4cee11dd47e0f6d2c16c4be83cd7f1288b'


def load_protocol(path=PROTOCOL_PATH):
    protocol, digest = load_frozen_protocol(path)
    if digest != FROZEN_DIGEST:
        raise ValueError('expansion protocol differs from the registered freeze')
    return protocol, digest


def fingerprint(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_sources(protocol, directory):
    sources = {}
    for key, spec in protocol['sources'].items():
        path = directory / spec['filename']
        if _file_sha256(path) != spec['sha256']:
            raise ValueError(f'{key} source hash differs from the freeze')
        sources[key] = json.loads(path.read_text(encoding='utf-8'))
    return sources


def inventory(protocol, sources):
    """Retain only registered old eligibility and untouched screen candidates."""
    pilot_ids = set(sources['pilot']['selection']['selected_fixture_ids'])
    old = sources['base_full']['rows'] + sources['extension_full']['rows']
    old_by_id = {r['fixture']['fixture_id']: r for r in old}
    if len(old_by_id) != len(old):
        raise ValueError('old full sources overlap')
    allowed = {d['fixture_id'] for d in
               sources['combined_audit']['selection']['dispositions']
               if d['eligible']} - pilot_ids
    reused = [old_by_id[fid] for fid in sorted(allowed)]
    base_protocol, base_digest = load_frozen_protocol()
    if base_digest != sources['base_screen']['protocol_digest']:
        raise ValueError('base selection protocol differs from source provenance')
    advancement = select_frozen_advancements(
        sources['base_screen']['rows'], base_protocol)
    remaining = {d['fixture_id'] for d in advancement['decisions']
                 if d['reason'] == 'screen_insensitive_rank_pool'
                 and d['fixture_id'] not in old_by_id
                 and d['fixture_id'] not in pilot_ids}
    recipes = {r['fixture']['fixture_id']: r['fixture']
               for r in sources['base_screen']['rows']}
    remaining_fixtures = [ControlledFixture.from_dict(recipes[fid])
                          for fid in sorted(remaining)]
    for char, count in protocol['expansion']['remaining_counts'].items():
        if sum(f.character == char for f in remaining_fixtures) != count:
            raise ValueError('remaining old pool count differs from the freeze')
    fresh, attempts = generate_frozen_candidates(protocol)
    ids = [f.fixture_id for f in fresh]
    old_seeds = {r['fixture']['seed'] for r in sources['base_screen']['rows']}
    fresh_seeds = [a['seed'] for a in attempts]
    if len(set(fresh_seeds)) != len(fresh_seeds) or old_seeds.intersection(fresh_seeds):
        raise ValueError('candidate seeds overlap')
    if len(ids) != len(set(ids)) or set(ids).intersection(recipes):
        raise ValueError('candidate fixture IDs overlap')
    digests = [f.state_digest for f in fresh] + [r['state_digest'] for r in recipes.values()]
    if len(digests) != len(set(digests)):
        raise ValueError('candidate state digests overlap')
    return fresh, attempts, remaining_fixtures, reused, pilot_ids


def read_stage(path, digest, stage, fixtures, horizons, node_budget, wall_seconds, binding,
               require_complete=False):
    report = json.loads(path.read_text(encoding='utf-8'))
    expected = {f.fixture_id: asdict(f) for f in fixtures}
    metadata = dict(protocol_digest=digest, stage=stage, horizons=list(horizons),
                    node_budget_per_fixture_h=node_budget,
                    wall_seconds_per_fixture_h=wall_seconds,
                    requested_fixture_rows=len(fixtures), binding=binding)
    if any(report.get(k) != v for k, v in metadata.items()):
        raise ValueError('checkpoint contract differs from selected stage')
    rows = report.get('rows', [])
    ids = [r['fixture']['fixture_id'] for r in rows]
    if len(ids) != len(set(ids)) or not set(ids).issubset(expected):
        raise ValueError('checkpoint contains duplicate or foreign fixtures')
    if any(r['fixture'] != expected[r['fixture']['fixture_id']] for r in rows):
        raise ValueError('checkpoint fixture recipe differs')
    if report.get('completed_fixture_rows') != len(rows):
        raise ValueError('checkpoint count differs from rows')
    complete = set(ids) == set(expected)
    if report.get('complete') != complete or (require_complete and not complete):
        raise ValueError('checkpoint completion is inconsistent or incomplete')
    return report


def run_stage(protocol, digest, stage, fixtures, spec, output, binding,
              max_new=None, audit_fn=None):
    """Checkpoint each disposition; rejected/budget-failed rows are never retried."""
    if max_new is not None and max_new < 1:
        raise ValueError('max-new-fixtures must be positive')
    if len({f.fixture_id for f in fixtures}) != len(fixtures):
        raise ValueError('duplicate selected fixtures')
    audit_fn = audit_fixture if audit_fn is None else audit_fn
    horizons = tuple(spec['horizons'])
    node_budget, wall = spec['node_budget_per_fixture_h'], spec['wall_seconds_per_fixture_h']
    prior = (read_stage(output, digest, stage, fixtures, horizons, node_budget, wall,
                        binding) if output.exists() else {})
    created = prior.get('created_at_utc', dt.datetime.now(dt.timezone.utc).isoformat())
    rows = list(prior.get('rows', []))
    completed = {r['fixture']['fixture_id'] for r in rows}
    def report():
        return dict(_base_report(protocol, digest, stage, created),
                    run_kind='controlled-h-model-free-expansion',
                    horizons=list(horizons), node_budget_per_fixture_h=node_budget,
                    wall_seconds_per_fixture_h=wall, requested_fixture_rows=len(fixtures),
                    completed_fixture_rows=len(rows), complete=len(rows)==len(fixtures),
                    binding=binding, rows=rows)
    added = 0
    for fixture in fixtures:
        if fixture.fixture_id in completed:
            continue
        print(f'{stage}: {fixture.fixture_id}', file=sys.stderr, flush=True)
        row = audit_fn(fixture, horizons, node_budget, wall)
        if row.get('fixture') != asdict(fixture):
            raise ValueError('audit returned a different fixture')
        rows.append(row)
        _atomic_write_json(output, report())
        added += 1
        if max_new is not None and added >= max_new:
            break
    final = report()
    _atomic_write_json(output, final)
    return final


def select_release(protocol, reused, audited, pilot_ids):
    rows = reused + audited
    ids = [r['fixture']['fixture_id'] for r in rows]
    if len(ids) != len(set(ids)) or set(ids).intersection(pilot_ids):
        raise ValueError('release source overlap or pilot fixture leakage')
    digests = [r['fixture']['state_digest'] for r in rows]
    if len(digests) != len(set(digests)):
        raise ValueError('release state digests overlap')
    selection = select_frozen_release(rows, protocol)
    selected = set(selection['selected_fixture_ids'])
    payload = [r['fixture'] for r in rows if r['fixture']['fixture_id'] in selected]
    return selection, sorted(payload, key=lambda f:f['fixture_id'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('manifest','screen','full','release'))
    parser.add_argument('--protocol', type=Path, default=PROTOCOL_PATH)
    parser.add_argument('--source-dir', type=Path, default=ROOT/'results')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--screen-audit', type=Path)
    parser.add_argument('--full-audit', type=Path)
    parser.add_argument('--fixtures-out', type=Path)
    parser.add_argument('--max-new-fixtures', type=int)
    args = parser.parse_args()
    protocol, digest = load_protocol(args.protocol)
    inputs = [args.protocol] + [args.source_dir/s['filename'] for s in protocol['sources'].values()]
    inputs += [p for p in (args.screen_audit,args.full_audit) if p is not None]
    outputs = [p for p in (args.out,args.fixtures_out) if p is not None]
    if len({p.resolve() for p in outputs}) != len(outputs) or any(
            out.resolve() == inp.resolve() for out in outputs for inp in inputs):
        parser.error('outputs must be distinct from each other and all sources')
    if args.stage in ('full','release') and args.screen_audit is None:
        parser.error('full/release requires --screen-audit')
    if args.stage == 'release' and (args.full_audit is None or args.fixtures_out is None):
        parser.error('release requires --full-audit and --fixtures-out')
    if args.max_new_fixtures is not None and args.stage not in ('screen','full'):
        parser.error('max-new-fixtures is only valid for screen/full')
    sources = load_sources(protocol, args.source_dir)
    fresh, attempts, remaining, reused, pilot_ids = inventory(protocol, sources)
    binding = dict(sources=protocol['sources'], generation_attempts=attempts,
                   selected_recipe_sha256=fingerprint([asdict(f) for f in fresh]))
    if args.stage == 'manifest':
        report = dict(_base_report(protocol,digest,'manifest',dt.datetime.now(dt.timezone.utc).isoformat()),
            fresh_candidate_attempts=attempts, fresh_fixtures=[asdict(f) for f in fresh],
            remaining_old_fixtures=[asdict(f) for f in remaining],
            reused_fixture_ids=[r['fixture']['fixture_id'] for r in reused],
            excluded_pilot_fixture_ids=sorted(pilot_ids),
            source_hashes=protocol['sources'])
        if args.out.exists():
            previous=json.loads(args.out.read_text(encoding='utf-8'))
            stable={k:v for k,v in report.items() if k not in ('provenance','created_at_utc')}
            if any(previous.get(k)!=v for k,v in stable.items()):
                raise ValueError('existing manifest differs from freeze')
        _atomic_write_json(args.out,report)
    elif args.stage == 'screen':
        report=run_stage(protocol,digest,'screen',fresh,protocol['screen'],args.out,
                         binding,args.max_new_fixtures)
    else:
        spec=protocol['screen']
        screen=read_stage(args.screen_audit,digest,'screen',fresh,spec['horizons'],
            spec['node_budget_per_fixture_h'],spec['wall_seconds_per_fixture_h'],binding,True)
        advanced=select_frozen_advancements(screen['rows'],protocol)
        ids=set(advanced['selected_fixture_ids'])
        full_fixtures=sorted(remaining+[f for f in fresh if f.fixture_id in ids],key=lambda f:f.fixture_id)
        full_binding=dict(sources=protocol['sources'], screen_sha256=_file_sha256(args.screen_audit),
            advancement=advanced, selected_recipe_sha256=fingerprint([asdict(f) for f in full_fixtures]))
        if args.stage == 'full':
            report=run_stage(protocol,digest,'full',full_fixtures,protocol['full_oracle'],
                             args.out,full_binding,args.max_new_fixtures)
        else:
            spec=protocol['full_oracle']
            full=read_stage(args.full_audit,digest,'full',full_fixtures,spec['horizons'],
                spec['node_budget_per_fixture_h'],spec['wall_seconds_per_fixture_h'],full_binding,True)
            selection,payload=select_release(protocol,reused,full['rows'],pilot_ids)
            report=dict(_base_report(protocol,digest,'release',dt.datetime.now(dt.timezone.utc).isoformat()),
                source_hashes=protocol['sources'], full_artifact_sha256=_file_sha256(args.full_audit),
                original_pilot_gate_passed=False, release_gate_passed=selection['release_gate_passed'],
                selection=selection,released_fixture_count=len(payload),
                source_counts=dict(reused=len(reused),newly_audited=len(full['rows'])),
                model_inference_authorized=False)
            _atomic_write_json(args.out,report)
            _atomic_write_json(args.fixtures_out,dict(report,stage='release-fixtures',fixtures=payload))
    print(json.dumps({k:report.get(k) for k in ('stage','protocol_digest','complete','completed_fixture_rows','release_gate_passed','released_fixture_count')},sort_keys=True))


if __name__ == '__main__':
    main()
