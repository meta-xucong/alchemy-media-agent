Prompt Transform Layer (Conjure Integration)

Overview
This module integrates a prompt transformation pipeline into V2 as an independent enhancement layer.

V2 defines intent and base prompt.
This layer improves prompt expression without changing meaning.

Architecture
User -> V2 -> Base Prompt -> Conjure Layer -> Final Prompt -> Image Model

Modes
1. Stable Mode
- minimal modification
- preserve structure

2. Enhanced Mode
- expand
- rewrite
- refine
- normalize

3. Exploration Mode
- allow variation
- generate multiple prompts

Pipeline
expand -> rewrite -> refine -> normalize

Rule
Do not change V2 intent, only improve expression.

Config
mode: stable / enhanced / exploration
max_variants: 3
