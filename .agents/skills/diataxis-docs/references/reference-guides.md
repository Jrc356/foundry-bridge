# Reference Guides Reference

A reference guide is a **map** — it describes the machinery accurately, completely, and neutrally so users can consult it while working.

**Purpose**: Provide truth and certainty. The user consults reference; they don't read it cover to cover.

## Section Structure

```markdown
# [Component/API/Command Name]

One-line description of what this is.

## Syntax / Signature
```
command [options] <required-arg>
```

## Parameters / Options / Fields

| Name | Type | Default | Description |
|---|---|---|---|
| `param_name` | string | `"default"` | What it does. |

## Return value / Output
Description of what is returned or produced.

## Errors / Exceptions
List known error conditions and what triggers them.

## Examples
Brief usage examples that illustrate the interface (not tutorials).

## See also
- Links to relevant how-to guides for task guidance
- Links to related reference entries
```

## Key Principles

- **Describe and only describe**: Neutral, factual, authoritative — no opinions, no instructions
- **Austere style**: Don't try to be entertaining; consistency and precision matter more
- **Mirror the structure of the machinery**: Organise reference docs the same way the product is organised
- **Complete within scope**: Within its defined scope, reference must be complete ("sub-commands are: a, b, c, d")
- **Adopt standard patterns**: Use consistent table formats, heading levels, and terminology throughout
- **Provide examples as illustration**: Short snippets that show usage — not step-by-step workflows
- **Auto-generation is valuable**: API docs can and should be generated from code where possible

## Language Patterns

| Pattern | Example |
|---|---|
| State facts | `Django's default logging configuration inherits Python's defaults.` |
| List exhaustively | `Available flags: --verbose, --dry-run, --force, --output` |
| State constraints | `You must use option A. You must not apply B unless C. Never use D in production.` |
| Describe behaviour | `When no config file is found, the command exits with code 1.` |
| Provide context via example | `# Example: connecting to a replica set` followed by a code block |

## What to Exclude

- ❌ Step-by-step instructions (that's a how-to guide)
- ❌ Tutorials or worked examples with narrative
- ❌ Conceptual explanation of why things are designed a certain way (that's explanation)
- ❌ Opinions or recommendations ("we recommend…") — unless as a clearly labelled note
- ❌ Marketing language or subjective claims

## Structure Variants by Type

| Reference type | Typical structure |
|---|---|
| CLI command | Syntax, flags/options table, exit codes, examples |
| REST API endpoint | Method + path, request params, request body, response schema, error codes, example |
| Class / Function | Signature, parameters, return type, raises, example |
| Configuration file | Key, type, default, valid values, description |
| Glossary | Term, definition, cross-references |
