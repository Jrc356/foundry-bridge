# Tutorials Reference

A tutorial is a **lesson** — a learning experience led by the teacher (you), in which the student learns by *doing*.

**Purpose**: Help the user acquire skill and familiarity. Not to help them accomplish a task.

## Section Structure

```markdown
# [Title: "Build/Create/Get started with X"]

Brief statement of what the learner will achieve and what they'll encounter along the way.
Use "In this tutorial, we will…" — NOT "In this tutorial you will learn…"

## Prerequisites
- What the learner needs before starting

## [Step 1: Concrete action]
[Instructional step with expected visible result]

> You should see…  /  Notice that…

## [Step 2: Next concrete action]
…

## What you've built
Summary of the completed result — describe (and mildly admire) what they've accomplished.

## Next steps
- Links to relevant how-to guides, reference, or explanation
```

## Key Principles

- **Guide through doing**: Every step = a concrete action with a visible result
- **Show destination upfront**: Let the learner see where they're going from the start
- **Deliver results early and often**: Each step should produce something observable
- **Maintain narrative of expectations**: "You will notice…", "After a moment, you should see…"
- **Minimise explanation ruthlessly**: If you must explain, do it in one sentence and link to explanation docs
- **Ignore options and alternatives**: Stay on the one golden path to completion
- **Encourage repetition**: Make steps repeatable where possible
- **Use "we"**: First-person plural "We will now…" — teacher and learner together
- **Be reliable**: The tutorial must work every single time, for every user

## Language Patterns

| Pattern | Example |
|---|---|
| Describe what we'll do | `In this tutorial, we will build a secure login flow using JWT tokens.` |
| Action steps | `First, do x. Now, do y. Now that you have done y, do z.` |
| Set expectations | `The output should look something like…` |
| Confirm progress | `Notice that… / Remember that… / Let's check…` |
| Minimal explanation | `We use HTTPS here because it's more secure — see [Why HTTPS](../explanation/https.md) for details.` |
| Celebrate completion | `You have built a working three-layer authentication system.` |

## What to Exclude

- ❌ Full API reference tables
- ❌ Extended explanation of why things work
- ❌ Options and alternatives ("you could also…")
- ❌ "You will learn…" framing (presumptuous)
- ❌ Warnings about edge cases not relevant to the tutorial path
