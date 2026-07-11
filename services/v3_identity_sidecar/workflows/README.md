# ComfyUI Workflow Contract

Export the identity workflow from ComfyUI using **Save (API Format)** and place
the JSON file in this directory. The gateway replaces structured tokens inside
the JSON before sending it to ComfyUI.

Required identity workflow tokens:

```text
${prompt}
${reference_0}
```

Optional tokens:

```text
${negative_prompt}
${reference_1}
${reference_2}
${seed}
${width}
${height}
${quality}
${input_fidelity}
```

A repair workflow must additionally contain:

```text
${canvas}
${mask}
```

Tokens may be exact typed values or embedded in strings. For example, a
PhotoMaker class-word trigger may use:

```json
{"text": "${prompt}, person img"}
```

The gateway checks all `class_type` values against ComfyUI `/object_info` before
advertising identity capability. It cannot infer whether an arbitrary graph
actually preserves identity, so `IDENTITY_CONDITIONING_CONFIRMED` must also be
set by an operator after a real workflow review. Local repair has a separate
confirmation gate.

Do not commit production workflow files containing private URLs, credentials,
or proprietary model identifiers. Keep the ComfyUI input volume ephemeral or
apply a retention policy because ComfyUI's standard upload route stores input
files on its own volume.
