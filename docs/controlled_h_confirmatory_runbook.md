# Controlled-H Qwen3 confirmation

> **2026-09-08 supersession:** allocation 10611 ended after one saved smoke
> response. Do not execute the historical interactive/same-server continuation
> below. See `docs/controlled_h_batch_amendment.md` for the separately versioned
> batch amendment and its validation status. Preserve the original evidence.


Frozen 2026-09-07 before model inference. The separately audited expansion
contains 504 fixtures, 252 per character (63 sensitive and 189 controls).
`configs/controlled_h_v2_confirmatory.json` binds source hashes, implementation,
inference, failure handling, and analysis. Its canonical digest is
`76bf7f917b46ffbe7d6deab859b961a28e4251e4cf875a17e12828d0795de1da`.
The original pilot remains NO-GO. This freeze does not authorize compute.

CSIS-specific source transfer, interactive allocation, and retrieval commands
are in `cluster/CSIS_CONTROLLED_H_CONFIRMATORY.md`. Keep smoke and full run
in the same allocation; the current freeze has no cross-job restart path.

## Estimand and gates

Qwen3-32B, pinned revision and serving stack, structured prompts, H=1/2/4/8,
one response per fixture/H: 2,016 slots total. A hash-ranked Latin rotation
balances horizon position within character. All 252 H8-minus-H1 pairs remain
in each character's estimate. Effective quality is the stored normalized
quality for parse/schema/legal, nontruncated responses and zero otherwise.
Raw responses, scores, and conditional regret denominators remain available.
Transport or ambiguous slots receive zero for accounting and block claims.

Each primary test uses 100,000 fixed-seed within-stratum bootstrap resamples,
weights .25/.75, a common-mean centered-null two-sided test with plus-one p,
and a basic 97.5% interval with nearest-rank quantiles. Two character tests
use alpha .025 each (Bonferroni familywise .05). H slopes and stratum/horizon
summaries are exploratory. The null is zero; .10 is the planning effect.

The reproduced pilot-upper-SD planning calculation requires N=191 Ironclad
and N=251 Silent at this alpha, against 252 available each. This normal
approximation does not calibrate bootstrap power, guarantee joint power, or
power other models/formats. Both character interface gates must pass:
parse/legal >=.95 overall and >=.90 in each H cell; overall truncation <=.01;
zero execution failures. Incomplete and mock runs cannot support claims.
Exact quality boundaries and near-zero paired/bootstrap variance suppress
claims pending an independent per-sample and degenerate-policy audit. There
is intentionally no automatic audit override.

## Offline validation

Run from the repository root; sources must retain their frozen result bytes.

```powershell
python scripts/controlled_horizon_confirmatory.py --provider mock --phase smoke --out results/controlled_h_v2_confirmatory_mock.json
python scripts/controlled_horizon_confirmatory.py --provider mock --phase run --out results/controlled_h_v2_confirmatory_mock.json
python scripts/controlled_horizon_confirmatory_analysis.py --report results/controlled_h_v2_confirmatory_mock.json --out results/controlled_h_v2_confirmatory_mock_analysis.json
```

Omit `--report` for a source/power preflight only. Analysis reconstructs all
prompts, re-parses each response, and recomputes scores before summarizing.
The source receipt normalizes CRLF/LF, and replaces only the runner's own
protocol-digest literal with a sentinel to avoid a hash cycle. No other
implementation changes are allowed without a new documented freeze.

## Real execution after explicit authorization

The Linux serving environment must have the pinned vLLM and transformers
versions. Copy all frozen sources and exact implementation there first.
Run the server in the allocated job using the launcher below. Keep its
receipt and logs private under ignored `results/`; the launcher requires
an unused receipt path and records its exact command before replacing itself.

```bash
python scripts/controlled_horizon_confirmatory_server.py --receipt results/controlled_h_v2_confirmatory_server.json --authorize-model-inference
```

Once that server is ready, run the one-query smoke from the same host and
checkout. Add `--cluster-compute` to both invocations if using a cluster.
The flags record authorization; documentation containing these commands is
not authorization to execute them.

```bash
python scripts/controlled_horizon_confirmatory.py --provider local --phase smoke --server-receipt results/controlled_h_v2_confirmatory_server.json --authorize-model-inference --out results/controlled_h_v2_confirmatory_qwen3_32b.json
python scripts/controlled_horizon_confirmatory.py --provider local --phase run --server-receipt results/controlled_h_v2_confirmatory_server.json --authorize-model-inference --out results/controlled_h_v2_confirmatory_qwen3_32b.json
```

Inspect the smoke's saved response, legality, truncation, server logs, and
resource use before the second command. A failed smoke terminates this
protocol's inference eligibility: preserve it; do not create another
checkout/output to draw a replacement. The canonical real report path is
enforced. A changed server launch receipt or endpoint blocks continuation.
The Linux live process command is checked on each CLI invocation. This is
local operational attestation, not cryptographic proof of loaded weights;
the real stack smoke and server-log review remain required.

Each query has an in-flight marker, an immutable row file, and a manifest
checksum. Preserve the manifest and its `.rows` directory together. Known
transport failure records one failed slot and stops the invocation; completed
slots are never retried. A crash with an unsaved response blocks resume.
Resolve that slot using the same CLI arguments plus
`--resolve-pending-as-failure`; this makes no model call and does not need
the authorization flag or a live server. Preserve the original receipt.
Resolution produces a zero-quality ambiguous slot and blocks inference
claims even if subsequent slots are completed. Do not delete checkpoints.

After completion retrieve the manifest, every row, server receipt/log, and
source receipts. Run the same analysis command against the real report,
then obtain independent per-sample review before adding manuscript claims.
This single-model confirmation is one step toward the main-track program;
multi-family replication and controls remain separate work.

## Prompt preparation and comparability

The full-release mock exposed a dynamic-cost side effect in the pilot
helper: serializing the first H could refresh Eviscerate's cost only after
the hand had been printed. Confirmation reconstructs the fixture and
enumerates legal actions before every H serialization, matching the
existing oracle audit's preparation. A released Silent fixture provides
the regression test. All H prompts must differ only in H after preparation.
Engine dynamics, oracle values, and scorer v2.1 are unchanged. Pilot bytes
and its NO-GO remain historical evidence; do not pool its responses with
this separately labelled prompt-preparation contract. Pilot variance is
used only as an explicitly approximate planning input.

Independent comparison found all 120 saved pilot prompts byte-equivalent
under this preparation. The pilot variance remains usable for approximate
planning; this does not relax the prohibition on response pooling. Offline
validation completed 2,016 mock slots and replayed every score; all 209 tests
and four standard mock pipelines passed. Real Linux serving remains untested.
