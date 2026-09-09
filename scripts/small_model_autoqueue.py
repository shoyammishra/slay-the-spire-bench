#!/usr/bin/env python
"""Bounded automatic continuation of the separate 48-query development pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import small_model_pilot as pilot
from scripts.controlled_horizon_confirmatory import exclusive_writer
from scripts.controlled_horizon_pilot import _atomic_write_json

STATE = ROOT / 'results/small_model_development/qwen3-8b_autoqueue.json'
STOP = ROOT / 'results/small_model_development/qwen3-8b_autoqueue.stop'
POLICY = 'small-model-autoqueue-2026-09-08'
MAX_JOBS = 5
ACTIVE = {'PENDING', 'RUNNING', 'CONFIGURING', 'COMPLETING', 'SUSPENDED',
          'RESIZING', 'REQUEUED', 'REQUEUE_FED', 'REQUEUE_HOLD'}


def source_hash():
    return hashlib.sha256(Path(__file__).read_text(encoding='utf-8').encode()).hexdigest()


def command(argv):
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                          timeout=60, check=False, close_fds=True)


def accounting(job_id, execute=command):
    result = execute(['sacct', '-n', '-P', '-j', str(job_id),
                      '--format=JobIDRaw,JobName%80,State%30,ExitCode'])
    if result.returncode:
        raise ValueError('Slurm accounting query failed; no successor submitted')
    matches = [line.split('|') for line in result.stdout.splitlines()
               if line.split('|')[0].strip() == str(job_id)]
    if not matches:
        return None
    if len(matches) != 1 or len(matches[0]) < 4:
        raise ValueError('ambiguous Slurm accounting record')
    _, name, state, exit_code, *_ = [x.strip() for x in matches[0]]
    if name != 'slay_small_pilot':
        raise ValueError('observed job is not the development pilot job')
    return state.split()[0], exit_code


def check_preflight(model):
    ctx, queries = pilot.prepare()
    report = pilot.get_report(pilot.output_path(model), model, False, queries, ctx)
    if len(queries) != 48 or not report['rows'] or not pilot.clean(report['rows'][0]['row']):
        raise ValueError('missing or failed development smoke')
    return len(report['rows'])


def decide(index, prior_index, submitted, limit):
    if (not isinstance(index, int) or isinstance(index, bool)
            or not 1 <= index <= 48 or not 1 <= index-prior_index <= 16):
        raise ValueError('completed job must add 1..16 rows within the 48-query pilot')
    if index == 48:
        return 'complete'
    return 'budget_exhausted' if submitted >= limit else 'submit'


def no_other_jobs(execute):
    result = execute(['squeue', '-h', '--name=slay_small_pilot', '--format=%A'])
    if result.returncode or result.stdout.strip():
        raise ValueError('another development job is queued/running, or queue check failed; do not duplicate it')


def submit(state, path, index, execute=command, stop_path=STOP):
    if stop_path.exists():
        state.update(phase='stopped', reason='operator stop file')
        _atomic_write_json(path, state)
        return
    # A durable marker precedes the non-idempotent scheduler operation.
    no_other_jobs(execute)
    state.update(phase='submit_pending', before_index=index,
                 submission_tag=f"{state['chain_id']}-{len(state['submitted_jobs']) + 1}")
    _atomic_write_json(path, state)
    result = execute([
        'sbatch', '--parsable', '--no-requeue',
        f"--export=PILOT_MODEL={state['model']},PILOT_MAX_NEW={min(16,48-index)},CONDA_SH,CONDA_ENV,HF_HOME,HOME,PATH",
        '--comment=' + state['submission_tag'],
        'cluster/csis_small_model_pilot.sbatch'])
    match = re.fullmatch(r'([1-9][0-9]*)(?:;[^\s;]+)?', result.stdout.strip())
    if result.returncode or match is None:
        raise ValueError('submission outcome is unconfirmed; retain submit_pending and reconcile manually')
    job_id = int(match.group(1))
    if job_id == state['after_job'] or job_id in state['submitted_jobs']:
        raise ValueError('scheduler returned an already recorded job ID')
    state['submitted_jobs'].append(job_id)
    state.update(phase='waiting', current_job=job_id, reason=None)
    _atomic_write_json(path, state)
    print(json.dumps({'submitted_job': job_id, 'completed': index,
                      'new_jobs': len(state['submitted_jobs']), 'max_jobs': state['max_jobs']}), flush=True)


def run(after_job, max_jobs, after_index, model='qwen3-8b', *, path=STATE, stop_path=STOP, execute=command,
        sleep=time.sleep, preflight=check_preflight):
    contract = dict(policy=POLICY, source_sha256=source_hash(), pilot_contract=pilot.contract(model, False), model=model,
                    after_job=after_job, max_jobs=max_jobs, after_index=after_index,
                    report=str(pilot.output_path(model).relative_to(ROOT)))
    with exclusive_writer(path):
        if path.exists():
            state = json.loads(path.read_text(encoding='utf-8'))
            if any(state.get(k) != v for k, v in contract.items()):
                raise ValueError('autoqueue contract changed; preserve state and review')
        else:
            state = dict(contract, chain_id=uuid.uuid4().hex, phase='waiting',
                         current_job=after_job, submitted_jobs=[], before_index=after_index,
                         reason=None)
            _atomic_write_json(path, state)
        if state['phase'] == 'submit_pending':
            raise ValueError('ambiguous earlier submission; do not resubmit or delete the state')
        if state['phase'] != 'waiting':
            print(json.dumps({'phase': state['phase'], 'reason': state.get('reason')}), flush=True)
            return state
        print(json.dumps({'watching_job': state['current_job'], 'phase': 'waiting',
                          'submitted_jobs': len(state['submitted_jobs']), 'max_jobs': max_jobs}), flush=True)
        missing_since = None
        while True:
            if stop_path.exists():
                state.update(phase='stopped', reason='operator stop file')
                _atomic_write_json(path, state)
                return state
            if source_hash() != contract['source_sha256']:
                raise ValueError('autoqueue source changed while running')
            if pilot.contract(model, False) != contract['pilot_contract']:
                raise ValueError('development runner/config/launcher changed')
            job = accounting(state['current_job'], execute)
            if job is None:
                missing_since = time.monotonic() if missing_since is None else missing_since
                if time.monotonic() - missing_since > 600:
                    raise ValueError('job absent from accounting for ten minutes; stopping')
                sleep(30)
                continue
            missing_since = None
            job_state, exit_code = job
            if job_state in ACTIVE:
                sleep(30)
                continue
            if job_state != 'COMPLETED' or exit_code != '0:0':
                state.update(phase='stopped', reason=f'job {state["current_job"]}: {job_state} {exit_code}')
                _atomic_write_json(path, state)
                print(json.dumps({'phase': state['phase'], 'reason': state['reason']}), flush=True)
                return state
            index = preflight(model)
            action = decide(index, state['before_index'], len(state['submitted_jobs']), max_jobs)
            print(json.dumps({'checked_job': state['current_job'], 'completed': index,
                              'decision': action}), flush=True)
            if action != 'submit':
                state.update(phase=action, reason=action)
                _atomic_write_json(path, state)
                return state
            submit(state, path, index, execute, stop_path)
            if state['phase'] != 'waiting':
                return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--after-job', type=int, required=True)
    parser.add_argument('--max-jobs', type=int, required=True)
    parser.add_argument('--after-index', type=int, required=True)
    parser.add_argument('--model', choices=tuple(pilot.spec()['models']), default='qwen3-8b')
    parser.add_argument('--authorize-submit', action='store_true')
    args = parser.parse_args()
    if not args.authorize_submit:
        parser.error('automatic cluster submissions require --authorize-submit')
    if args.after_job < 1 or not 1 <= args.max_jobs <= MAX_JOBS:
        parser.error('positive job ID and max-jobs between 1 and 5 required')
    if not 0 <= args.after_index < 48:
        parser.error('after-index is the saved count BEFORE the watched job: 0 for initial smoke')
    if sys.platform == 'win32':
        parser.error('run the supervisor on the CSIS login node, not Windows')
    os.chdir(ROOT)
    try:
        run(args.after_job, args.max_jobs, args.after_index, args.model,
            path=ROOT/f'results/small_model_development/{args.model}_autoqueue.json',
            stop_path=ROOT/f'results/small_model_development/{args.model}_autoqueue.stop')
    except Exception as exc:
        print(f'AUTOQUEUE STOPPED: {exc}', file=sys.stderr, flush=True)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
