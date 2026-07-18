# Doc163 — V3 Face-localized Identity Evidence and Non-identity Channel Suppression

Status: implementation complete; model-ready 2/3/5 serial evidence verified and provider-equivalent visual acceptance recorded.

## 1. Runtime finding

The formal Doc162 Professional front run completed all three GPT Image 2 candidates,
with valid Remote Brain plans, canonical prompt/reference parity and verified shared
Vision decisions. No candidate passed. The blocking evidence was consistent:

- same-person readability and overall visual quality were already high;
- every candidate copied the source garment even though wardrobe belonged to the
  current request;
- two candidates also copied the source hairstyle;
- one candidate retained an over-polished human finish.

Pixel inspection found that Doc161 isolation v2 was active, but both provider-only
identity derivatives still showed the source garment and hairstyle inside the retained
central region. The Provider therefore received stronger visual evidence for those
non-identity channels than the Brain-owned current direction.

This is an evidence-admission defect, not a prompt-strength defect and not a reason to
relax shared Vision.

## 2. Authority and scope

This document extends Doc93, Doc95, Doc96, Doc161 and Doc162. It is shared foundation
work. It applies to any identity-only portrait reference whose non-identity channels
remain prompt-owned, including adult portraits, child portraits, General, Photography
and Professional Mode.

It must not introduce a child, kidswear, wardrobe, hairstyle, studio or marketplace
branch. It must not add local creative language, negative-word stacks, regex prompt
inspection, a private Provider, a private reviewer or a second retry path.

## 3. Required correction

### 3.1 Face-localized evidence admission

When the resolved Doc93 policy says that a portrait reference owns identity geometry
but not hair, wardrobe, accessories, lighting, scene, camera, mood or finish:

1. locate the primary face with the existing ephemeral local face detector;
2. derive complementary feature-detail and face/head-geometry evidence around that
   detected face rather than around a fixed fraction of the full source frame;
3. preserve facial feature relationships, face outline, age direction and ears;
4. strongly neutralize pixels outside the face-local evidence region, especially hair
   styling, neck/shoulder clothing, background and source lighting;
5. suppress the full source frame exactly as before;
6. never modify the user's stored upload.

The detector result is an ephemeral crop aid. No embedding or biometric vector is
persisted. Public provenance records only whether face localization was applied and the
evidence profile version, never the detected coordinates.

If face localization is unavailable, the existing conservative crop remains available
for Standard compatibility. A formal Professional anchor preparation run must expose
that fallback in provenance and may not count as identity-channel isolation acceptance.

### 3.2 Explicit reference-owned channels remain unchanged

If the user explicitly assigns hair or appearance to the reference, the existing
preservation path remains authoritative. Face-local suppression must not erase an
explicitly locked source channel.

### 3.3 Brain and Provider responsibilities remain unchanged

Remote Brain still owns the final visual direction and canonical Provider prompt.
Provider materialization consumes the same frozen prompt and the admitted derivatives.
This correction changes only which source pixels are admissible as identity evidence.
It never compensates by appending local prompt text.

### 3.4 Review remains strict

Shared Vision continues to reject:

- source wardrobe, hair, scene or lighting over-inheritance;
- same-person or age drift;
- AI polish, plastic skin or generic stock-face finish;
- prompt-owned channel noncompliance.

No threshold is lowered. A retry remains a complete Brain rewrite driven by normalized
review evidence.

## 4. Acceptance matrix

Code acceptance requires:

1. prompt-owned portrait derivatives use a face-localized v3 profile when the detector
   is available;
2. derivative pixels below and outside the localized face no longer preserve source
   garment/background color;
3. feature-detail and geometry evidence remain distinct and retain facial color/detail;
4. explicit same-hair/appearance locks stay on the assigned-channel preservation path;
5. adult vertical, adult landscape and child/full-body regression fixtures prove the
   rule is general rather than scene-specific;
6. product and non-human references are unchanged;
7. provenance contains profile/applied/fallback truth but no face coordinates;
8. canonical prompt/reference parity, General/E-Commerce/Photography isolation and
   full V3 regression remain green.

Pixel acceptance is a new bounded Professional front run:

```text
3 candidates
→ shared Vision
→ at most one bounded repair for candidate 1
→ front winner only if verified and deliverable
```

Only after a front winner exists may the existing host proceed to three-quarter and
profile. Failed candidates and repairs remain append-only evidence; the gate is never
relaxed to force a winner.

## 5. Explicit non-goals

- no child/kidswear detector or prompt recipe;
- no aesthetic face template or forced complexion;
- no string/regex-based final-prompt validator;
- no local prompt or negative-prompt patch;
- no change to user intent, reference ownership or product truth;
- no claim that a code pass alone completes M5, Gate C/D or production activation.

## 6. First bounded rerun record

The first run on the v3 evidence profile produced three verified, passing front
candidates. The selected winner recorded same-person readability 0.8447, human realism
0.90, visual quality 0.94 and pose compliance 0.98. Shared Vision no longer reported
source wardrobe or hairstyle over-inheritance.

The run then exposed a separate serial-lineage transport defect before the
three-quarter Provider call:

- the root and reviewed front winner were both analysed as competing hard
  `face_reference` uploads;
- the selected winner carried its canonical output ID only inside metadata, while the
  Provider admission contract requires a top-level output binding;
- all three three-quarter operations therefore failed closed with zero pixels.

The correction keeps both references as hard identity evidence but marks the reviewed
winner as server-owned `prior_view_winner` lineage evidence, not a competing identity
claim. It also projects the canonical output ID, source type, use policy, strength and
provider requirement at the typed asset boundary. Ordinary multiple hard face uploads
still conflict. No prompt, Provider, reviewer or retry semantics change.
