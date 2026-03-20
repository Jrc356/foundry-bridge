# How-to Guides Reference

A how-to guide is a **recipe** — it guides an already-competent user through accomplishing a specific, real-world goal or solving a real-world problem.

**Purpose**: Help the user get something done, correctly and safely. Assume they know what they want.

## Section Structure

```markdown
# How to [verb phrase describing the goal/problem]
# Examples:
#   How to configure reconnection back-off policies
#   How to integrate application performance monitoring
#   How to migrate from v1 to v2

Brief statement of what this guide achieves and when to use it.
"This guide shows you how to…"

## Prerequisites
- Assumed knowledge or prior setup

## [Step or Phase 1]
Instruction focused on the action.

## [Step or Phase 2]
…

## [Conditional/branching section — if applicable]
If you are doing X, then…
If instead you need Y, then…

## Related
- Links to reference for full options
- Links to explanation for deeper understanding
```

## Key Principles

- **Goal-oriented title**: The title should be a real-world task: "How to X". Not a topic "X Configuration".
- **Assume competence**: The reader knows what they're doing; you don't need to teach basics
- **Address real-world complexity**: Guides can fork, branch, or have multiple entry/exit points
- **Action and only action**: Cut anything that isn't contributing to accomplishing the goal
- **Omit the unnecessary**: Unlike a tutorial, it doesn't need to be complete end-to-end
- **Seek flow**: Order steps to match how a human actually thinks and acts through the task
- **Link, don't inline**: Reference docs for full options, explanation docs for context — don't inline either

## Language Patterns

| Pattern | Example |
|---|---|
| Opening | `This guide shows you how to deploy a Django application to AWS ECS.` |
| Conditional imperatives | `If you want to enable caching, set CACHE_BACKEND to redis.` |
| Direct instructions | `To deploy, run: make deploy` |
| Point outward | `Refer to the [CLI reference](../reference/cli.md) for a full list of flags.` |
| Assume knowledge | (Don't explain what a migration is; just say "run the migration") |

## What to Exclude

- ❌ Teaching or explaining concepts from scratch (that's a tutorial or explanation)
- ❌ Full reference tables of every option (that's reference — link to it)
- ❌ "In this guide you will learn…" framing (that's tutorial language)
- ❌ Exhaustive coverage of every edge case (address the common real-world cases; acknowledge complexity)
- ❌ Background/history/context (that's explanation — link to it)

## Naming Guide

| Good | Bad | Why bad |
|---|---|---|
| How to integrate APM | Integrating APM | Ambiguous — is it a how-to or an explanation? |
| How to configure TLS | TLS Configuration | Sounds like reference |
| How to migrate from v1 to v2 | Migration guide | Too vague about what the guide does |
