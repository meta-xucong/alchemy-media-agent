# Named Photographer Profile And Rights Governance

## 1. Purpose

Named photographer profiles are a deliberate product feature for users who
explicitly seek a recognizable photographer IP or photographic language. They
are not an LLM optimization choice.

This document governs catalog creation, frontend selection, runtime binding,
technique compilation, availability, audit and failure behavior.

## 2. Absolute Selection Boundary

```text
frontend catalog selection
  -> trusted explicit selection record
  -> catalog validation
  -> immutable PhotographerProfileBinding
  -> Brain applies authorized technique package
```

Forbidden activation paths:

```text
LLM guess from scene
LLM preference or recommendation
keyword match in free-text prompt
similarity to an uploaded image
historical profile from another project
provider suggestion
automatic A/B winner selection
silent fallback from an unavailable profile
```

The UI may recommend that the user browse the catalog, but it may not preselect
a named profile on the user's behalf.

## 3. Profile Kinds

The catalog supports distinct kinds:

```text
general
  Non-named General Photography default.

technique_archetype
  Non-named photographic language such as cinematic low-key portrait,
  soft-window documentary, minimalist still life or large-format landscape.

named_photographer
  User-visible profile associated with a named photographer and governed by
  explicit rights and availability metadata.
```

Technique archetypes may be selected automatically as internal technical
support for General Photography. `named_photographer` profiles may not.

## 4. Catalog Contract

Recommended profile record:

```python
class PhotographerProfile:
    profile_id: str
    profile_version: str
    profile_kind: str
    public_display_name: str
    public_description: str
    supported_scene_ids: list[str]
    supported_commission_ids: list[str]
    technique_package: PhotographyTechniquePackage
    forbidden_techniques: list[str]
    conflicts: list[str]
    rights_status: str
    availability_status: str
    allowed_regions: list[str]
    effective_from: str | None
    effective_until: str | None
    source_provenance: list[dict]
    review_owner: str
    reviewed_at: str
    metadata: dict
```

Catalog records are trusted, versioned configuration. They must not be created
or rewritten by the LLM at request time.

## 5. Rights And Availability States

Suggested operator-controlled values:

```text
rights_status:
  approved
  approved_with_constraints
  pending_review
  disabled

availability_status:
  active
  inactive
  expired
  region_restricted
  suspended
```

Only an allowed combination may appear as selectable and may validate at job
creation. Product and legal owners define the meaning and evidence for these
states outside LLM reasoning.

The runtime still revalidates an explicit selection when the job starts. A UI
cache is not sufficient availability authority.

## 6. Technique DNA Contract

A named profile is compiled into structured, observable photographic decisions:

```text
composition geometry
subject-to-environment relationship
camera position and perspective tendency
depth and focus behavior
motion treatment
light topology, quality and contrast ratio
exposure key and highlight behavior
palette and color response
tonal curve and black/white point behavior
texture, grain and microcontrast
subject direction and moment selection
retouch and print-finish behavior
scene-specific exclusions
```

The runtime must not depend only on appending the photographer's name to the
provider prompt. The technique package is the stable execution contract and the
review target.

## 7. Profile Compilation

Profile compilation follows this order:

1. Load the exact pinned catalog version.
2. Validate scene and commission compatibility.
3. Resolve profile constraints against user instructions and reference truth.
4. Keep identity, product, scene and explicit prompt channels authoritative.
5. Translate the authorized technique package into structured contributions.
6. Record omitted or weakened profile features and the reason.
7. Freeze the resulting package checksum in the activation plan.

The Brain may decide how to express an allowed technique for the current scene.
It may not add undocumented profile traits or select a different named profile.

## 8. Conflict Resolution

Priority:

```text
user safety and explicit prohibitions
hard reference truth and preservation contract
explicit current-job content requirements
selected named profile's authorized technique package
scene and commission defaults
General Photography fallback grammar
```

If a selected profile conflicts with the user's requested subject, identity or
scene truth, preserve truth and record the profile feature as constrained. Do
not alter the subject merely to make the style score higher.

If the selected profile is incompatible with the entire requested commission,
the UI should present a clear compatibility warning and require a user decision.
The LLM must not choose a replacement.

## 9. No Implicit Mixing

First-release rules:

```text
maximum named profiles per job: 1
automatic named-profile blending: forbidden
historical named-profile carryover: forbidden without current UI selection
retry profile switching: forbidden
```

Generic technical modules may support the selected profile, but they must not
secretly reconstruct another named profile.

## 10. Free-Text Photographer Names

If the user types a photographer name but does not choose a catalog profile:

1. Treat the text as non-authoritative for named-profile activation.
2. Preserve the user's full text in the job request.
3. Optionally return a frontend confirmation opportunity when an exact catalog
   match exists.
4. Until confirmed, run General Photography without a named profile.
5. Never convert fuzzy matching into an activation record.

This separates conversational intent recognition from the legal/product act of
selecting a named profile.

## 11. Failure Semantics

| Condition | Required behavior |
| --- | --- |
| No profile selected | Use General Photography |
| Valid explicit selection | Pin and use the selected profile |
| Selection source missing or non-UI | Reject named activation |
| Unknown profile ID | Block and report unavailable |
| Disabled/expired/restricted profile | Block and report reason category |
| Profile becomes unavailable before generation | Stop before provider call |
| Profile becomes unavailable after generation starts | Keep frozen run audit; follow operator policy, never switch profile |
| LLM outputs another profile ID | Ignore, audit and keep pinned selection |

Detailed rights metadata should remain internal. Beginner-facing errors should
be clear without exposing operator or legal notes.

## 12. Persistence And Continuation

Store internally:

```text
profile binding
catalog version
technique checksum
selection source
availability decision
activation plan ID
output and review linkage
```

A project may display the last used profile, but a new job must not silently
reuse it. The frontend may offer “use the same photographer again” as an
unselected control; the user must explicitly confirm it for the new action.

## 13. Review Contract

Named-profile review evaluates technique compliance, not name recognition alone.
It must inspect only declared dimensions, such as:

```text
composition tendency
lighting behavior
color and tone
camera relation
moment or subject direction
texture and retouch finish
```

Profile fidelity must not compensate for failures in identity, anatomy, object
truth, scene truth, artifacts or explicit user requirements.

Required issue families:

```text
named_profile_not_explicitly_selected
named_profile_binding_mismatch
named_profile_unavailable
named_profile_technique_underapplied
named_profile_technique_overapplied
named_profile_overrode_reference_truth
named_profile_changed_during_retry
```

Only active named-profile issue codes may influence retry.

## 14. Frontend Requirements

The frontend must:

1. Default to General Photography with no named profile selected.
2. Require a deliberate user action to choose a named profile.
3. Make the selected state visually unambiguous.
4. Show profile suitability and current availability in product language.
5. Allow the user to return to General Photography.
6. Clear or reconfirm incompatible selections when the scene changes materially.
7. Never preselect a named profile from prompt analysis, recommendation ranking,
   upload similarity, project history or experimentation results.

## 15. Audit And Acceptance

Every release of the profile catalog requires:

```text
catalog diff review
rights/availability review
technique package review
profile-specific test fixtures
frontend manual-selection verification
runtime binding verification
real-output visual review
rollback version
```

No named profile is production-ready solely because its prompt output looks
similar in one hand-picked example.
