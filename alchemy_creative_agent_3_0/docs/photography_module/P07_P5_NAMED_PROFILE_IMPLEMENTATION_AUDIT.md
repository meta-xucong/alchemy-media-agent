# P5 Named Photographer Profile Implementation Audit

## 1. Status And Ownership

```text
phase: P5 named photographer catalog and UI integration
ownership: Photography specialized-template module + existing mainline contract
production Scenario Pack activation: still disabled
real-provider quality gate: pending (Doc103 remains paused)
```

This milestone does not add a second profile-selection API.  Mainline owns the
public catalog route, explicit frontend confirmation, validation, immutable
Job/Project binding and retry immutability.  Photography owns only
operator-reviewed technique-package records and compilation of the exact
binding that mainline already froze.

## 2. Implemented Boundary

`PhotographyProfileCatalog.shared_catalog()` projects eligible operator records
onto the foundation `PhotographerProfileCatalog` accepted by
`V3ProductApiService`.  A future composition root may inject that catalog; the
frontend must read the mainline endpoint, never a module-local list:

```text
GET /api/v3/creative-agent/scenarios/photography/photographer-profiles
```

The default Photography catalog contains General Photography only.  A named
record becomes eligible only when all of the following are true:

```text
profile_kind = named_photographer
rights_status = approved | approved_with_constraints
availability_status = active
```

No real photographer profile is shipped by this commit.  Adding one requires
an operator-reviewed rights, region, version and technique-package record; it
cannot be inferred from a prompt or created by the LLM.

## 3. Technique Compilation And Review

For an already explicit and immutable named binding, the compiler verifies:

```text
profile ID
profile version
technique package checksum
selection source = user_explicit_ui
```

It produces structured composition/camera/light/color/finish contributions
without inserting the photographer's name into a renderer prompt.  It never
selects, blends, replaces or changes a profile.

Reference-owned camera, lighting, composition, color or finish channels
constrain the corresponding named-package directions.  Identity, product,
scene and prompt-owned channels retain the ownership defined by Doc93.

The module review checks explicit binding, technique-binding match and
reference-truth precedence.  Its named-profile issue codes are additive; they
do not compensate for foundation quality or identity failures.  Any future
retry remains on the mainline frozen-plan path and must preserve the profile
binding.

## 4. Non-Human Identity Boundary

Animal scene direction and named-profile compilation do not contain a local
identity prompt, image comparison, Provider shortcut or retry.  An individual
animal reference must enter mainline with:

```text
role = nonhuman_identity_reference
```

The shared `nonhuman_subject_identity` capability supplies native high-fidelity
conditioning and its one bounded retry; unsupported/missing evidence blocks
instead of falling back to text.

## 5. Verification

```text
P1/P3/P4/P5 Photography plus mainline contract suite: 46 passed
```

The P5 tests cover shared-catalog projection, explicit binding, checksum and
version mismatch rejection, no profile name in prompt additions, reference
truth precedence, default no-named-profile behavior, and non-human isolation.

## 6. Remaining Gate

P6 must activate the Photography Scenario Pack through the existing central
runtime/composition root, inject the approved catalog, connect professional-set
continuation, and then complete Doc103's real-provider quality acceptance.
Until then this branch deliberately keeps the pack inactive and does not call
a Provider directly.
