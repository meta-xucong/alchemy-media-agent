# Body Garment Identity Continuity Correction Model

## Observed mismatch

The current Body Silhouette rendering contract requires the same top, bottom,
and footwear category across front, side, and rear outputs, but it does not
freeze the concrete garment identity. Real output review therefore observed
shorts with different color/material identities across views, and the shared
cross-view gate correctly rejected `garment_drift_between_views`.

## Owning boundary

This is a Body modeling-card presentation and renderer-execution contract
defect. The owning layers are:

1. the server-owned Body garment continuity contract;
2. the MCP renderer execution directive and its frozen handoff fingerprint;
3. the shared cross-view review instructions.

The Body morphology profile, Face identity references, slot authority, formal
receipt authority, and activation rules are not the owning layers.

## Minimal complete correction

New strict Body materializations freeze one request-scoped outfit identity:

- plain white short-sleeve cotton top with a crew-neck cut;
- light-blue lightweight denim shorts with a straight mid-thigh cut;
- plain white ankle socks;
- graphic-free surface and no extra layer.

View angle, pose, lighting, natural fabric folds, and natural occlusion remain
the only allowed garment variation. The typed identity is carried through the
renderer directive, handoff sanitizer, fingerprint, public-safe projection,
and cross-view review contract. The canonical Brain prompt remains unchanged.

The garment contract is presentation-only. It does not contain age, body
proportion, identity, source-image, or biometric data. The five admitted
six-year-old Body sources remain analysis-only and continue to be bound by the
separate `age_6_child_only` morphology profile. Teen, adult, inference-first,
ordinary, and non-Body paths do not inherit that profile or the Body
reference partition.

Historical v1 handoffs remain readable for append-only history, but new strict
Body materialization must use the v2 identity-bearing contract. A v1 contract
must never be silently upgraded or treated as proof of exact garment parity.
