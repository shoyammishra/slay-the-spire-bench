"""v3 held-out fixture pipeline: disjoint generation, sharding, merge coverage (mock oracle)."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import controlled_horizon_v3 as v3
from scripts.controlled_horizon_expansion import run_stage
from scripts.controlled_horizon_pilot import _atomic_write_json


def _small_protocol(n=6):
    protocol, _ = v3.load_protocol()
    protocol = json.loads(json.dumps(protocol))
    protocol['candidate_generation']['candidates_per_character'] = n
    digest = v3.fingerprint(protocol)
    return protocol, digest


def _mock_audit(fixture, horizons, node_budget, wall):
    return dict(fixture=asdict(fixture), error=None, oracles={}, prompt_only_h_changes=True)


def test_shards_partition_and_merge_roundtrip():
    protocol, digest = _small_protocol()
    manifest = v3.build_manifest(protocol, digest, ROOT / 'results')
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        mpath = tmp / 'manifest.json'
        _atomic_write_json(mpath, manifest)
        _, fixtures = v3.load_manifest(mpath, digest)
        shards = 5
        parts = [v3.shard_fixtures(fixtures, i, shards) for i in range(shards)]
        ids = sorted(f.fixture_id for p in parts for f in p)
        assert ids == [f.fixture_id for f in fixtures], 'shards must partition the manifest'
        paths = []
        for i, part in enumerate(parts):
            path = tmp / f'shard_{i}.json'
            run_stage(protocol, digest, 'full', part, protocol['full_oracle'], path,
                      v3.shard_binding(mpath, i, shards), audit_fn=_mock_audit)
            paths.append(path)
        rows = v3.merge_shards(protocol, digest, mpath, fixtures, paths, shards)
        assert [r['fixture']['fixture_id'] for r in rows] == [f.fixture_id for f in fixtures]
        # A shard missing one row must fail closed.
        broken = json.loads(paths[0].read_text(encoding='utf-8'))
        broken['rows'] = broken['rows'][:-1]
        broken['completed_fixture_rows'] -= 1
        broken['complete'] = False
        paths[0].write_text(json.dumps(broken), encoding='utf-8')
        try:
            v3.merge_shards(protocol, digest, mpath, fixtures, paths, shards)
        except ValueError:
            pass
        else:
            raise AssertionError('incomplete shard was merged')


def test_manifest_rejects_overlap_with_prior_fixtures():
    protocol, digest = _small_protocol(2)
    protocol['candidate_generation']['seed_base'] = 9050000  # the v2 expansion's base
    try:
        v3.build_manifest(protocol, digest, ROOT / 'results')
    except ValueError:
        return
    raise AssertionError('overlapping seeds were accepted')


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('PASS', name)
