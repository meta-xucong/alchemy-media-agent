# Conjure Prompt Transformation Layer - Architecture (Codex Ready)

## 1. Overview
This document defines the **implementation-level architecture** for integrating a Conjure-style prompt transformation pipeline into V2.

It is designed for direct implementation using Codex.

---

## 2. System Goal
Transform a V2-generated base prompt into a higher-quality image-ready prompt using a deterministic multi-stage pipeline.

---

## 3. High-Level Architecture

```
User Input
   ↓
V2 Core Engine
   ↓
Base Prompt
   ↓
Conjure Transformation Layer
   ↓
Final Prompt
   ↓
Image Generation Engine
```

---

## 4. Module Breakdown

### 4.1 V2 Core (Existing System)
Responsible for:
- Intent parsing
- Template selection
- Base prompt generation

Output:
```
BasePrompt
```

---

### 4.2 Conjure Transformation Layer (New Module)
Responsible for multi-stage prompt optimization.

Pipeline:
```
expand → rewrite → refine → normalize
```

---

## 5. Mode System

### 5.1 Stable Mode
- Preserve structure
- Minimal modification
- No semantic drift allowed

### 5.2 Enhanced Mode (default)
- Full pipeline enabled
- Balanced transformation

### 5.3 Exploration Mode
- Allow semantic variation
- Generate multiple prompt candidates

---

## 6. Data Flow

### Input
```
BasePrompt (string)
```

### Processing
```
Step 1: expand
Step 2: rewrite
Step 3: refine
Step 4: normalize
```

### Output
```
FinalPrompt (string)
```

---

## 7. Functional Contracts

### expand(prompt)
Adds missing visual details:
- lighting
- environment
- texture
- composition hints

---

### rewrite(prompt)
Improves structure:
- reorder elements
- improve clarity
- convert to structured language

---

### refine(prompt)
Improves generation quality:
- remove ambiguity
- resolve conflicts
- align style consistency

---

### normalize(prompt)
Ensures format consistency:
- standard camera syntax
- standard lighting syntax
- ordering rules

---

## 8. Mode Routing Logic

```
if mode == stable:
    skip expand/rewrite/refine, only normalize

if mode == enhanced:
    run full pipeline

if mode == exploration:
    run pipeline + generate variants
```

---

## 9. Integration Contract with V2

### Input from V2
```json
{
  "prompt": "...",
  "style": "...",
  "scene": "..."
}
```

### Output to Image Engine
```
FinalPrompt: string
```

---

## 10. Implementation Notes (Codex Guidance)
- Each pipeline step MUST be a pure function
- No shared mutable state between steps
- Mode routing must be deterministic
- Output must always remain valid prompt string

---

## 11. Success Criteria
- Stable Mode: zero semantic drift
- Enhanced Mode: improved detail richness
- Exploration Mode: controlled diversity

---

## 12. Positioning
This module is a **post-processing transformation layer**, not a generator.
