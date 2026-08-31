# Research priorities

## P0 — required before any new submission

| Priority | Deliverable | Acceptance criterion | Cost |
|---|---|---|---|
| P0.1 | retire horizon curve, radar, overall scalar | generation fails closed; regression test passes | zero inference — done |
| P0.2 | reframe all current claims | no “nested horizon,” “full-run control,” “faithful,” or “optimal combat” claim | writing — in progress |
| P0.3 | shortcut audit | lookup, position, constant-answer baselines published | zero inference — lookup/removal done |
| P0.4 | result provenance schema | commit/config/controller/source per dimension | zero inference — done for future artifacts |
| P0.5 | statistical claim correction | C6 `NOT-IDENTIFIED`; task-specific C4/C7 language | zero inference — done |
| P0.6 | controlled-H infrastructure | same prompt/state/action/utility; exactness fails closed | zero inference — done |
| P0.7 | turn oracle exactness audit | node count and exact flag for every fixture | zero inference — done on current-code replay |
| P0.8 | manuscript supersession | current draft has explicit audit banner and corrected thesis | writing — pending |
| P0.9 | PTA workshop short paper | four-page anonymized, citation-checked PDF approved by 2026-09-04; submit by 2026-09-05 AoE | writing — active |

The immediate submission schedule and venue-policy boundaries live in
`docs/submission_plan.md`. A missed quality gate means fallback to an ICLR 2027
non-archival workshop, not a rushed PTA submission.

## P1 — decisive evidence

1. Build and pre-register 200 controlled-H fixtures (100/character), including a
   predeclared horizon-sensitive subset.
2. Run mock/greedy/exact baselines and oracle sizing.
3. Run one cheap open model smoke only after the exact stack passes.
4. Simulate power and authorize the registered inference matrix.
5. Create card-pick-v2 with blinded expert labels and prospective rollout validation.
6. Run full-agency versus default scripted-agency ablation on matched seeds.
7. Build an external simulator conformance suite and resolve severity-1 discrepancies.
8. Release complete future traces under schema 2.0+.

These items form the ICML 2027 main-track critical path. Internal freeze is
2027-01-15; official ICML dates are not yet published and will supersede the
provisional late-January planning dates.

## P2 — top-tier and community ceiling

- original-game or independently implemented transfer study;
- frontier proprietary comparator if user authorizes cost;
- multi-backbone controlled-H replication;
- public fixture challenge set with hidden test partition;
- container/lockfile, checksum manifest, archival DOI;
- stable leaderboard rules, submission validator, model-card requirements, and annual
  versioning inspired by durable shared tasks such as HASOC;
- independent external users reproducing the analysis.

## Stop/go gates

- **Stop horizon work** if fewer than 20% of model-blind fixtures change optimal action
  between H=1 and H=8.
- **Stop scaling claims** if the controlled-H slope is not replicated across at least
  two model families.
- **Stop synergy claims** if expert agreement or prospective utility is weak.
- **Stop full-run claims** if scripted assistance dominates the agency ablation.
- **Go top-tier** only with construct intervention, external validation, adequate
  power, complete traces, and a clean artifact audit.

## Compute authorization

No paid API, cluster, or limited frontier run is implied by this roadmap. Obtain user
authorization after the exact-stack smoke and power calculation.
