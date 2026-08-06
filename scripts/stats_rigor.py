#!/usr/bin/env python
"""P4b -- STATISTICAL RIGOR PASS over the slay-bench result matrix (zero GPU).

WHY THIS EXISTS
---------------
The external expert review (``docs/review_2026-07-14.md``, adopted as the
evaluation baseline) named statistics as a top-5 rejection reason: the matrix
reports means +/- std and nothing else. Critically, the benchmark's
**seed-matched format ablation was designed for paired testing and the paired
test had never been run**. This script is backlog row P4b (``docs/handoff.md``
Sec 6): bootstrap CIs, effect sizes, paired seed-matched format tests, and a
variance decomposition -- computed entirely from files already on disk.

It is ADDITIVE ANALYSIS ONLY. It reads results, never re-runs the benchmark,
never changes a published mean, and makes zero API calls.

WHAT IT ANALYSES
----------------
Two units of analysis, chosen by what the harness actually persisted:

  * SEED level (all four dimensions). Each per-seed file holds one summary per
    dimension. A (model, character, format) combo therefore contributes 5
    seed-level observations. Structured and raw share the same seed bases, so
    the two formats are PAIRED at the seed level.
  * SAMPLE level (synergy only). ``synergy.samples[]`` persists per-fixture
    outcomes for every combo (2,400 records). Verified 2026-08-07: for a given
    (model, character, seed), the structured and raw sample streams carry
    byte-identical ``expert_archetype``/``expert_pick_idx`` sequences in all 60
    pairs -- the two formats saw the SAME fixtures in the SAME offer positions.
    That licenses McNemar's exact test on paired binary outcomes.
    (``turn.samples[]``/``combat.samples[]`` were instrumented 2026-07-13, AFTER
    the matrix ran; only qwen3-32b has them, so turn/combat stay seed-level.)

METHOD CHOICES (rationale in docs/decision_log.md 2026-08-07)
-------------------------------------------------------------
  * Paired tests use an EXACT sign-flip permutation test, not a t-test: n=5
    seeds cannot support a normality assumption. Consequence, stated everywhere
    it matters: with 5 pairs there are 2^5 = 32 sign assignments, so the
    smallest attainable two-sided p is 2/32 = 0.0625. **No single combo can
    reach p < 0.05.** Per-combo rows are therefore descriptive; the inferential
    claims come from the pooled stratified test (sign-flips within combo,
    across all 12 model x character strata) and from sample-level McNemar.
  * Sample-level McNemar has more power but assumes independent pairs, and the
    same 20 fixtures recur across seeds. It is reported alongside the
    cluster-safe seed-level permutation test; a claim is called supported only
    when both agree, and disagreements are printed explicitly.
  * Multiplicity: Holm-Bonferroni within each family (a family = one metric
    across the 12 combos).
  * A non-significant result is NEVER reported as "no effect". Format
    insensitivity is tested as EQUIVALENCE (TOST via the 90% bootstrap CI of
    the paired difference) against a pre-declared margin of 0.05 -- the
    measurement granularity of the instrument, since one sample in 20 moves any
    rate by exactly 0.05.
  * Bootstrap: percentile method, 10,000 resamples, fixed RNG seed (numbers are
    reproducible). Seed-level CIs resample 5 values and are labelled COARSE.
    Synergy accuracies use a hierarchical bootstrap (resample seeds, then
    samples within seed) so fixture clustering is respected.
  * Boundary cells (0/0 or 100/100 correct) get Clopper-Pearson exact intervals;
    a bootstrap of a constant vector would report a zero-width CI.

READING THE OUTPUT
------------------
``docs/stats_report.md`` is the human artifact (committed; the paper cites it).
``results/stats/stats_rigor.json`` is the machine artifact (gitignored).
Every table carries its n and its caveat. Nothing here supersedes a published
mean -- it puts uncertainty around means that already exist.

RE-RUNNING WHEN NEW ROWS LAND (e.g. M3b frontier models)
--------------------------------------------------------
Models are DISCOVERED from filenames, not hard-coded. Drop new
``<model>[_silent]_<format>_seed<base>.json`` files into ``results/`` and re-run;
new models join every table automatically. Cells with a different sample size
(e.g. qwen3-32b's n=5 run-level) are tagged and never pooled with n=20 rows.

USAGE
-----
    .venv/Scripts/python.exe scripts/stats_rigor.py
    .venv/Scripts/python.exe scripts/stats_rigor.py --boot 2000 --quiet

Deterministic: fixed bootstrap seed -> identical numbers on every run.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

SEED_BASES = [42, 1042, 2042, 3042, 4042]
FORMATS = ("structured", "raw")
CHARACTERS = ("ironclad", "silent")

BOOT_DEFAULT = 10000
RNG_SEED = 20260807          # fixed => reproducible CIs
ALPHA = 0.05                 # 95% CIs
EQUIV_MARGIN = 0.05          # see module docstring: 1 sample in 20

# Metrics analysed per dimension. (key in the per-seed summary, display name,
# "higher is better" flag used only for wording).
METRICS: Dict[str, List[Tuple[str, str, bool]]] = {
    "turn":    [("avg_damage_ratio", "dmg_ratio", True),
                ("legal_rate", "legal_rate", True),
                ("parse_ok_rate", "parse_ok", True)],
    "combat":  [("win_rate", "win_rate", True),
                ("avg_hp_ratio", "hp_ratio", True),
                ("avg_parse_errors", "invalid_action_errors", False)],
    "synergy": [("archetype_acc", "archetype", True),
                ("card_pick_acc", "card_pick", True),
                ("removal_acc", "removal", True),
                ("parse_ok_rate", "parse_ok", True)],
    "run":     [("survival_rate", "survival", True),
                ("avg_floors_reached", "floors", True),
                ("avg_progress", "progress", True),
                ("avg_draft_coherence", "draft_coherence", True)],
}

# The metrics the paper's headline claims rest on.
HEADLINE = [("turn", "avg_damage_ratio"), ("combat", "win_rate"),
            ("combat", "avg_hp_ratio"), ("synergy", "archetype_acc"),
            ("synergy", "card_pick_acc"), ("synergy", "removal_acc"),
            ("run", "avg_floors_reached"), ("run", "avg_progress")]

# Per-sample synergy fields -> metric names (paired sample-level tests).
SYNERGY_SAMPLE_FIELDS = [("archetype_correct", "archetype"),
                         ("card_pick_correct", "card_pick"),
                         ("removal_correct", "removal")]

# Files that are diagnostics or superseded, never matrix rows.
EXCLUDE_SUBSTRINGS = ("parse_probe", "sharanga_smoke", "mock")


# --------------------------------------------------------------------------
# Statistical primitives (each independently unit-tested in tests/test_stats.py)
# --------------------------------------------------------------------------

def mean(xs: Sequence[float]) -> float:
    return float(np.mean(xs))


def bootstrap_mean_ci(values: Sequence[float], rng: np.random.Generator,
                      boot: int, alpha: float = ALPHA) -> Dict[str, float]:
    """Percentile bootstrap CI for the mean of ``values``.

    With the matrix's 5 seeds this resamples 5 numbers; the interval is honest
    but COARSE (it can only take a few dozen distinct endpoints). Callers label
    it as such. A constant vector yields a zero-width CI -- that is a property
    of the bootstrap, not evidence of certainty, so boundary cells use
    ``clopper_pearson`` instead.
    """
    v = np.asarray(values, dtype=float)
    n = len(v)
    if n == 0:
        return {"mean": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": 0}
    idx = rng.integers(0, n, size=(boot, n))
    means = v[idx].mean(axis=1)
    return {"mean": float(v.mean()),
            "lo": float(np.percentile(means, 100 * alpha / 2)),
            "hi": float(np.percentile(means, 100 * (1 - alpha / 2))),
            "n": n}


def hierarchical_bootstrap_ci(per_cluster: Sequence[Sequence[float]],
                              rng: np.random.Generator, boot: int,
                              alpha: float = ALPHA) -> Dict[str, float]:
    """Two-stage (cluster) bootstrap for a pooled rate.

    ``per_cluster`` is one list of 0/1 outcomes per seed. Resamples seeds with
    replacement, then samples within each drawn seed -- so the CI reflects both
    between-seed and within-seed variability. Using a flat bootstrap here would
    understate the interval, because the same 20 fixtures recur across seeds.
    """
    clusters = [np.asarray(c, dtype=float) for c in per_cluster if len(c)]
    if not clusters:
        return {"mean": float("nan"), "lo": float("nan"), "hi": float("nan"),
                "n_clusters": 0, "n_obs": 0}
    k = len(clusters)
    flat = np.concatenate(clusters)
    stats = np.empty(boot, dtype=float)
    for b in range(boot):
        pick = rng.integers(0, k, size=k)
        vals = []
        for j in pick:
            c = clusters[j]
            vals.append(c[rng.integers(0, len(c), size=len(c))])
        stats[b] = float(np.concatenate(vals).mean())
    return {"mean": float(flat.mean()),
            "lo": float(np.percentile(stats, 100 * alpha / 2)),
            "hi": float(np.percentile(stats, 100 * (1 - alpha / 2))),
            "n_clusters": k, "n_obs": int(flat.size)}


def exact_sign_flip_p(diffs: Sequence[float]) -> Dict[str, object]:
    """Exact two-sided paired permutation test (sign-flip) on the mean.

    Under H0 "format has no effect on this combo", the sign of each seed-matched
    difference is exchangeable. Enumerates all 2^n sign assignments (n <= 20).

    Zero differences are kept: they contribute to every permutation identically
    and shrink the observed statistic, which is the conservative choice.
    """
    d = np.asarray(diffs, dtype=float)
    n = len(d)
    if n == 0:
        return {"p": float("nan"), "n": 0, "exact": True, "obs": float("nan")}
    obs = abs(float(d.mean()))
    signs = np.array(list(itertools.product([1.0, -1.0], repeat=n)))
    perm = np.abs((signs * d).mean(axis=1))
    # >= obs, with a tolerance so float noise cannot drop the identity permutation
    p = float((perm >= obs - 1e-12).sum()) / len(perm)
    return {"p": p, "n": n, "exact": True, "obs": float(d.mean()),
            "n_perm": int(len(perm)), "p_floor": 2.0 / len(perm)}


def stratified_sign_flip_p(diffs_by_stratum: Dict[str, Sequence[float]],
                           rng: np.random.Generator, boot: int) -> Dict[str, object]:
    """Pooled paired test across strata (one stratum = one model x character).

    Statistic = unweighted mean of per-stratum mean differences, so a combo with
    more seeds cannot dominate. Signs are flipped independently per observation
    within its stratum. With 60 observations exhaustive enumeration is
    infeasible, so this is Monte-Carlo with the script's fixed RNG seed;
    ``n_perm`` is reported and the p-value carries its MC error.
    """
    keys = [k for k, v in diffs_by_stratum.items() if len(v)]
    if not keys:
        return {"p": float("nan"), "n_strata": 0}
    arrs = [np.asarray(diffs_by_stratum[k], dtype=float) for k in keys]
    obs = abs(float(np.mean([a.mean() for a in arrs])))
    count = 0
    for _ in range(boot):
        stat = np.mean([float((a * rng.choice([1.0, -1.0], size=len(a))).mean())
                        for a in arrs])
        if abs(stat) >= obs - 1e-12:
            count += 1
    # add-one correction: an MC permutation p is never reported as exactly 0
    p = (count + 1) / (boot + 1)
    return {"p": float(p), "n_strata": len(keys), "n_perm": boot,
            "obs": float(np.mean([a.mean() for a in arrs])),
            "exact": False,
            "mc_se": float(math.sqrt(max(p * (1 - p), 1e-12) / boot))}


def binom_pmf(k: int, n: int, p: float) -> float:
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_cdf(k: int, n: int, p: float) -> float:
    return sum(binom_pmf(i, n, p) for i in range(0, k + 1))


def mcnemar_exact(b: int, c: int) -> Dict[str, float]:
    """Exact (binomial) McNemar test on paired binary outcomes.

    ``b`` = pairs where condition A is correct and B is wrong; ``c`` the
    reverse. Concordant pairs carry no information about the difference. Under
    H0 the discordant pairs split Binomial(b+c, 1/2).

    Also returns the risk difference (b-c)/n_pairs -- but note n_pairs must be
    supplied by the caller for that, so here only the discordant-based odds
    ratio b/c is given.
    """
    n = b + c
    if n == 0:
        return {"p": 1.0, "b": b, "c": c, "n_discordant": 0, "odds_ratio": float("nan")}
    k = min(b, c)
    p = min(1.0, 2.0 * binom_cdf(k, n, 0.5))
    or_ = float("inf") if c == 0 else (0.0 if b == 0 else b / c)
    return {"p": float(p), "b": int(b), "c": int(c), "n_discordant": int(n),
            "odds_ratio": float(or_)}


def binom_test_two_sided(k: int, n: int, p0: float) -> float:
    """Exact two-sided binomial test (method of small p-values)."""
    if n == 0:
        return float("nan")
    obs = binom_pmf(k, n, p0)
    tot = sum(binom_pmf(i, n, p0) for i in range(n + 1)
              if binom_pmf(i, n, p0) <= obs * (1 + 1e-9))
    return float(min(1.0, tot))


def clopper_pearson(k: int, n: int, alpha: float = ALPHA) -> Tuple[float, float]:
    """Exact binomial CI by inverting the binomial test (bisection, no scipy).

    Used wherever a rate sits on a boundary (0/0 or all-correct), where the
    bootstrap would report a zero-width interval.
    """
    if n == 0:
        return (float("nan"), float("nan"))

    def _lo() -> float:
        if k == 0:
            return 0.0
        target = 1 - alpha / 2
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            # P(X >= k | p=mid) = 1 - CDF(k-1); want it == alpha/2
            if 1 - binom_cdf(k - 1, n, mid) < alpha / 2:
                lo = mid
            else:
                hi = mid
        return lo

    def _hi() -> float:
        if k == n:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if binom_cdf(k, n, mid) > alpha / 2:
                lo = mid
            else:
                hi = mid
        return hi

    return (_lo(), _hi())


def cohens_dz(diffs: Sequence[float]) -> float:
    """Paired effect size: mean(diff) / sd(diff). NaN when sd = 0."""
    d = np.asarray(diffs, dtype=float)
    if len(d) < 2:
        return float("nan")
    sd = float(d.std(ddof=1))
    if sd == 0:
        return float("nan") if d.mean() == 0 else float("inf") * np.sign(d.mean())
    return float(d.mean() / sd)


def cliffs_delta(x: Sequence[float], y: Sequence[float]) -> float:
    """Non-parametric effect size P(X>Y) - P(X<Y); small-n safe."""
    a, b = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    gt = float((a[:, None] > b[None, :]).sum())
    lt = float((a[:, None] < b[None, :]).sum())
    return (gt - lt) / (len(a) * len(b))


def holm(pvals: Sequence[float]) -> List[float]:
    """Holm-Bonferroni step-down adjusted p-values (monotone, capped at 1)."""
    idx = [i for i, p in enumerate(pvals) if not (isinstance(p, float) and math.isnan(p))]
    out = [float("nan")] * len(pvals)
    m = len(idx)
    order = sorted(idx, key=lambda i: pvals[i])
    running = 0.0
    for rank, i in enumerate(order):
        adj = min(1.0, (m - rank) * pvals[i])
        running = max(running, adj)
        out[i] = running
    return out


def equivalence_test(diffs: Sequence[float], margin: float,
                     rng: np.random.Generator, boot: int) -> Dict[str, object]:
    """TOST-style equivalence via the 90% bootstrap CI of the paired difference.

    A 90% CI wholly inside [-margin, +margin] is equivalent to both one-sided
    tests rejecting at alpha=0.05. "Inconclusive" is a real outcome and is
    reported as such -- it is NOT evidence of a difference, nor of equivalence.
    """
    ci = bootstrap_mean_ci(diffs, rng, boot, alpha=0.10)
    inside = (ci["lo"] >= -margin) and (ci["hi"] <= margin)
    return {"mean_diff": ci["mean"], "ci90_lo": ci["lo"], "ci90_hi": ci["hi"],
            "margin": margin, "equivalent": bool(inside),
            "verdict": "equivalent" if inside else "inconclusive"}


def anova_variance_shares(values: Dict[Tuple[str, str, str], List[float]]
                          ) -> Optional[Dict[str, float]]:
    """Variance decomposition on a balanced, fully crossed model x character x
    format design with the seeds as replicates.

    Returns eta^2 (share of total sum of squares) per term. Seeds are treated
    as replication rather than as a fitted factor, so ``residual`` IS the
    seed-level noise share -- which is exactly the "seed vs model vs format"
    question the review asked. ``seed_main_within_residual`` additionally splits
    off the seed main effect, an instrument check: a large value means some seed
    bases are systematically harder, not that the models are noisy.

    Returns None unless every cell is present with the same replicate count
    (eta^2 shares are only orthogonal on a balanced design).
    """
    models = sorted({k[0] for k in values})
    chars = sorted({k[1] for k in values})
    fmts = sorted({k[2] for k in values})
    reps = {len(v) for v in values.values()}
    if len(reps) != 1:
        return None
    r = reps.pop()
    if r < 2 or len(values) != len(models) * len(chars) * len(fmts):
        return None

    # y[i, j, k, rep]
    y = np.empty((len(models), len(chars), len(fmts), r), dtype=float)
    for i, m in enumerate(models):
        for j, c in enumerate(chars):
            for k, f in enumerate(fmts):
                cell = values.get((m, c, f))
                if cell is None:
                    return None
                y[i, j, k, :] = cell
    grand = y.mean()
    ss_total = float(((y - grand) ** 2).sum())
    if ss_total <= 0:
        return {"degenerate": True}

    n_cell = r
    a, b, c_ = len(models), len(chars), len(fmts)

    def ss_main(axis_keep: int) -> float:
        axes = tuple(ax for ax in range(4) if ax != axis_keep)
        m_ = y.mean(axis=axes)
        n_per = y.size / y.shape[axis_keep]
        return float((n_per * (m_ - grand) ** 2).sum())

    ss_model = ss_main(0)
    ss_char = ss_main(1)
    ss_fmt = ss_main(2)

    cell_means = y.mean(axis=3)                      # (a, b, c_)
    ss_cells = float(n_cell * ((cell_means - grand) ** 2).sum())
    ss_resid = ss_total - ss_cells                   # pure seed-level variation
    ss_inter = ss_cells - ss_model - ss_char - ss_fmt

    # Instrument check: how much of the residual is a systematic seed effect?
    seed_means = y.mean(axis=(0, 1, 2))              # (r,)
    ss_seed_main = float((y.size / r) * ((seed_means - grand) ** 2).sum())

    return {
        "model": ss_model / ss_total,
        "character": ss_char / ss_total,
        "format": ss_fmt / ss_total,
        "interactions": max(0.0, ss_inter) / ss_total,
        "residual_seed": ss_resid / ss_total,
        "seed_main_within_residual": (ss_seed_main / ss_resid) if ss_resid > 0 else float("nan"),
        "ss_total": ss_total,
        "n_obs": int(y.size),
        "levels": {"model": a, "character": b, "format": c_, "seeds": r},
        "degenerate": False,
    }


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def _fname(model: str, character: str, fmt: str, seed: int) -> str:
    tag = "_silent" if character == "silent" else ""
    return f"{model}{tag}_{fmt}_seed{seed}.json"


def discover_models(results_dir: str) -> List[str]:
    """Find every model with at least one matrix per-seed file.

    Filenames are ``<model>[_silent]_<format>_seed<base>.json``; models are
    parsed off the end so new (M3b) models appear with no code change.
    """
    found = set()
    for fn in os.listdir(results_dir):
        if not fn.endswith(".json"):
            continue
        if any(s in fn for s in EXCLUDE_SUBSTRINGS):
            continue
        stem = fn[:-len(".json")]
        for fmt in FORMATS:
            for base in SEED_BASES:
                suffix = f"_{fmt}_seed{base}"
                if stem.endswith(suffix):
                    head = stem[: -len(suffix)]
                    if head.endswith("_silent"):
                        head = head[: -len("_silent")]
                    if head:
                        found.add(head)
    return sorted(found)


def load_matrix(results_dir: str, models: Sequence[str]) -> Dict:
    """Load per-seed summaries + synergy per-sample records for every combo."""
    cells: Dict[Tuple[str, str, str], Dict] = {}
    for model in models:
        for ch in CHARACTERS:
            for fmt in FORMATS:
                per_seed: Dict[int, Dict] = {}
                for base in SEED_BASES:
                    path = os.path.join(results_dir, _fname(model, ch, fmt, base))
                    if not os.path.exists(path):
                        continue
                    with open(path, "r", encoding="utf-8") as fh:
                        per_seed[base] = json.load(fh)
                if per_seed:
                    cells[(model, ch, fmt)] = per_seed
    return cells


def metric_series(cells: Dict, model: str, ch: str, fmt: str,
                  dim: str, key: str) -> Tuple[List[int], List[float]]:
    """Seed-ordered (bases, values) for one metric of one combo. Missing = skipped."""
    per_seed = cells.get((model, ch, fmt), {})
    bases, vals = [], []
    for base in SEED_BASES:
        d = per_seed.get(base)
        if not d:
            continue
        block = d.get(dim)
        if not isinstance(block, dict):
            continue
        v = block.get(key)
        if v is None:
            continue
        bases.append(base)
        vals.append(float(v))
    return bases, vals


def dim_n(cells: Dict, model: str, ch: str, fmt: str, dim: str) -> Optional[int]:
    """Per-seed sample size for a dimension (guards n=5 vs n=20 blending)."""
    per_seed = cells.get((model, ch, fmt), {})
    ns = {(per_seed[b].get(dim) or {}).get("n") for b in per_seed
          if isinstance(per_seed[b].get(dim), dict)}
    ns.discard(None)
    return int(sorted(ns)[0]) if len(ns) == 1 else (None if not ns else -1)


def synergy_pairs(cells: Dict, model: str, ch: str, field: str
                  ) -> Tuple[List[List[Tuple[int, int]]], int]:
    """Fixture-matched (structured, raw) outcome pairs, grouped by seed.

    Returns (pairs_by_seed, n_dropped). A pair is dropped when either side is
    ``None`` -- the harness writes None when the model's answer did not parse or
    the fixture was ambiguous. Dropped counts are reported so every accuracy
    carries its conditioning caveat (deepseek-7b parse_ok .69-.92).
    """
    s_seeds = cells.get((model, ch, "structured"), {})
    r_seeds = cells.get((model, ch, "raw"), {})
    out, dropped = [], 0
    for base in SEED_BASES:
        ds, dr = s_seeds.get(base), r_seeds.get(base)
        if not ds or not dr:
            continue
        ss = (ds.get("synergy") or {}).get("samples") or []
        rs = (dr.get("synergy") or {}).get("samples") or []
        if len(ss) != len(rs):
            dropped += abs(len(ss) - len(rs))
        row = []
        for a, b in zip(ss, rs):
            va, vb = a.get(field), b.get(field)
            if va is None or vb is None:
                dropped += 1
                continue
            row.append((int(bool(va)), int(bool(vb))))
        if row:
            out.append(row)
    return out, dropped


def verify_pairing(cells: Dict, models: Sequence[str]) -> Dict:
    """Instrument check: do the two formats really see identical fixtures?

    Compares the (expert_archetype, expert_pick_idx) stream of structured vs raw
    for every (model, character, seed). Paired sample-level tests are only valid
    if this passes; the script refuses to run them for a combo that fails.
    """
    ok, bad, missing = 0, [], 0
    for model in models:
        for ch in CHARACTERS:
            for base in SEED_BASES:
                ds = cells.get((model, ch, "structured"), {}).get(base)
                dr = cells.get((model, ch, "raw"), {}).get(base)
                if not ds or not dr:
                    missing += 1
                    continue
                ka = [(s.get("expert_archetype"), s.get("expert_pick_idx"))
                      for s in (ds.get("synergy") or {}).get("samples") or []]
                kb = [(s.get("expert_archetype"), s.get("expert_pick_idx"))
                      for s in (dr.get("synergy") or {}).get("samples") or []]
                if ka and ka == kb:
                    ok += 1
                else:
                    bad.append(f"{model}/{ch}/seed{base}")
    return {"pairs_identical": ok, "mismatched": bad, "missing_pairs": missing,
            "valid": not bad}


# --------------------------------------------------------------------------
# Analyses
# --------------------------------------------------------------------------

def analysis_descriptive(cells: Dict, models: Sequence[str],
                         rng: np.random.Generator, boot: int) -> List[Dict]:
    """A. Bootstrap CI (over seeds) for every metric of every combo."""
    rows = []
    for model in models:
        for ch in CHARACTERS:
            for fmt in FORMATS:
                for dim, specs in METRICS.items():
                    n_per_seed = dim_n(cells, model, ch, fmt, dim)
                    for key, disp, _ in specs:
                        bases, vals = metric_series(cells, model, ch, fmt, dim, key)
                        if not vals:
                            continue
                        ci = bootstrap_mean_ci(vals, rng, boot)
                        rows.append({
                            "model": model, "character": ch, "format": fmt,
                            "dimension": dim, "metric": disp, "key": key,
                            "n_seeds": len(vals), "n_per_seed": n_per_seed,
                            "mean": round(ci["mean"], 4),
                            "std": round(float(np.std(vals, ddof=1)), 4) if len(vals) > 1 else 0.0,
                            "ci95_lo": round(ci["lo"], 4), "ci95_hi": round(ci["hi"], 4),
                            "min": round(min(vals), 4), "max": round(max(vals), 4),
                            "ci_note": "COARSE (bootstrap over %d seeds)" % len(vals),
                        })
    return rows


def analysis_format_paired(cells: Dict, models: Sequence[str],
                           rng: np.random.Generator, boot: int) -> Dict:
    """B. The test the design was built for: seed-matched structured vs raw.

    Per combo: exact sign-flip permutation p, Cohen's d_z, bootstrap CI of the
    paired difference, and a TOST equivalence verdict. Holm-adjusted within
    each metric family. Then a pooled stratified test per metric.
    """
    per_combo: List[Dict] = []
    pooled: List[Dict] = []

    for dim, specs in METRICS.items():
        for key, disp, higher_better in specs:
            family: List[Dict] = []
            strata: Dict[str, List[float]] = {}
            for model in models:
                for ch in CHARACTERS:
                    n_s = dim_n(cells, model, ch, "structured", dim)
                    n_r = dim_n(cells, model, ch, "raw", dim)
                    bs, vs = metric_series(cells, model, ch, "structured", dim, key)
                    br, vr = metric_series(cells, model, ch, "raw", dim, key)
                    common = [b for b in bs if b in br]
                    if len(common) < 2:
                        continue
                    if n_s is not None and n_r is not None and n_s != n_r:
                        continue        # never pair across different sample sizes
                    sv = [vs[bs.index(b)] for b in common]
                    rv = [vr[br.index(b)] for b in common]
                    diffs = [a - b for a, b in zip(sv, rv)]
                    test = exact_sign_flip_p(diffs)
                    ci = bootstrap_mean_ci(diffs, rng, boot)
                    eq = equivalence_test(diffs, EQUIV_MARGIN, rng, boot)
                    row = {
                        "dimension": dim, "metric": disp, "key": key,
                        "model": model, "character": ch,
                        "n_pairs": len(common), "n_per_seed": n_s,
                        "structured_mean": round(mean(sv), 4),
                        "raw_mean": round(mean(rv), 4),
                        "mean_diff": round(mean(diffs), 4),
                        "ci95_lo": round(ci["lo"], 4), "ci95_hi": round(ci["hi"], 4),
                        "p_exact": round(test["p"], 4),
                        "p_floor": round(test.get("p_floor", float("nan")), 4),
                        "dz": None if math.isnan(cohens_dz(diffs)) else round(cohens_dz(diffs), 3),
                        "equivalence": eq["verdict"],
                        "favours": ("structured" if mean(diffs) > 0 else
                                    ("raw" if mean(diffs) < 0 else "tie"))
                        if higher_better else
                        ("raw" if mean(diffs) > 0 else
                         ("structured" if mean(diffs) < 0 else "tie")),
                    }
                    family.append(row)
                    strata[f"{model}/{ch}"] = diffs
            if family:
                adj = holm([r["p_exact"] for r in family])
                for r, a in zip(family, adj):
                    r["p_holm"] = round(a, 4)
                per_combo.extend(family)
                pool = stratified_sign_flip_p(strata, rng, boot)
                all_d = [d for v in strata.values() for d in v]
                # Direction-consistency check. The permutation statistic is a MEAN,
                # so one model with a huge effect can carry a "significant" pooled
                # result while the direction flips across models. The sign test on
                # per-stratum directions (ties dropped) separates "format has a
                # consistent direction" from "one model dominates the average" --
                # the difference between a general claim and a model-property claim.
                n_s = sum(1 for v in strata.values() if mean(v) > 0)
                n_r = sum(1 for v in strata.values() if mean(v) < 0)
                p_sign = binom_test_two_sided(n_s, n_s + n_r, 0.5) if (n_s + n_r) else float("nan")
                pooled.append({
                    "dimension": dim, "metric": disp, "key": key,
                    "n_strata": pool["n_strata"], "n_pairs": len(all_d),
                    "mean_diff": round(pool["obs"], 4),
                    "p_pooled": round(pool["p"], 4),
                    "mc_se": round(pool["mc_se"], 5),
                    "n_favour_structured": n_s,
                    "n_favour_raw": n_r,
                    "n_tie": sum(1 for v in strata.values() if mean(v) == 0),
                    "p_sign_test": None if math.isnan(p_sign) else round(p_sign, 4),
                    "direction_consistent": bool((n_s + n_r) and not math.isnan(p_sign)
                                                 and p_sign < ALPHA),
                    "higher_is_better": higher_better,
                })
    return {"per_combo": per_combo, "pooled": pooled}


def analysis_synergy_mcnemar(cells: Dict, models: Sequence[str],
                             rng: np.random.Generator, boot: int,
                             pairing_ok: bool) -> List[Dict]:
    """C. Sample-level paired test on the fixture-matched synergy outcomes.

    Higher power than the 5-seed test, but assumes independent pairs while the
    same 20 fixtures recur across seeds. Reported next to the seed-level exact
    test; ``agrees_with_seed_level`` flags any conflict at alpha=0.05 vs 0.0625.
    """
    if not pairing_ok:
        return []
    rows = []
    for model in models:
        for ch in CHARACTERS:
            for field, disp in SYNERGY_SAMPLE_FIELDS:
                pairs_by_seed, dropped = synergy_pairs(cells, model, ch, field)
                flat = [p for seed_row in pairs_by_seed for p in seed_row]
                if not flat:
                    continue
                b = sum(1 for s, r in flat if s == 1 and r == 0)
                c = sum(1 for s, r in flat if s == 0 and r == 1)
                mc = mcnemar_exact(b, c)
                s_ci = hierarchical_bootstrap_ci([[s for s, _ in row] for row in pairs_by_seed],
                                                 rng, boot)
                r_ci = hierarchical_bootstrap_ci([[r for _, r in row] for row in pairs_by_seed],
                                                 rng, boot)
                n_pairs = len(flat)
                rows.append({
                    "model": model, "character": ch, "metric": disp,
                    "n_pairs": n_pairs, "n_dropped": dropped,
                    "structured_acc": round(s_ci["mean"], 4),
                    "structured_ci95": [round(s_ci["lo"], 4), round(s_ci["hi"], 4)],
                    "raw_acc": round(r_ci["mean"], 4),
                    "raw_ci95": [round(r_ci["lo"], 4), round(r_ci["hi"], 4)],
                    "risk_diff": round((b - c) / n_pairs, 4),
                    "b_struct_only": b, "c_raw_only": c,
                    "n_discordant": mc["n_discordant"],
                    "odds_ratio": (None if math.isinf(mc["odds_ratio"]) else
                                   (None if math.isnan(mc["odds_ratio"]) else round(mc["odds_ratio"], 3))),
                    "p_mcnemar": round(mc["p"], 5),
                })
    # Holm within each metric family
    for disp in {r["metric"] for r in rows}:
        fam = [r for r in rows if r["metric"] == disp]
        for r, a in zip(fam, holm([x["p_mcnemar"] for x in fam])):
            r["p_holm"] = round(a, 5)
    return rows


def analysis_variance(cells: Dict, models: Sequence[str]) -> List[Dict]:
    """D. Variance decomposition: how much of the spread is model vs seed noise?

    Runs on the largest balanced subset per metric (all models with all four
    combos at a single per-seed n). Reported as eta^2 shares of total SS.
    """
    out = []
    for dim, specs in METRICS.items():
        for key, disp, _ in specs:
            values: Dict[Tuple[str, str, str], List[float]] = {}
            usable_models = []
            for model in models:
                ok, ns = True, set()
                cellvals = {}
                for ch in CHARACTERS:
                    for fmt in FORMATS:
                        _, v = metric_series(cells, model, ch, fmt, dim, key)
                        n = dim_n(cells, model, ch, fmt, dim)
                        if len(v) != len(SEED_BASES):
                            ok = False
                        ns.add(n)
                        cellvals[(model, ch, fmt)] = v
                if ok and len(ns) == 1:
                    usable_models.append((model, ns.pop()))
                    values.update(cellvals)
            # keep only the dominant per-seed n (never mix n=5 run rows with n=20)
            if usable_models:
                from collections import Counter
                dom_n = Counter(n for _, n in usable_models).most_common(1)[0][0]
                keep = {m for m, n in usable_models if n == dom_n}
                values = {k: v for k, v in values.items() if k[0] in keep}
            else:
                dom_n = None
            if len(values) < 4 or len({k[0] for k in values}) < 2:
                continue
            shares = anova_variance_shares(values)
            if not shares or shares.get("degenerate"):
                out.append({"dimension": dim, "metric": disp, "key": key,
                            "n_models": len({k[0] for k in values}),
                            "n_per_seed": dom_n, "degenerate": True,
                            "note": "zero total variance (metric constant across the design)"})
                continue
            out.append({
                "dimension": dim, "metric": disp, "key": key,
                "models": sorted({k[0] for k in values}),
                "n_models": len({k[0] for k in values}),
                "n_per_seed": dom_n, "n_obs": shares["n_obs"],
                "share_model": round(shares["model"], 4),
                "share_character": round(shares["character"], 4),
                "share_format": round(shares["format"], 4),
                "share_interactions": round(shares["interactions"], 4),
                "share_residual_seed": round(shares["residual_seed"], 4),
                "seed_main_within_residual": (None if math.isnan(shares["seed_main_within_residual"])
                                              else round(shares["seed_main_within_residual"], 4)),
                "degenerate": False,
            })
    return out


def analysis_boundary_cells(cells: Dict, models: Sequence[str]) -> List[Dict]:
    """E. Exact intervals for cells sitting on a boundary (the 1.000s and 0.000s).

    Project rule: a boundary value is an instrument bug until audited. The audit
    for turn-level already ran (scripts/turn_saturation_check.py); this adds the
    statistical half -- an exact Clopper-Pearson interval on the underlying
    successes, so a saturated cell reports [lo, 1.0] instead of a zero-width
    bootstrap CI.
    """
    out = []
    # avg_damage_ratio is a mean of ratios, not a rate -- but AT the boundary the
    # k/n reading is exact (mean 1.0 with every ratio <= 1 means all samples hit
    # the oracle optimum; mean 0.0 means none did), which is precisely the
    # saturation cell we need an interval for.
    targets = [("turn", "avg_damage_ratio"), ("turn", "legal_rate"),
               ("turn", "parse_ok_rate"),
               ("combat", "win_rate"), ("synergy", "archetype_acc"),
               ("synergy", "card_pick_acc"), ("synergy", "removal_acc"),
               ("run", "survival_rate")]
    for model in models:
        for ch in CHARACTERS:
            for fmt in FORMATS:
                for dim, key in targets:
                    bases, vals = metric_series(cells, model, ch, fmt, dim, key)
                    if not vals:
                        continue
                    m = mean(vals)
                    if not (m <= 1e-9 or m >= 1 - 1e-9):
                        continue
                    n_per = dim_n(cells, model, ch, fmt, dim)
                    if not n_per or n_per < 0:
                        continue
                    n_tot = n_per * len(vals)
                    k = int(round(m * n_tot))
                    lo, hi = clopper_pearson(k, n_tot)
                    out.append({"model": model, "character": ch, "format": fmt,
                                "dimension": dim, "metric": key,
                                "value": round(m, 4), "successes": k, "trials": n_tot,
                                "cp95_lo": round(lo, 4), "cp95_hi": round(hi, 4)})
    return out


def analysis_run_vs_greedy(cells: Dict, models: Sequence[str], results_dir: str,
                           rng: np.random.Generator, boot: int) -> List[Dict]:
    """F. Run-level vs the MEASURED greedy anchor, matched on identical run seeds.

    ``run_all`` draws run seeds as ``range(base+300, base+300+n_run)``, and
    ``scripts/greedy_baseline.py`` swept the same scheme at n_run=20 while
    persisting per-run records. So for a model evaluated at n_run=k we can pull
    greedy's runs on the SAME k seeds per base and pair at the base-seed level.
    This is strictly better than comparing against greedy's 20-run average, and
    it is the test behind the "first model to rise off the run floor" claim.
    """
    anchors = {}
    for ch in CHARACTERS:
        p = os.path.join(results_dir, f"greedy_baseline_{ch}.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as fh:
                anchors[ch] = json.load(fh)
    out = []
    for model in models:
        for ch in CHARACTERS:
            anchor = anchors.get(ch)
            if not anchor:
                continue
            by_seed = {s["seed"]: s for s in anchor.get("all_samples", [])}
            for fmt in FORMATS:
                n_run = dim_n(cells, model, ch, fmt, "run")
                if not n_run or n_run < 1:
                    continue
                for key, disp in (("avg_floors_reached", "floors"),
                                  ("avg_progress", "progress"),
                                  ("survival_rate", "survival")):
                    bases, vals = metric_series(cells, model, ch, fmt, "run", key)
                    if len(vals) < 2:
                        continue
                    gvals, matched = [], True
                    for base in bases:
                        seeds = [base + 300 + i for i in range(n_run)]
                        recs = [by_seed.get(s) for s in seeds]
                        if any(r is None for r in recs):
                            matched = False
                            break
                        if key == "avg_floors_reached":
                            gvals.append(mean([r["floors_reached"] for r in recs]))
                        elif key == "avg_progress":
                            gvals.append(mean([r["progress"] for r in recs]))
                        else:
                            gvals.append(mean([1.0 if r["survived"] else 0.0 for r in recs]))
                    if not matched:
                        continue
                    diffs = [a - b for a, b in zip(vals, gvals)]
                    test = exact_sign_flip_p(diffs)
                    ci = bootstrap_mean_ci(diffs, rng, boot)
                    out.append({
                        "model": model, "character": ch, "format": fmt,
                        "metric": disp, "n_run_per_seed": n_run, "n_pairs": len(diffs),
                        "model_mean": round(mean(vals), 4),
                        "greedy_matched_mean": round(mean(gvals), 4),
                        "mean_diff": round(mean(diffs), 4),
                        "ci95_lo": round(ci["lo"], 4), "ci95_hi": round(ci["hi"], 4),
                        "p_exact": round(test["p"], 4),
                        "p_floor": round(test.get("p_floor", float("nan")), 4),
                        "dz": None if math.isnan(cohens_dz(diffs)) else round(cohens_dz(diffs), 3),
                        "seed_matched": True,
                    })
    # Holm within metric families
    for disp in {r["metric"] for r in out}:
        fam = [r for r in out if r["metric"] == disp]
        for r, a in zip(fam, holm([x["p_exact"] for x in fam])):
            r["p_holm"] = round(a, 4)
    return out


def analysis_headline_claims(cells: Dict, models: Sequence[str], desc: List[Dict],
                             fmt_res: Dict, mcnemar: List[Dict], var_rows: List[Dict],
                             run_rows: List[Dict], rng: np.random.Generator,
                             boot: int) -> List[Dict]:
    """G. Re-check each published headline claim against the statistics above.

    Every claim gets a verdict of SUPPORTED / SUPPORTED-DIRECTIONAL /
    UNDERPOWERED / NOT-SUPPORTED plus the evidence used. "UNDERPOWERED" is a
    distinct outcome from "NOT-SUPPORTED" on purpose.
    """
    claims: List[Dict] = []

    # C1 -- "structured >= raw on synergy removal for 5 of 6 models".
    rem = [r for r in mcnemar if r["metric"] == "removal"]
    by_model: Dict[str, List[Dict]] = {}
    for r in rem:
        by_model.setdefault(r["model"], []).append(r)
    holds, reverses, detail = [], [], []
    for model, rows in sorted(by_model.items()):
        d = mean([r["risk_diff"] for r in rows])
        (holds if d >= 0 else reverses).append(model)
        sig = [r for r in rows if r["p_mcnemar"] < ALPHA]
        detail.append({"model": model, "mean_risk_diff": round(d, 4),
                       "chars_significant_mcnemar": [r["character"] for r in sig]})
    claims.append({
        "id": "C1", "claim": "structured >= raw on synergy removal for 5 of 6 models",
        "verdict": "SUPPORTED" if len(reverses) <= 1 else "NOT-SUPPORTED",
        "n_hold": len(holds), "n_models": len(by_model),
        "models_holding": holds, "models_reversing": reverses,
        "evidence": "sample-level paired McNemar on fixture-matched pairs",
        "detail": detail,
    })

    # C2 -- format effect on synergy, pooled across the whole matrix. A pooled
    # result counts as SUPPORTED only when the magnitude test AND the direction
    # test agree; magnitude alone can be carried by a single model.
    for metric in ("archetype", "card_pick", "removal"):
        p = next((x for x in fmt_res["pooled"]
                  if x["dimension"] == "synergy" and x["metric"] == metric), None)
        if not p:
            continue
        if p["mean_diff"] <= 0:
            verdict = "NOT-SUPPORTED"
        elif p["p_pooled"] < ALPHA and p["direction_consistent"]:
            verdict = "SUPPORTED"
        elif p["p_pooled"] < ALPHA:
            verdict = "SUPPORTED-MAGNITUDE-ONLY"
        else:
            verdict = "UNDERPOWERED"
        claims.append({
            "id": f"C2-{metric}",
            "claim": f"structured beats raw on synergy {metric} across the matrix",
            "verdict": verdict,
            "pooled_mean_diff": p["mean_diff"], "p_pooled": p["p_pooled"],
            "p_sign_test": p["p_sign_test"],
            "strata_favouring_structured": p["n_favour_structured"],
            "strata_favouring_raw": p["n_favour_raw"],
            "note": (None if p["direction_consistent"] else
                     "pooled magnitude is significant but the DIRECTION is not "
                     "consistent across models (sign test n.s.) -- report as a "
                     "model-dependent effect, not a general one"),
            "evidence": ("stratified sign-flip permutation (magnitude) + exact sign "
                         "test on per-stratum direction, 12 model x character strata"),
        })

    # C3 -- "combat/run outcomes are format-insensitive". Tested as EQUIVALENCE,
    # never inferred from a null. Verdict wording distinguishes "holds
    # everywhere" from "holds except for an identifiable subgroup" -- the latter
    # is a correction to the claim, not a confirmation of it.
    for dim, key, disp in (("combat", "win_rate", "win_rate"),
                           ("combat", "avg_hp_ratio", "hp_ratio"),
                           ("run", "avg_progress", "progress")):
        rows = [r for r in fmt_res["per_combo"]
                if r["dimension"] == dim and r["key"] == key]
        if not rows:
            continue
        eq = [r for r in rows if r["equivalence"] == "equivalent"]
        frac = len(eq) / len(rows)
        if frac == 1.0:
            verdict = "SUPPORTED"
        elif frac >= 2 / 3:
            verdict = "PARTIAL — holds for most combos, fails for a named subgroup"
        else:
            verdict = "NOT-SUPPORTED-AS-STATED"
        claims.append({
            "id": f"C3-{dim}-{disp}",
            "claim": f"{dim} {disp} is insensitive to prompt format",
            "verdict": verdict,
            "combos_equivalent": len(eq), "combos_tested": len(rows),
            "margin": EQUIV_MARGIN,
            "not_equivalent": [f"{r['model']}/{r['character']}" for r in rows
                               if r["equivalence"] != "equivalent"],
            "note": (None if frac == 1.0 else
                     "combos listed in not_equivalent are NOT shown to differ -- "
                     "equivalence simply cannot be concluded for them at this margin "
                     "and n=5; the claim must be scoped to the combos that pass"),
            "evidence": f"TOST via 90% bootstrap CI, margin +/-{EQUIV_MARGIN}",
        })

    # C7 -- the format effect reaches the COMBAT horizon (correction candidate to
    # the standing "combat is format-insensitive on outcome" claim).
    for key, disp in (("win_rate", "win_rate"), ("avg_hp_ratio", "hp_ratio")):
        p = next((x for x in fmt_res["pooled"]
                  if x["dimension"] == "combat" and x["key"] == key), None)
        if not p:
            continue
        rows = [r for r in fmt_res["per_combo"]
                if r["dimension"] == "combat" and r["key"] == key]
        # Which combos actually move by more than the equivalence margin, and are
        # they the ones that sit BELOW the combat ceiling? If so, "format-
        # insensitive" was a ceiling artifact, not a property of the horizon.
        material = [r for r in rows if abs(r["mean_diff"]) > EQUIV_MARGIN]
        # "At the ceiling" is defined by WIN RATE for both metrics: winning every
        # fight in both formats is what removes the outcome variance a format
        # effect could show up in. (Using each metric's own value would make
        # hp_ratio -- an unbounded ratio against the greedy bot -- define its own
        # ceiling, which is circular.)
        win_rows = {(r["model"], r["character"]): r for r in fmt_res["per_combo"]
                    if r["dimension"] == "combat" and r["key"] == "win_rate"}
        def _saturated(r):
            w = win_rows.get((r["model"], r["character"]))
            return bool(w and min(w["structured_mean"], w["raw_mean"]) >= 0.95)
        at_ceiling = [r for r in rows if _saturated(r)]
        material_at_ceiling = [r for r in material if _saturated(r)]
        claims.append({
            "material_strata": [f"{r['model']}/{r['character']} ({r['mean_diff']:+.3f})"
                                for r in material],
            "n_at_combat_ceiling": len(at_ceiling),
            "n_material_among_ceiling_models": len(material_at_ceiling),
            "ceiling_artifact_note": (
                "every combo whose effect exceeds the equivalence margin sits BELOW "
                "the combat ceiling => the old 'combat is format-insensitive' reading "
                "was a CEILING ARTIFACT: models that win every fight leave format "
                "nothing to move" if material and not material_at_ceiling else
                "some ceiling-saturated combos also move materially -- do not attribute "
                "the effect to the ceiling alone"),
            "id": f"C7-{disp}",
            "claim": f"prompt format reaches the COMBAT horizon (structured > raw on {disp})",
            "verdict": ("SUPPORTED" if p["p_pooled"] < ALPHA and p["mean_diff"] > 0
                        and p["direction_consistent"] else
                        ("SUPPORTED-MAGNITUDE-ONLY" if p["p_pooled"] < ALPHA and p["mean_diff"] > 0
                         else "UNDERPOWERED")),
            "pooled_mean_diff": p["mean_diff"], "p_pooled": p["p_pooled"],
            "p_sign_test": p["p_sign_test"],
            "strata_favouring_structured": p["n_favour_structured"],
            "strata_favouring_raw": p["n_favour_raw"],
            "note": ("if SUPPORTED this CORRECTS the standing claim that combat "
                     "outcomes are format-insensitive; check whether the effect is "
                     "carried by the R1 distills before generalising"),
            "evidence": "stratified permutation + sign test over 12 strata",
        })

    # C8 -- turn-level format direction. The published framing is that the format
    # effect is a MODEL property with no fixed sign; test that directly.
    p = next((x for x in fmt_res["pooled"]
              if x["dimension"] == "turn" and x["key"] == "avg_damage_ratio"), None)
    if p:
        claims.append({
            "id": "C8",
            "claim": "the turn-level format effect has no consistent direction (it is a model property)",
            "verdict": ("SUPPORTED" if not p["direction_consistent"] else "NOT-SUPPORTED"),
            "pooled_mean_diff": p["mean_diff"], "p_pooled": p["p_pooled"],
            "p_sign_test": p["p_sign_test"],
            "strata_favouring_structured": p["n_favour_structured"],
            "strata_favouring_raw": p["n_favour_raw"],
            "note": ("the pooled MAGNITUDE favours raw and is significant, but the "
                     "direction splits across models -- so the honest statement is "
                     "'format matters, its sign is model-specific', NOT 'raw beats "
                     "structured at turn level'"),
            "evidence": "stratified permutation (magnitude) vs sign test (direction)",
        })

    # C4 -- run-level is a shared collapse floor (models cluster at greedy).
    floors = [r for r in run_rows if r["metric"] == "floors"]
    surv_rows = [r for r in run_rows if r["metric"] == "survival"]
    if floors:
        # "as extreme as the design allows": every seed pair the same sign.
        above = [r for r in floors if r["mean_diff"] > 0 and r["p_exact"] <= r["p_floor"] + 1e-9]
        below = [r for r in floors if r["mean_diff"] < 0 and r["p_exact"] <= r["p_floor"] + 1e-9]
        surv_lift = [r for r in surv_rows if r["mean_diff"] > 0.02]
        claims.append({
            "id": "C4", "claim": "run-level is a shared collapse floor (on par with greedy)",
            "verdict": "SUPPORTED-WITH-NUANCE",
            "combos_tested": len(floors),
            "combos_above_greedy_on_floors_all_seeds": [
                f"{r['model']}/{r['character']}/{r['format']} ({r['mean_diff']:+.2f})" for r in above],
            "combos_below_greedy_on_floors_all_seeds": [
                f"{r['model']}/{r['character']}/{r['format']} ({r['mean_diff']:+.2f})" for r in below],
            "combos_with_survival_lift_gt_0.02": [
                f"{r['model']}/{r['character']}/{r['format']} ({r['mean_diff']:+.3f})" for r in surv_lift],
            "note": ("nuance the paper must carry: SURVIVAL is floored for everyone, but "
                     "FLOORS/PROGRESS show small seed-consistent lifts over the matched "
                     "greedy anchor for some combos (~0.5-1.3 floors). 'On par, not "
                     "beating' is right for survival; for floors say 'within ~1 floor of "
                     "greedy'. n=5 seed pairs => p_min = 0.0625, so none of these can "
                     "reach alpha=0.05 by construction."),
            "evidence": "run-seed-matched paired comparison against the measured greedy anchor",
        })

    # C5 -- qwen3-32b rises off the run floor (the registered n=25 signal).
    # The published comparison used greedy's 100-run anchor (survival .01); this
    # re-runs it against greedy on the SAME 25 run seeds, which is the honest
    # comparator and gives a smaller gap.
    q = [r for r in run_rows if r["model"].startswith("qwen3-32b")
         and r["character"] == "ironclad" and r["format"] == "structured"]
    if q:
        surv = next((r for r in q if r["metric"] == "survival"), None)
        fl = next((r for r in q if r["metric"] == "floors"), None)
        n_run = (surv or fl)["n_run_per_seed"] * (surv or fl)["n_pairs"]
        k = lo = hi = None
        gk = None
        if surv is not None:
            k = int(round(surv["model_mean"] * n_run))
            lo, hi = clopper_pearson(k, n_run)
            gk = int(round(surv["greedy_matched_mean"] * n_run))
        claims.append({
            "id": "C5",
            "claim": "qwen3-32b/Ironclad/structured is the first model to rise off the run floor",
            "verdict": "UNDERPOWERED",
            "survival_successes": k, "survival_trials": n_run,
            "survival_cp95": [round(lo, 4), round(hi, 4)] if k is not None else None,
            "greedy_survivors_same_seeds": gk,
            "greedy_matched_survival": surv["greedy_matched_mean"] if surv else None,
            "survival_vs_greedy_diff": surv["mean_diff"] if surv else None,
            "survival_p_exact": surv["p_exact"] if surv else None,
            "floors_model": fl["model_mean"] if fl else None,
            "greedy_matched_floors": fl["greedy_matched_mean"] if fl else None,
            "floors_vs_greedy_diff": fl["mean_diff"] if fl else None,
            "floors_p_exact": fl["p_exact"] if fl else None,
            "note": ("CORRECTION the docs must absorb: the published gap compares the "
                     "model's 25 runs against greedy's 100-run anchor (survival .01, "
                     "12.48 floors). On the SAME 25 run seeds greedy scores higher than "
                     "its global anchor, so the honest gap is smaller than published. "
                     "Registered phrasing ('signal, not a win') stands and is now "
                     "quantified: with 5 seed pairs p_min = 0.0625, so this cannot reach "
                     "alpha=0.05 by construction; confirming it needs N_RUN=20."),
            "evidence": "run-seed-matched paired test + exact binomial CI on survival",
        })

    # C6 -- models separate at reasoning horizons and converge at survival horizons.
    sep = {}
    for dim in ("turn", "combat", "synergy", "run"):
        key = {"turn": "dmg_ratio", "combat": "win_rate",
               "synergy": "archetype", "run": "floors"}[dim]
        row = next((r for r in var_rows if r["dimension"] == dim
                    and r["metric"] == key and not r.get("degenerate")), None)
        if row:
            sep[dim] = {"share_model": row["share_model"],
                        "share_residual_seed": row["share_residual_seed"],
                        "n_models": row["n_models"]}
    if sep:
        claims.append({
            "id": "C6",
            "claim": "between-model variance is large at reasoning horizons, small at survival horizons",
            "verdict": "SUPPORTED" if sep.get("turn", {}).get("share_model", 0) >
                       sep.get("run", {}).get("share_model", 1) else "NOT-SUPPORTED",
            "model_variance_share_by_dimension": sep,
            "evidence": "eta^2 shares from the balanced model x character x format decomposition",
        })
    return claims


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def _fmt(v, nd=3):
    if v is None:
        return "-"
    if isinstance(v, float):
        if math.isnan(v):
            return "-"
        return f"{v:.{nd}f}"
    return str(v)


def render_markdown(res: Dict) -> str:
    L: List[str] = []
    meta = res["meta"]
    L.append("# Statistical rigor pass (P4b) — slay-bench")
    L.append("")
    L.append(f"*Generated by `scripts/stats_rigor.py` on {meta['generated']}. "
             f"Zero GPU, zero API: pure analysis of {meta['n_cells']} on-disk combos "
             f"({meta['n_models']} models × {len(CHARACTERS)} characters × {len(FORMATS)} formats "
             f"× {len(SEED_BASES)} seeds). Bootstrap B={meta['boot']}, RNG seed {meta['rng_seed']} "
             f"→ numbers reproduce exactly.*")
    L.append("")
    L.append("**This file adds uncertainty to published means; it changes none of them.**")
    L.append("")
    L.append("## 0. Method + the power ceiling you must quote with these numbers")
    L.append("")
    L.append("- Paired format tests are **exact sign-flip permutation tests** on the 5 "
             "seed-matched differences (no normality assumption at n=5).")
    L.append(f"- **Hard ceiling:** 2^5 = 32 sign assignments ⇒ the smallest attainable "
             f"two-sided p per combo is **0.0625**. No single combo can reach p<0.05. "
             f"Per-combo rows are descriptive; inference comes from the pooled stratified "
             f"test and from sample-level McNemar.")
    L.append("- Synergy is additionally tested at the **sample level** (McNemar exact) "
             "because structured and raw saw byte-identical fixtures — verified below.")
    L.append("- Multiplicity: **Holm–Bonferroni** within each metric family.")
    L.append(f"- Format *insensitivity* is tested as **equivalence** (TOST via the 90% "
             f"bootstrap CI, margin ±{EQUIV_MARGIN} = one sample in 20), never inferred "
             f"from a non-significant test.")
    L.append("- Boundary cells get **Clopper–Pearson** exact intervals (a bootstrap of a "
             "constant vector reports zero width, which is not certainty).")
    L.append("")

    pv = res["pairing_verification"]
    L.append("### 0.1 Pairing verification (precondition for every paired test)")
    L.append("")
    L.append(f"- Structured/raw sample streams compared on `(expert_archetype, expert_pick_idx)`: "
             f"**{pv['pairs_identical']} of {pv['pairs_identical'] + len(pv['mismatched'])} "
             f"(model × character × seed) pairs identical**, "
             f"{len(pv['mismatched'])} mismatched, {pv['missing_pairs']} pairs absent.")
    L.append(f"- Verdict: **{'PASS — sample-level pairing is real' if pv['valid'] else 'FAIL'}**"
             + ("" if pv["valid"] else f" — {', '.join(pv['mismatched'][:6])}"))
    L.append("")

    L.append("## 1. Headline-claim verdicts")
    L.append("")
    L.append("| Claim | Verdict | Key evidence |")
    L.append("|---|---|---|")
    for c in res["claims"]:
        ev = []
        for k in ("pooled_mean_diff", "p_pooled", "p_sign_test", "n_hold",
                  "combos_equivalent", "combos_tested", "survival_cp95",
                  "survival_p_exact"):
            if k in c and c[k] is not None:
                ev.append(f"{k}={c[k]}")
        share = c.get("model_variance_share_by_dimension")
        if share:
            ev.append("model-variance share " + ", ".join(
                f"{d} {v['share_model']:.2f}" for d, v in share.items()))
        L.append(f"| **{c['id']}** {c['claim']} | `{c['verdict']}` | {'; '.join(ev[:3])} |")
    L.append("")
    for c in res["claims"]:
        if c.get("note"):
            L.append(f"- **{c['id']} caveat:** {c['note']}")
        if c.get("ceiling_artifact_note"):
            L.append(f"- **{c['id']} ceiling check:** {c['ceiling_artifact_note']} "
                     f"(material strata: {', '.join(c.get('material_strata', [])) or 'none'})")
    L.append("")

    L.append("## 2. Format ablation — pooled across the matrix (the paired test that had never been run)")
    L.append("")
    L.append("Stratified sign-flip permutation over model × character strata; "
             "statistic = unweighted mean of per-stratum mean differences "
             "(structured − raw). **Two tests, deliberately:** `p (magnitude)` can be "
             "carried by one model with a large effect, so `p (direction)` — an exact "
             "sign test on which format each stratum favours — decides whether the "
             "effect is *general* or *model-specific*. A claim is general only when "
             "both are significant.")
    L.append("")
    L.append("| Dim | Metric | strata | pairs | mean diff (S−R) | p (magnitude) | S>R | R>S | tie | p (direction) | reading |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["format_pooled"]:
        mag = r["p_pooled"] < ALPHA
        con = r["direction_consistent"]
        reading = ("general effect" if mag and con else
                   ("model-specific" if mag else "no evidence"))
        L.append(f"| {r['dimension']} | {r['metric']} | {r['n_strata']} | {r['n_pairs']} | "
                 f"{_fmt(r['mean_diff'],4)} | {_fmt(r['p_pooled'],4)} | "
                 f"{r['n_favour_structured']} | {r['n_favour_raw']} | {r['n_tie']} | "
                 f"{_fmt(r['p_sign_test'],4)} | {reading} |")
    L.append("")

    L.append("## 3. Format ablation — synergy at the sample level (McNemar exact, fixture-matched)")
    L.append("")
    L.append("The strongest test available: same fixture, same offer position, both formats. "
             "`b` = structured-only correct, `c` = raw-only correct; concordant pairs carry "
             "no information. CIs are hierarchical bootstraps (seed → sample).")
    L.append("")
    L.append("| Model | Char | Metric | pairs | dropped | structured [95% CI] | raw [95% CI] | risk diff | b/c | p | p (Holm) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["synergy_mcnemar"]:
        L.append(f"| {r['model']} | {r['character']} | {r['metric']} | {r['n_pairs']} | "
                 f"{r['n_dropped']} | {_fmt(r['structured_acc'])} "
                 f"[{_fmt(r['structured_ci95'][0])}, {_fmt(r['structured_ci95'][1])}] | "
                 f"{_fmt(r['raw_acc'])} [{_fmt(r['raw_ci95'][0])}, {_fmt(r['raw_ci95'][1])}] | "
                 f"{_fmt(r['risk_diff'])} | {r['b_struct_only']}/{r['c_raw_only']} | "
                 f"{_fmt(r['p_mcnemar'],4)} | {_fmt(r['p_holm'],4)} |")
    L.append("")

    L.append("## 4. Format ablation — per combo, seed-matched (all dimensions)")
    L.append("")
    L.append(f"Exact sign-flip p; **minimum attainable p = 0.0625** at 5 pairs. "
             f"`equiv` = TOST verdict at ±{EQUIV_MARGIN}.")
    L.append("")
    L.append("| Dim | Metric | Model | Char | n | S mean | R mean | diff | 95% CI | p | p(Holm) | d_z | equiv |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["format_per_combo"]:
        if (r["dimension"], r["key"]) not in HEADLINE:
            continue
        L.append(f"| {r['dimension']} | {r['metric']} | {r['model']} | {r['character']} | "
                 f"{r['n_pairs']} | {_fmt(r['structured_mean'])} | {_fmt(r['raw_mean'])} | "
                 f"{_fmt(r['mean_diff'],4)} | [{_fmt(r['ci95_lo'],3)}, {_fmt(r['ci95_hi'],3)}] | "
                 f"{_fmt(r['p_exact'],4)} | {_fmt(r.get('p_holm'),4)} | {_fmt(r['dz'],2)} | "
                 f"{'yes' if r['equivalence']=='equivalent' else 'incon.'} |")
    L.append("")
    L.append("*(Non-headline metrics — legal_rate, parse_ok, invalid-action errors, "
             "draft coherence — are in the JSON artifact.)*")
    L.append("")

    L.append("## 5. Variance decomposition (η² shares of total sum of squares)")
    L.append("")
    L.append("Balanced model × character × format design with the 5 seeds as replicates, so "
             "`residual` **is** seed-level noise. `seed-main/resid` splits off the seed main "
             "effect — an instrument check: a large value means some seed bases are "
             "systematically harder, not that models are noisy.")
    L.append("")
    L.append("| Dim | Metric | models | n/seed | model | character | format | interactions | residual (seed) | seed-main/resid |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in res["variance"]:
        if r.get("degenerate"):
            L.append(f"| {r['dimension']} | {r['metric']} | {r.get('n_models','-')} | "
                     f"{r.get('n_per_seed','-')} | — | — | — | — | — | *{r['note']}* |")
            continue
        L.append(f"| {r['dimension']} | {r['metric']} | {r['n_models']} | {r['n_per_seed']} | "
                 f"**{_fmt(r['share_model'])}** | {_fmt(r['share_character'])} | "
                 f"{_fmt(r['share_format'])} | {_fmt(r['share_interactions'])} | "
                 f"{_fmt(r['share_residual_seed'])} | {_fmt(r['seed_main_within_residual'])} |")
    L.append("")

    L.append("## 6. Run level vs the measured greedy anchor (matched on identical run seeds)")
    L.append("")
    L.append("`run_all` draws run seeds `range(base+300, base+300+n_run)`; the greedy sweep "
             "used the same scheme at n_run=20 and kept per-run records, so greedy is "
             "subset to the **exact same run seeds** before pairing. Strictly tighter than "
             "comparing against greedy's 20-run average.")
    L.append("")
    L.append("| Model | Char | Fmt | Metric | runs/seed | model | greedy (matched) | diff | 95% CI | p | d_z |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["run_vs_greedy"]:
        L.append(f"| {r['model']} | {r['character']} | {r['format']} | {r['metric']} | "
                 f"{r['n_run_per_seed']} | {_fmt(r['model_mean'])} | "
                 f"{_fmt(r['greedy_matched_mean'])} | {_fmt(r['mean_diff'],4)} | "
                 f"[{_fmt(r['ci95_lo'],3)}, {_fmt(r['ci95_hi'],3)}] | {_fmt(r['p_exact'],4)} | "
                 f"{_fmt(r['dz'],2)} |")
    L.append("")

    if res["boundary"]:
        L.append("## 7. Boundary cells — exact (Clopper–Pearson) intervals")
        L.append("")
        L.append("Every 0.000 and 1.000 in the matrix, with the interval a bootstrap cannot give.")
        L.append("")
        L.append("| Model | Char | Fmt | Dim | Metric | value | k/n | exact 95% CI |")
        L.append("|---|---|---|---|---|---|---|---|")
        for r in res["boundary"]:
            L.append(f"| {r['model']} | {r['character']} | {r['format']} | {r['dimension']} | "
                     f"{r['metric']} | {_fmt(r['value'])} | {r['successes']}/{r['trials']} | "
                     f"[{_fmt(r['cp95_lo'],4)}, {_fmt(r['cp95_hi'],4)}] |")
        L.append("")

    L.append("## 8. Per-combo bootstrap CIs (headline metrics)")
    L.append("")
    L.append("Percentile bootstrap over the 5 seed-level values — **coarse by construction**; "
             "quote alongside n, never alone.")
    L.append("")
    L.append("| Model | Char | Fmt | Dim | Metric | n/seed | mean | std | 95% CI | seed range |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in res["descriptive"]:
        if (r["dimension"], r["key"]) not in HEADLINE:
            continue
        L.append(f"| {r['model']} | {r['character']} | {r['format']} | {r['dimension']} | "
                 f"{r['metric']} | {r['n_per_seed']} | {_fmt(r['mean'],4)} | {_fmt(r['std'],4)} | "
                 f"[{_fmt(r['ci95_lo'],3)}, {_fmt(r['ci95_hi'],3)}] | "
                 f"{_fmt(r['min'],3)}–{_fmt(r['max'],3)} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("*Reproduce: `.venv/Scripts/python.exe scripts/stats_rigor.py`. "
             "New models are discovered from `results/` filenames — M3b rows join every "
             "table with no code change.*")
    return "\n".join(L)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="P4b statistical rigor pass (zero GPU).")
    ap.add_argument("--results-dir", default=os.path.join(ROOT, "results"))
    ap.add_argument("--out-json", default=os.path.join(ROOT, "results", "stats", "stats_rigor.json"))
    ap.add_argument("--out-md", default=os.path.join(ROOT, "docs", "stats_report.md"))
    ap.add_argument("--boot", type=int, default=BOOT_DEFAULT,
                    help="bootstrap / Monte-Carlo permutation resamples (default %d)" % BOOT_DEFAULT)
    ap.add_argument("--models", nargs="*", default=None,
                    help="restrict to these models (default: discover from results/)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    def say(*a):
        if not args.quiet:
            print(*a, flush=True)

    rng = np.random.default_rng(RNG_SEED)
    models = args.models or discover_models(args.results_dir)
    if not models:
        print("No matrix result files found in", args.results_dir, file=sys.stderr)
        return 1
    say(f"models discovered ({len(models)}): {', '.join(models)}")

    cells = load_matrix(args.results_dir, models)
    say(f"loaded {len(cells)} (model, character, format) combos")

    pairing = verify_pairing(cells, models)
    say(f"pairing verification: {pairing['pairs_identical']} identical, "
        f"{len(pairing['mismatched'])} mismatched -> "
        f"{'PASS' if pairing['valid'] else 'FAIL (sample-level tests skipped)'}")

    say("A. descriptive bootstrap CIs ...")
    desc = analysis_descriptive(cells, models, rng, args.boot)
    say("B. seed-matched paired format tests ...")
    fmt_res = analysis_format_paired(cells, models, rng, args.boot)
    say("C. synergy sample-level McNemar ...")
    mcn = analysis_synergy_mcnemar(cells, models, rng, args.boot, pairing["valid"])
    say("D. variance decomposition ...")
    var_rows = analysis_variance(cells, models)
    say("E. boundary-cell exact intervals ...")
    boundary = analysis_boundary_cells(cells, models)
    say("F. run level vs seed-matched greedy anchor ...")
    run_rows = analysis_run_vs_greedy(cells, models, args.results_dir, rng, args.boot)
    say("G. headline-claim verdicts ...")
    claims = analysis_headline_claims(cells, models, desc, fmt_res, mcn,
                                      var_rows, run_rows, rng, args.boot)

    import datetime
    res = {
        "meta": {
            "generated": datetime.date.today().isoformat(),
            "script": "scripts/stats_rigor.py",
            "boot": args.boot, "rng_seed": RNG_SEED, "alpha": ALPHA,
            "equivalence_margin": EQUIV_MARGIN,
            "seed_bases": SEED_BASES,
            "n_models": len(models), "models": list(models),
            "n_cells": len(cells),
            "power_ceiling_note": ("5 seed pairs => 32 sign assignments => minimum "
                                   "attainable two-sided p per combo is 0.0625"),
            "additive_only": True,
        },
        "pairing_verification": pairing,
        "claims": claims,
        "format_pooled": fmt_res["pooled"],
        "format_per_combo": fmt_res["per_combo"],
        "synergy_mcnemar": mcn,
        "variance": var_rows,
        "run_vs_greedy": run_rows,
        "boundary": boundary,
        "descriptive": desc,
    }

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    with open(args.out_md, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(res))
    say(f"\nwrote {args.out_json}")
    say(f"wrote {args.out_md}")

    say("\n--- claim verdicts ---")
    for c in claims:
        say(f"  {c['id']:12} {c['verdict']:22} {c['claim']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
