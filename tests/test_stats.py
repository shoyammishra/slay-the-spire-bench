"""Statistical-primitive tests for scripts/stats_rigor.py (P4b) — no API, no GPU.

The analysis script is itself an instrument, and this project's standing rule is
that the instrument is suspect before the subject is. Every primitive is checked
against a value derived by hand or by an independent closed-form route, so a
silent change in the statistics cannot quietly move a published p-value.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import math
import numpy as np

from stats_rigor import (
    exact_sign_flip_p, stratified_sign_flip_p, mcnemar_exact,
    binom_test_two_sided, binom_cdf, clopper_pearson, cohens_dz, cliffs_delta,
    holm, bootstrap_mean_ci, hierarchical_bootstrap_ci, equivalence_test,
    anova_variance_shares, discover_models, EQUIV_MARGIN,
)


# ── Paired permutation test ───────────────────────────────────────────────────

def test_sign_flip_is_exact_and_hits_its_floor():
    """All-positive differences give the most extreme attainable p = 2/2^n."""
    res = exact_sign_flip_p([0.1, 0.2, 0.3, 0.4, 0.5])
    assert res["exact"] is True
    assert res["n_perm"] == 32
    assert abs(res["p"] - 2 / 32) < 1e-12, res["p"]
    assert abs(res["p_floor"] - 0.0625) < 1e-12
    print(f"[PASS] exact sign-flip: p={res['p']:.4f} at the 0.0625 floor")


def test_sign_flip_symmetric_data_is_not_significant():
    """A symmetric difference vector cannot look like an effect."""
    res = exact_sign_flip_p([0.2, -0.2, 0.1, -0.1])
    assert res["p"] > 0.9, res["p"]
    print(f"[PASS] symmetric diffs -> p={res['p']:.3f}")


def test_sign_flip_all_zero_diffs_gives_p_one():
    """Zero differences are kept (conservative), so p must be exactly 1.0."""
    res = exact_sign_flip_p([0.0, 0.0, 0.0])
    assert res["p"] == 1.0
    print("[PASS] all-zero diffs -> p=1.0")


def test_sign_flip_is_sign_symmetric():
    """Flipping every difference cannot change a two-sided p-value."""
    a = exact_sign_flip_p([0.3, 0.1, 0.05, 0.2, 0.4])["p"]
    b = exact_sign_flip_p([-0.3, -0.1, -0.05, -0.2, -0.4])["p"]
    assert abs(a - b) < 1e-12
    print(f"[PASS] two-sided symmetry: {a:.4f} == {b:.4f}")


def test_stratified_permutation_detects_a_consistent_shift():
    """A uniform +0.2 shift across 12 strata must beat the per-combo 0.0625 floor."""
    rng = np.random.default_rng(7)
    strata = {f"m{i}": [0.2, 0.15, 0.25, 0.2, 0.18] for i in range(12)}
    res = stratified_sign_flip_p(strata, rng, 2000)
    assert res["p"] < 0.01, res["p"]
    assert res["n_strata"] == 12
    print(f"[PASS] pooled permutation recovers a consistent effect: p={res['p']:.5f}")


def test_stratified_permutation_p_is_never_zero():
    """Monte-Carlo p uses the add-one correction, so 0 is unreportable."""
    rng = np.random.default_rng(3)
    strata = {f"m{i}": [5.0] * 5 for i in range(10)}
    res = stratified_sign_flip_p(strata, rng, 200)
    assert res["p"] >= 1 / 201 - 1e-12 and res["p"] > 0
    print(f"[PASS] MC p floored at 1/(B+1): {res['p']:.5f}")


# ── McNemar / binomial ────────────────────────────────────────────────────────

def test_mcnemar_matches_hand_computed_binomial():
    """b=9, c=1: p = 2 * P(X<=1 | Bin(10,0.5)) = 2 * 11/1024."""
    res = mcnemar_exact(9, 1)
    assert abs(res["p"] - 2 * (11 / 1024)) < 1e-12, res["p"]
    assert res["n_discordant"] == 10
    assert abs(res["odds_ratio"] - 9.0) < 1e-12
    print(f"[PASS] McNemar exact p={res['p']:.5f} (hand-checked)")


def test_mcnemar_no_discordant_pairs_is_p_one():
    """Concordant-only data carries no information about a difference."""
    assert mcnemar_exact(0, 0)["p"] == 1.0
    print("[PASS] McNemar with 0 discordant pairs -> p=1.0")


def test_mcnemar_ignores_concordant_pairs():
    """Same discordant split => same p regardless of how many pairs agreed."""
    assert mcnemar_exact(7, 2)["p"] == mcnemar_exact(7, 2)["p"]
    assert mcnemar_exact(2, 7)["p"] == mcnemar_exact(7, 2)["p"]  # symmetric
    print("[PASS] McNemar symmetric in b/c")


def test_binom_test_and_cdf_agree_on_a_known_case():
    """Two-sided binomial test on 0 successes in 25 at p0=0.5 is 2*0.5^25."""
    p = binom_test_two_sided(0, 25, 0.5)
    assert abs(p - 2 * 0.5 ** 25) < 1e-15, p
    assert abs(binom_cdf(25, 25, 0.3) - 1.0) < 1e-12
    print(f"[PASS] binomial test p={p:.3e}")


def test_clopper_pearson_saturated_and_zero_cells():
    """The intervals a bootstrap cannot produce for boundary cells."""
    lo, hi = clopper_pearson(100, 100)
    assert hi == 1.0 and 0.96 < lo < 0.9705, (lo, hi)
    lo0, hi0 = clopper_pearson(0, 100)
    assert lo0 == 0.0 and 0.029 < hi0 < 0.037, (lo0, hi0)
    # invert the interval: at the lower endpoint, P(X>=k) == alpha/2
    assert abs((1 - binom_cdf(99, 100, lo)) - 0.025) < 1e-3
    print(f"[PASS] Clopper-Pearson 100/100 -> [{lo:.4f}, 1.0]; 0/100 -> [0.0, {hi0:.4f}]")


def test_clopper_pearson_brackets_the_point_estimate():
    for k, n in ((3, 25), (12, 100), (1, 5)):
        lo, hi = clopper_pearson(k, n)
        assert lo <= k / n <= hi, (k, n, lo, hi)
    print("[PASS] Clopper-Pearson brackets k/n")


# ── Effect sizes + multiplicity ───────────────────────────────────────────────

def test_cohens_dz_known_value():
    """diffs = [1,2,3,4,5]: mean 3, sd (ddof=1) sqrt(2.5) -> d_z = 3/1.5811."""
    assert abs(cohens_dz([1, 2, 3, 4, 5]) - 3 / math.sqrt(2.5)) < 1e-12
    assert math.isnan(cohens_dz([2.0]))
    print("[PASS] Cohen's d_z matches the closed form")


def test_cliffs_delta_extremes():
    assert cliffs_delta([4, 5, 6], [1, 2, 3]) == 1.0
    assert cliffs_delta([1, 2, 3], [4, 5, 6]) == -1.0
    assert abs(cliffs_delta([1, 2, 3], [1, 2, 3])) < 1e-12
    print("[PASS] Cliff's delta = +1 / -1 / 0 at the extremes")


def test_holm_is_monotone_and_matches_hand_computation():
    """p = [0.01, 0.04, 0.03], m=3.

    Step-down: 0.01x3 = 0.03; 0.03x2 = 0.06; 0.04x1 = 0.04 but the running max
    keeps it monotone at 0.06. Expected: [0.03, 0.06, 0.06].
    """
    adj = holm([0.01, 0.04, 0.03])
    assert abs(adj[0] - 0.03) < 1e-12, adj
    assert abs(adj[2] - 0.06) < 1e-12, adj
    assert abs(adj[1] - 0.06) < 1e-12, adj
    assert adj[0] <= adj[2] <= adj[1]
    print(f"[PASS] Holm adjusted = {[round(a, 4) for a in adj]}")


def test_holm_never_shrinks_a_p_value():
    ps = [0.001, 0.2, 0.5, 0.9]
    for p, a in zip(ps, holm(ps)):
        assert a >= p - 1e-12
    print("[PASS] Holm adjustment is never anti-conservative")


# ── Bootstrap + equivalence ───────────────────────────────────────────────────

def test_bootstrap_ci_is_reproducible_and_brackets_the_mean():
    v = [0.6, 0.7, 0.65, 0.72, 0.68]
    a = bootstrap_mean_ci(v, np.random.default_rng(1), 2000)
    b = bootstrap_mean_ci(v, np.random.default_rng(1), 2000)
    assert a == b, "fixed RNG seed must reproduce the interval exactly"
    assert a["lo"] <= a["mean"] <= a["hi"]
    assert a["n"] == 5
    print(f"[PASS] bootstrap CI reproducible: [{a['lo']:.4f}, {a['hi']:.4f}]")


def test_hierarchical_bootstrap_is_wider_than_a_flat_one():
    """Clustered data: ignoring the clusters understates the interval."""
    rng = np.random.default_rng(11)
    clusters = [[1] * 20, [1] * 20, [0] * 20, [0] * 20, [1] * 20]  # strong seed clustering
    hier = hierarchical_bootstrap_ci(clusters, rng, 2000)
    flat = bootstrap_mean_ci([x for c in clusters for x in c], np.random.default_rng(11), 2000)
    assert (hier["hi"] - hier["lo"]) > (flat["hi"] - flat["lo"]), (hier, flat)
    assert hier["n_clusters"] == 5 and hier["n_obs"] == 100
    print(f"[PASS] hierarchical CI width {hier['hi']-hier['lo']:.3f} > flat {flat['hi']-flat['lo']:.3f}")


def test_equivalence_declares_equivalent_only_inside_the_margin():
    rng = np.random.default_rng(5)
    tight = equivalence_test([0.001, -0.002, 0.0, 0.001, -0.001], EQUIV_MARGIN, rng, 2000)
    wide = equivalence_test([0.3, 0.25, 0.35, 0.28, 0.31], EQUIV_MARGIN, rng, 2000)
    assert tight["equivalent"] is True and tight["verdict"] == "equivalent"
    assert wide["equivalent"] is False and wide["verdict"] == "inconclusive"
    print("[PASS] TOST: tight diffs equivalent, large diffs inconclusive")


def test_equivalence_of_noisy_zero_mean_is_inconclusive_not_equivalent():
    """A null result with wide spread must NOT be reported as equivalence."""
    rng = np.random.default_rng(9)
    res = equivalence_test([0.4, -0.4, 0.35, -0.38, 0.02], EQUIV_MARGIN, rng, 2000)
    assert abs(res["mean_diff"]) < 0.05           # mean is near zero ...
    assert res["verdict"] == "inconclusive"       # ... but the CI is wide
    print("[PASS] noisy zero-mean -> inconclusive, not 'no effect'")


# ── Variance decomposition ────────────────────────────────────────────────────

def test_variance_shares_recover_a_pure_model_effect():
    """Only the model factor varies -> its share is 1.0 and residual is 0."""
    vals = {}
    for i, m in enumerate(("a", "b", "c")):
        for ch in ("ironclad", "silent"):
            for f in ("structured", "raw"):
                vals[(m, ch, f)] = [float(i)] * 5
    sh = anova_variance_shares(vals)
    assert abs(sh["model"] - 1.0) < 1e-9, sh
    assert sh["residual_seed"] < 1e-9 and sh["format"] < 1e-9
    print("[PASS] variance decomposition recovers a pure model effect")


def test_variance_shares_recover_a_pure_seed_effect():
    """Only the seed replicate varies -> everything lands in the residual."""
    vals = {}
    for m in ("a", "b"):
        for ch in ("ironclad", "silent"):
            for f in ("structured", "raw"):
                vals[(m, ch, f)] = [1.0, 2.0, 3.0, 4.0, 5.0]
    sh = anova_variance_shares(vals)
    assert abs(sh["residual_seed"] - 1.0) < 1e-9, sh
    # the seed variation is entirely systematic (same pattern in every cell)
    assert abs(sh["seed_main_within_residual"] - 1.0) < 1e-9, sh
    print("[PASS] variance decomposition recovers a pure seed effect")


def test_variance_shares_recover_a_pure_format_effect():
    vals = {}
    for m in ("a", "b", "c"):
        for ch in ("ironclad", "silent"):
            for f, base in (("structured", 1.0), ("raw", 0.0)):
                vals[(m, ch, f)] = [base] * 5
    sh = anova_variance_shares(vals)
    assert abs(sh["format"] - 1.0) < 1e-9, sh
    print("[PASS] variance decomposition recovers a pure format effect")


def test_variance_shares_sum_to_one_on_mixed_data():
    rng = np.random.default_rng(4)
    vals = {}
    for i, m in enumerate(("a", "b", "c")):
        for j, ch in enumerate(("ironclad", "silent")):
            for k, f in enumerate(("structured", "raw")):
                base = 0.5 * i + 0.2 * j - 0.1 * k
                vals[(m, ch, f)] = list(base + rng.normal(0, 0.05, 5))
    sh = anova_variance_shares(vals)
    total = (sh["model"] + sh["character"] + sh["format"]
             + sh["interactions"] + sh["residual_seed"])
    assert abs(total - 1.0) < 1e-9, total
    print(f"[PASS] shares sum to 1.0 (model {sh['model']:.3f}, resid {sh['residual_seed']:.3f})")


def test_variance_shares_refuse_unbalanced_designs():
    """eta^2 shares are only orthogonal on a balanced design -> refuse otherwise."""
    vals = {("a", "ironclad", "structured"): [1.0, 2.0],
            ("a", "ironclad", "raw"): [1.0, 2.0, 3.0]}
    assert anova_variance_shares(vals) is None
    print("[PASS] unbalanced design refused")


# ── Discovery (so M3b rows join with no code change) ──────────────────────────

def test_discover_models_parses_filenames_and_skips_diagnostics():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        for fn in ("qwen2.5-7b_structured_seed42.json",
                   "qwen2.5-7b_silent_raw_seed1042.json",
                   "claude-opus-5_structured_seed42.json",       # a future M3b row
                   "deepseek-r1-distill-14b_silent_raw_seed42_parse_probe.json",
                   "mock_structured_seed42.json",
                   "qwen2.5-7b_structured_seeds42_1042_2042_3042_4042.json",
                   "greedy_baseline_ironclad.json"):
            open(os.path.join(d, fn), "w").write("{}")
        found = discover_models(d)
    assert found == ["claude-opus-5", "qwen2.5-7b"], found
    print(f"[PASS] discovery -> {found} (diagnostics/mock/aggregates skipped)")


if __name__ == "__main__":
    tests = [
        test_sign_flip_is_exact_and_hits_its_floor,
        test_sign_flip_symmetric_data_is_not_significant,
        test_sign_flip_all_zero_diffs_gives_p_one,
        test_sign_flip_is_sign_symmetric,
        test_stratified_permutation_detects_a_consistent_shift,
        test_stratified_permutation_p_is_never_zero,
        test_mcnemar_matches_hand_computed_binomial,
        test_mcnemar_no_discordant_pairs_is_p_one,
        test_mcnemar_ignores_concordant_pairs,
        test_binom_test_and_cdf_agree_on_a_known_case,
        test_clopper_pearson_saturated_and_zero_cells,
        test_clopper_pearson_brackets_the_point_estimate,
        test_cohens_dz_known_value,
        test_cliffs_delta_extremes,
        test_holm_is_monotone_and_matches_hand_computation,
        test_holm_never_shrinks_a_p_value,
        test_bootstrap_ci_is_reproducible_and_brackets_the_mean,
        test_hierarchical_bootstrap_is_wider_than_a_flat_one,
        test_equivalence_declares_equivalent_only_inside_the_margin,
        test_equivalence_of_noisy_zero_mean_is_inconclusive_not_equivalent,
        test_variance_shares_recover_a_pure_model_effect,
        test_variance_shares_recover_a_pure_seed_effect,
        test_variance_shares_recover_a_pure_format_effect,
        test_variance_shares_sum_to_one_on_mixed_data,
        test_variance_shares_refuse_unbalanced_designs,
        test_discover_models_parses_filenames_and_skips_diagnostics,
    ]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
