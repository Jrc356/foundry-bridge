# Explanation Reference

Explanation is a **discursive treatment of a subject** — it steps back, takes a wider view, and helps the reader build genuine understanding.

**Purpose**: Deepen and broaden understanding. The reader comes here when they want to *reflect*, not when they need to act.

## Section Structure

```markdown
# About [Topic]
# Or: [Topic] — background and context
# Or: Understanding [Topic]
# Or: Why [Topic] works the way it does

Opening statement of what this document illuminates and why it matters.

## Background / History
How did this come to be? What problem does it solve? What was tried before?

## How it works (conceptually)
Explain the underlying model, without being a reference manual.
Use analogies. Draw connections to other concepts.

## Design decisions and trade-offs
Why were certain choices made? What alternatives exist? What are the costs?

## Common misconceptions
Address popular misunderstandings about this topic.

## Implications for your work
(Optional) How does understanding this change how a practitioner approaches their work?

## Further reading
- Links to relevant tutorials for hands-on experience
- Links to reference for specifics
- Links to how-to guides for task guidance
- External resources
```

## Key Principles

- **Topic-oriented**: Explanation is "about" something — titles can have an implicit "About" in front of them ("About authentication", "About database connection pooling")
- **Reflect, don't instruct**: This is read away from the active task — while commuting, in a planning session, not while doing
- **Make connections**: Weave together concepts, history, related topics, implications — that's the whole point
- **Admit opinion and perspective**: Explanation can and should present informed opinions, design rationales, trade-off judgements
- **Consider alternatives**: Unlike a tutorial (single golden path), explanation can discuss different approaches and their merits
- **Provide context and background**: Design decisions, historical reasons, technical constraints, analogies
- **Keep it closely bounded**: Don't let it absorb instructions or reference material — link to those instead

## Language Patterns

| Pattern | Example |
|---|---|
| Explain causality | `The reason for X is because historically, Y…` |
| Offer judgement | `Approach W is better than Z in this context, because…` |
| Build analogies | `An X in system Y is analogous to a W in system Z. However…` |
| Weigh alternatives | `Some teams prefer W (because Z). This can work well, but it introduces…` |
| Reveal hidden structure | `An X interacts with a Y as follows: internally, when A happens, B is triggered because…` |
| Frame the topic | `Understanding connection pooling means understanding that database connections are expensive to create…` |

## What to Exclude

- ❌ Step-by-step instructions (that's a how-to guide)
- ❌ API documentation or reference tables (that's reference)
- ❌ Tutorial-style guided exercises (that's a tutorial)
- ❌ Pure feature announcements with no conceptual depth

## Signals That You're Writing Explanation

You're writing explanation if you find yourself:
- Using "because", "the reason", "historically", "the trade-off is"
- Discussing design decisions made by creators of the system
- Drawing analogies to concepts outside the immediate system
- Weighing alternatives ("you could do X or Y; X makes sense when…")
- Addressing the question "why does this work this way?"
- Writing content someone would read *before* starting a project, or *after* struggling to understand something
