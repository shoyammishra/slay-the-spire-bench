#!/usr/bin/env python
"""Model-free v3 held-out fixture generation and sharded exact-oracle audit.

Stages: manifest -> shard (one per Slurm array task) -> merge -> release.
Reuses the audited v2 generation, oracle and release-selection functions; only the
protocol (fresh disjoint seeds, node-budget exactness, DiD-sized quotas) is new.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import datetime as dt
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.controlled_horizon_expansion import fingerprint, read_stage, run_stage
from scripts.controlled_horizon_funnel import _file_sha256
from scripts.controlled_horizon_pilot import (
    _atomic_write_json, generate_frozen_candidates, load_frozen_protocol,
    select_frozen_release,
)
from slay_bench.controlled_horizon import ControlledFixture

PROTOCOL_PATH = ROOT / 'configs/controlled_h_v3_heldout.json'
FROZEN_DIGEST = 'dbcbc03bb38b7a27a0a80011db2365b0fa544da1878c9b13422dadb82262aff7'


def load_protocol(path=PROTOCOL_PATH):
    protocol, digest = load_frozen_protocol(path)
    if FROZEN_DIGEST is not None and digest != FROZEN_DIGEST:
        raise ValueError('v3 protocol differs from the registered freeze')
    return protocol, digest


def prior_identities(protocol, source_dir):
    """Seeds, fixture IDs and state digests of every earlier controlled-H fixture."""
    seeds, ids, digests = set(), set(), set()
    for key, spec in protocol['prior_fixture_sources'].items():
        path = source_dir / spec['filename']
        if _file_sha256(path) != spec['sha256']:
            raise ValueError(f'{key} prior source hash differs from the protocol')
        for row in json.loads(path.read_text(encoding='utf-8'))['rows']:
            f = row['fixture']
            seeds.add(f['seed']); ids.add(f['fixture_id']); digests.add(f['state_digest'])
    return seeds, ids, digests


def build_manifest(protocol, digest, source_dir):
    fixtures, attempts = generate_frozen_candidates(protocol)
    seeds, ids, digests = prior_identities(protocol, source_dir)
    new_seeds = [a['seed'] for a in attempts]
    new_ids = [f.fixture_id for f in fixtures]
    new_digests = [f.state_digest for f in fixtures]
    for name, new, old in (('seeds', new_seeds, seeds), ('fixture IDs', new_ids, ids),
                           ('state digests', new_digests, digests)):
        if len(set(new)) != len(new) or old.intersection(new):
            raise ValueError(f'candidate {name} overlap earlier fixtures or each other')
    return dict(result_schema_version='2.0', run_kind='controlled-h-v3-manifest',
                protocol_id=protocol['protocol_id'], protocol_digest=digest,
                created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                generated=len(fixtures), attempted=len(attempts),
                generation_failures=sum(not a['generated'] for a in attempts),
                attempts=attempts, fixtures=[asdict(f) for f in fixtures])


def load_manifest(path, digest):
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('protocol_digest') != digest:
        raise ValueError('manifest was built under a different protocol')
    fixtures = [ControlledFixture.from_dict(f) for f in manifest['fixtures']]
    return manifest, sorted(fixtures, key=lambda f: f.fixture_id)


def shard_fixtures(fixtures, shard, shards):
    if not 0 <= shard < shards:
        raise ValueError('shard index out of range')
    return fixtures[shard::shards]


def shard_binding(manifest_path, shard, shards):
    return dict(manifest_sha256=_file_sha256(manifest_path), shard=shard, shards=shards)


def merge_shards(protocol, digest, manifest_path, fixtures, shard_paths, shards):
    spec = protocol['full_oracle']
    if len(shard_paths) != shards:
        raise ValueError('expected exactly one checkpoint per shard')
    rows = []
    for shard, path in enumerate(shard_paths):
        report = read_stage(path, digest, 'full', shard_fixtures(fixtures, shard, shards),
                            tuple(spec['horizons']), spec['node_budget_per_fixture_h'],
                            spec['wall_seconds_per_fixture_h'],
                            shard_binding(manifest_path, shard, shards), require_complete=True)
        rows.extend(report['rows'])
    ids = [r['fixture']['fixture_id'] for r in rows]
    if sorted(ids) != [f.fixture_id for f in fixtures]:
        raise ValueError('merged shards do not cover the manifest exactly once')
    return sorted(rows, key=lambda r: r['fixture']['fixture_id'])


def failure_summary(rows):
    out = {}
    for row in rows:
        err = row.get('error')
        key = 'exact' if err is None else err.get('type', 'error')
        char = row['fixture']['character']
        out.setdefault(char, {}).setdefault(key, 0)
        out[char][key] += 1
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('manifest', 'shard', 'merge', 'release'))
    parser.add_argument('--protocol', type=Path, default=PROTOCOL_PATH)
    parser.add_argument('--source-dir', type=Path, default=ROOT/'results')
    parser.add_argument('--manifest', type=Path, default=ROOT/'results/controlled_h_v3_manifest.json')
    parser.add_argument('--shard', type=int)
    parser.add_argument('--shards', type=int)
    parser.add_argument('--shard-dir', type=Path, default=ROOT/'results/controlled_h_v3_shards')
    parser.add_argument('--full', type=Path, default=ROOT/'results/controlled_h_v3_full.json')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--max-new-fixtures', type=int)
    args = parser.parse_args()
    protocol, digest = load_protocol(args.protocol)

    if args.stage == 'manifest':
        if args.manifest.exists():
            raise ValueError('manifest exists; never regenerate over it')
        manifest = build_manifest(protocol, digest, args.source_dir)
        _atomic_write_json(args.manifest, manifest)
        print(json.dumps({k: manifest[k] for k in ('generated', 'attempted', 'generation_failures')}))
        return

    manifest, fixtures = load_manifest(args.manifest, digest)
    if args.stage == 'shard':
        if args.shard is None or not args.shards:
            parser.error('shard requires --shard and --shards')
        args.shard_dir.mkdir(parents=True, exist_ok=True)
        output = args.shard_dir / f'shard_{args.shard:04d}_of_{args.shards:04d}.json'
        report = run_stage(protocol, digest, 'full', shard_fixtures(fixtures, args.shard, args.shards),
                           protocol['full_oracle'], output,
                           shard_binding(args.manifest, args.shard, args.shards),
                           max_new=args.max_new_fixtures)
        print(json.dumps({'shard': args.shard, 'completed': report['completed_fixture_rows'],
                          'requested': report['requested_fixture_rows'], 'complete': report['complete']}))
        return

    if args.stage == 'merge':
        if not args.shards:
            parser.error('merge requires --shards')
        paths = [args.shard_dir / f'shard_{i:04d}_of_{args.shards:04d}.json' for i in range(args.shards)]
        rows = merge_shards(protocol, digest, args.manifest, fixtures, paths, args.shards)
        report = dict(result_schema_version='2.0', run_kind='controlled-h-v3-full-merged',
                      protocol_id=protocol['protocol_id'], protocol_digest=digest, stage='full',
                      manifest_sha256=_file_sha256(args.manifest), shards=args.shards,
                      created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                      completed_fixture_rows=len(rows), complete=True,
                      failures=failure_summary(rows), rows=rows)
        _atomic_write_json(args.full, report)
        print(json.dumps({'rows': len(rows), 'failures': report['failures']}))
        return

    full = json.loads(args.full.read_text(encoding='utf-8'))
    if full.get('protocol_digest') != digest or full.get('manifest_sha256') != _file_sha256(args.manifest):
        raise ValueError('merged audit does not belong to this protocol/manifest')
    selection = select_frozen_release(full['rows'], protocol)
    selected = set(selection['selected_fixture_ids'])
    fixtures_out = sorted((r['fixture'] for r in full['rows'] if r['fixture']['fixture_id'] in selected),
                          key=lambda f: f['fixture_id'])
    out = args.out or ROOT/'results/controlled_h_v3_release_fixtures.json'
    _atomic_write_json(out.with_name(out.stem + '_audit.json'),
                       dict(protocol_id=protocol['protocol_id'], protocol_digest=digest,
                            full_sha256=_file_sha256(args.full), selection=selection,
                            released_fixture_count=len(fixtures_out)))
    _atomic_write_json(out, fixtures_out)
    print(json.dumps({'released': len(fixtures_out), 'release_gate_passed': selection.get('release_gate_passed'),
                      'shortfalls': selection.get('shortfalls')}))


if __name__ == '__main__':
    main()
