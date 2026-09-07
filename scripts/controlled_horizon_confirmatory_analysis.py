#!/usr/bin/env python
"""Predeclared all-fixture analysis for the controlled-H confirmation."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.controlled_horizon_confirmatory import (
    load_protocol, load_context, load_rows, query_schedule, digest_json, code_receipt,
)
from scripts.controlled_horizon_model_pilot import load_pilot_protocol
from scripts.controlled_horizon_power import analyze_pilot, required_n, normal_approx_power
from scripts.controlled_horizon_pilot import _atomic_write_json


def nearest_rank(values, probability):
    return values[min(len(values)-1, max(0, math.ceil(len(values)*probability)-1))]


def stratified_bootstrap(sensitive, controls, replicates, seed, alpha=.025):
    """Basic CI and centered-null bootstrap; no within-stratum null centering."""
    if min(len(sensitive), len(controls)) < 2 or replicates < 1 or not 0 < alpha < 1:
        raise ValueError('invalid bootstrap sample/design')
    if any(not math.isfinite(x) for x in sensitive+controls):
        raise ValueError('nonfinite paired difference')
    observed = .25*statistics.fmean(sensitive)+.75*statistics.fmean(controls)
    rng = random.Random(seed)
    errors = []
    extreme = 0
    for _ in range(replicates):
        estimate = (.25*statistics.fmean(rng.choices(sensitive, k=len(sensitive)))
                    + .75*statistics.fmean(rng.choices(controls, k=len(controls))))
        error = estimate-observed
        errors.append(error)
        extreme += abs(error) >= abs(observed)
    errors.sort()
    return dict(mean_h8_minus_h1=observed,
                basic_ci_low=observed-nearest_rank(errors, 1-alpha/2),
                basic_ci_high=observed-nearest_rank(errors, alpha/2),
                confidence_level=1-alpha, p_two_sided=(1+extreme)/(replicates+1),
                bootstrap_mean_sd=statistics.stdev(errors) if len(errors)>1 else 0.,
                bootstrap_replicates=replicates, bootstrap_seed=seed,
                sensitive_n=len(sensitive), control_n=len(controls))


def planning_power(protocol, source_dir):
    source = protocol['sources']['pilot']
    path = source_dir/source['filename']
    if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
        raise ValueError('pilot source hash mismatch')
    pp, _ = load_pilot_protocol()
    if digest_json(pp) != protocol['sources']['pilot_protocol']['sha256']:
        raise ValueError('pilot protocol mismatch')
    result = analyze_pilot(json.loads(path.read_text(encoding='utf-8')), pp)
    rows = {}
    spec = protocol['power']
    for char in protocol['release']['characters']:
        sd = result['by_character'][char]['bootstrap_95pct_upper_sd']
        if not math.isclose(sd, spec['pilot_upper_sd'][char], abs_tol=1e-12):
            raise ValueError('pilot SD does not reproduce')
        n = required_n(spec['minimum_absolute_effect'], sd,
                       spec['two_sided_alpha_per_character'], spec['target_marginal_power'])
        if n != spec['required_n_per_character'][char]:
            raise ValueError('registered power arithmetic differs')
        rows[char] = dict(required_n=n, available=spec['planned_n_per_character'],
                          normal_approx_power=normal_approx_power(
                              spec['minimum_absolute_effect'], sd,
                              spec['planned_n_per_character'], spec['two_sided_alpha_per_character']),
                          planning_gate_passed=n <= spec['planned_n_per_character'])
    return dict(by_character=rows, planning_gate_passed=all(x['planning_gate_passed'] for x in rows.values()),
                limitation=spec['method'], model_execution_authorized=False)


def summarize_rows(rows, protocol):
    by_character = {}
    for char in protocol['release']['characters']:
        subset = [r for r in rows if r['character'] == char]
        def rates(items):
            n = len(items)
            return dict(n=n, parse_rate=sum(r['score']['parse_ok'] for r in items)/n if n else None,
                        mean_effective_quality=statistics.fmean(r['effective_quality'] for r in items) if n else None,
                        legal_rate=sum(r['score']['legal'] for r in items)/n if n else None)
        by_character[char] = dict(rates(subset), by_horizon={
            str(h): rates([r for r in subset if r['horizon'] == h])
            for h in protocol['inference']['horizons']})
    return dict(by_character=by_character, truncations=sum(r['diagnostics']['truncated'] for r in rows),
                execution_failures=sum(r['diagnostics']['execution_failure'] is not None for r in rows))


def analyze_rows(rows, protocol, real_evidence):
    spec, gates = protocol['analysis'], protocol['validity_gates']
    summary = summarize_rows(rows, protocol)
    by_character = {}
    complete = len(rows) == protocol['inference']['expected_query_count']
    keys = [(r['fixture_id'],r['horizon']) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate query in analysis')
    all_integrity = complete and real_evidence
    alpha = spec['two_sided_alpha_per_character']
    for char in protocol['release']['characters']:
        subset = [r for r in rows if r['character'] == char]
        paired = collections.defaultdict(dict)
        for r in subset:
            paired[r['fixture_id']][r['horizon']] = r
        result = dict(n_fixtures=len(paired), inference_available=False)
        if complete:
            sensitive, controls, slopes = [], [], []
            for fid, horizons in paired.items():
                if set(horizons) != set(protocol['inference']['horizons']):
                    raise ValueError('missing or unexpected fixture horizon')
                tags = {r['h1_h8_sensitive'] for r in horizons.values()}
                if len(tags) != 1:
                    raise ValueError('inconsistent fixture sensitivity')
                qualities = [horizons[h]['effective_quality'] for h in (1,2,4,8)]
                if any(not math.isfinite(q) or not 0 <= q <= 1 for q in qualities):
                    raise ValueError('invalid effective quality')
                difference = qualities[-1]-qualities[0]
                (sensitive if tags.pop() else controls).append(difference)
                slopes.append(sum((i-1.5)*q for i,q in enumerate(qualities))/5)
            if (len(sensitive),len(controls)) != (
                    protocol['release']['sensitive_per_character'],protocol['release']['control_per_character']):
                raise ValueError('analysis strata mismatch')
            result.update(stratified_bootstrap(sensitive,controls,spec['bootstrap_replicates'],
                                               spec['bootstrap_seed_by_character'][char],alpha))
            sd = statistics.stdev(sensitive+controls)
            result.update(paired_sd=sd, exploratory_mean_log2h_slope=statistics.fmean(slopes),
                          exploratory_strata={name:dict(n=len(values),mean=statistics.fmean(values),sd=statistics.stdev(values))
                                              for name,values in (('sensitive',sensitive),('control',controls))},
                          boundary_audit_required=(sd <= gates['near_zero_paired_sd']
                                                   or result['bootstrap_mean_sd'] <= gates['near_zero_paired_sd']
                                                   or any(c['mean_effective_quality'] in (0., 1.)
                                                          for c in summary['by_character'][char]['by_horizon'].values())))
            cell = summary['by_character'][char]
            interface = (cell['parse_rate'] >= gates['minimum_parse_rate_per_character']
                         and cell['legal_rate'] >= gates['minimum_legal_rate_per_character']
                         and all(x['parse_rate'] >= gates['minimum_parse_rate_per_character_horizon']
                                 and x['legal_rate'] >= gates['minimum_legal_rate_per_character_horizon']
                                 for x in cell['by_horizon'].values())
                         and summary['truncations']/len(rows) <= gates['maximum_truncation_rate']
                         and summary['execution_failures'] <= gates['maximum_execution_failures'])
            result.update(interface_gate_passed=interface)
            all_integrity = all_integrity and interface and not result['boundary_audit_required']
        by_character[char] = result
    for result in by_character.values():
        result['inference_available'] = all_integrity
        result['reject_primary_null'] = bool(all_integrity and result['p_two_sided'] < alpha)
        result['interpretation'] = ('non-confirmatory' if not all_integrity else
                                    'inconclusive' if not result['reject_primary_null'] else
                                    'degradation' if result['mean_h8_minus_h1'] < 0 else 'benefit')
        effect = protocol['power']['minimum_absolute_effect']
        result['ci_supports_degradation_at_least_planning_effect'] = bool(
            all_integrity and result['basic_ci_high'] <= -effect)
        result['ci_supports_benefit_at_least_planning_effect'] = bool(
            all_integrity and result['basic_ci_low'] >= effect)
    return dict(complete=complete, valid_for_primary_inference=all_integrity,
                rejected_primary_nulls=sum(r['reject_primary_null'] for r in by_character.values()),
                primary_test_count=2, by_character=by_character, interface_summary=summary,
                model_execution_authorized=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,default=ROOT/'results')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    p,digest = load_protocol()
    protected=[args.source_dir/s['filename'] if s['kind']=='result' else ROOT/s['filename'] for s in p['sources'].values()]
    if args.report is not None:
        protected.append(args.report)
    if args.out.resolve() in {x.resolve() for x in protected}:
        parser.error('analysis output must not overwrite a source')
    context = load_context(p,args.source_dir)
    output=dict(protocol_id=p['protocol_id'],protocol_digest=digest,planning=planning_power(p,args.source_dir),
                model_inference=False,analysis=None)
    if args.report is not None:
        report=json.loads(args.report.read_text(encoding='utf-8'))
        schedule=query_schedule(p,context[0],context[2])
        contract=report['contract']
        if (contract['protocol_digest']!=digest or contract['schedule_sha256']!=digest_json(schedule)
                or contract['source_code_sha256']!=code_receipt()
                or contract['action_scoring_version']!=p['action_scoring_version']
                or report['model']!=p['inference'] or report['transport']!=p['transport']
                or report.get('protocol_id')!=p['protocol_id']
                or report.get('run_kind')!='controlled-h-confirmatory'
                or report.get('result_schema_version')!='2.1'
                or contract['provider'] not in ('mock',p['inference']['provider'])
                or report.get('model_inference')!=(contract['provider']=='local')
                or report['expected_queries']!=len(schedule)):
            raise ValueError('report contract differs from analysis freeze')
        rows=load_rows(report,args.report,schedule,context)
        real=(contract['provider']=='local' and report['model_inference'] is True)
        if real:
            from scripts.controlled_horizon_confirmatory_server import server_command
            provenance=contract['server_provenance']
            receipt=provenance['launch_receipt']
            if (receipt['protocol_digest']!=digest
                    or receipt['endpoint_sha256']!=provenance['endpoint_sha256']
                    or receipt['command']!=server_command(p,receipt['port'])
                    or receipt['runtime_versions']!={k:p['inference']['serving_stack'][k+'_version'] for k in ('vllm','transformers')}):
                raise ValueError('server provenance differs from freeze')
            expected=p['inference']['serving_stack']
            if any(report['runtime_versions'][package]!=expected[package+'_version']
                   for package in ('vllm','transformers')):
                raise ValueError('recorded serving runtime differs from freeze')
        output['analysis']=analyze_rows(rows,p,real)
        output['analysis']['quality_by_character_horizon_stratum']={
            f'{char}/{h}/{label}':dict(n=len(values),mean=statistics.fmean(values) if values else None)
            for char in p['release']['characters'] for h in p['inference']['horizons']
            for tag,label in ((True,'sensitive'),(False,'control'))
            for values in [[r['effective_quality'] for r in rows if r['character']==char
                            and r['horizon']==h and r['h1_h8_sensitive']==tag]]}
        output['analysis']['raw_regret_by_character_horizon']={
            f'{char}/{h}':dict(valid_n=len(values),mean=statistics.fmean(values) if values else None,
                              interpretation='conditional on legal action; invalid raw regrets remain absent')
            for char in p['release']['characters'] for h in p['inference']['horizons']
            for values in [[r['score']['regret'] for r in rows if r['character']==char and r['horizon']==h
                            and r['score']['regret'] is not None]]}
        output['analysis']['oracle_diagnostics'] = {
            f'{char}/{h}': dict(
                fixture_n=len(oracles), zero_spans=sum(o['best_value']==o['worst_value'] for o in oracles),
                mean_span=statistics.fmean(o['best_value']-o['worst_value'] for o in oracles),
                mean_baseline_quality={name:statistics.fmean(o['baselines'][name]['quality'] for o in oracles)
                                       for name in ('always_end_turn','uniform_legal_expected',
                                                    'h1_mismatched_oracle','h_aware_exact_oracle')})
            for char in p['release']['characters'] for h in p['inference']['horizons']
            for oracles in [[context[1][fid]['oracles'][str(h)] for fid,f in context[0].items()
                             if f.character==char]]}
        output['report_sha256']=hashlib.sha256(args.report.read_bytes()).hexdigest()
    _atomic_write_json(args.out,output)
    print(json.dumps(dict(planning_gate_passed=output['planning']['planning_gate_passed'],
                         valid_for_primary_inference=output['analysis']['valid_for_primary_inference'] if output['analysis'] else False)))


if __name__=='__main__':
    main()
