---
name: diataxis-docs
description: "Write technical documentation following the Diátaxis framework. Use when: writing docs, creating tutorials, writing how-to guides, writing reference docs, writing explanation or conceptual guides, auditing existing documentation, classifying doc type, structuring documentation. Produces well-formed documentation organized into the four Diátaxis quadrants: tutorials (learning-oriented), how-to guides (task-oriented), reference (information-oriented), explanation (understanding-oriented)."
argument-hint: "Describe what you want to document, or paste existing doc content to audit"
---

# Diátaxis Documentation Skill

Documentation that serves users well must serve their actual needs. Diátaxis identifies four distinct user needs and four corresponding documentation forms. Mixing them degrades all of them.

## Step 1 — Classify the Documentation Need

Ask (or infer from context): What does the user need right now?

| If the user needs to… | Write a… |
|---|---|
| **Learn** — build new skill/familiarity with a product | **Tutorial** |
| **Accomplish** — complete a specific task or solve a problem | **How-to guide** |
| **Look up** — find accurate facts, API details, options | **Reference** |
| **Understand** — grasp concepts, context, design decisions | **Explanation** |

If asked to audit existing docs, check each section against this table and flag any mixing of types.

## Step 2 — Apply the Right Form

| Quadrant | Oriented | Serves | Analogy |
|---|---|---|---|
| Tutorial | Learning | Study | Cooking lesson with a child |
| How-to guide | Task/Goal | Work | A recipe |
| Reference | Information | Work | Nutritional label on food packaging |
| Explanation | Understanding | Study | Harold McGee's *On Food and Cooking* |

Load the relevant reference file for detailed principles:
- Tutorials → [./references/tutorials.md](./references/tutorials.md)
- How-to guides → [./references/how-to-guides.md](./references/how-to-guides.md)
- Reference guides → [./references/reference-guides.md](./references/reference-guides.md)
- Explanation → [./references/explanation.md](./references/explanation.md)

## Step 3 — Draft or Audit

### Writing new documentation

1. Confirm quadrant classification (Step 1)
2. Load the corresponding reference file (Step 2)
3. Use the section structure from that reference
4. Apply the language patterns from that reference
5. Check the "What to exclude" anti-patterns before finalising

### Auditing existing documentation

1. Read the content
2. Identify which quadrant it belongs to by its *intent*
3. Flag content that belongs to a different quadrant as misplaced
4. Suggest splitting documents that serve multiple needs
5. Suggest restructuring using the right section templates

## Step 4 — Quality Check

Before delivering any documentation, verify:

- [ ] **Single purpose**: Does every paragraph serve only one quadrant's intent?
- [ ] **No mixing**: Are tutorials free of reference dumps? Are how-to guides free of explanation? Are reference guides free of instructions?
- [ ] **User-oriented framing**: Is the title and opening sentence framed around the user's need, not the tool?
- [ ] **Correct language patterns**: Does the writing style match the quadrant? (See each reference file for language patterns)
- [ ] **Clear scope**: Does the document have a well-defined start and end point?

## Common Anti-patterns to Catch

| Anti-pattern | Problem | Fix |
|---|---|---|
| Tutorial that dumps API docs | Mixes learning with reference | Move API details to a reference guide; link from tutorial |
| How-to titled "Introduction to X" | Masquerading as tutorial | Either rewrite as actual lesson or rename/reframe as task-oriented |
| Reference guide with step-by-step instructions | Mixes information with task guidance | Move steps to a how-to guide; reference guide only describes |
| Explanation buried inside a tutorial | Disrupts the learning flow | Move to a separate explanation doc; add brief link from tutorial |
| "Learn how to X" framing in how-to guide | Tutorial language in wrong place | Reframe: "How to X" assumes existing competence |
