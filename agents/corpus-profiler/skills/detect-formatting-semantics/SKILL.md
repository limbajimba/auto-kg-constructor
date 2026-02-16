---
name: detect-formatting-semantics
description: >
  Discover formatting conventions that carry semantic meaning.
  Maps visual formatting (bold, italic, indentation) to semantic categories
  (requirement, guidance, defined term, example).
---

# Detect Formatting Semantics

In many authoritative documents, formatting IS meaning. Bold text means "mandatory requirement."
Italic text means "defined term." This skill discovers those mappings.

## Common Patterns

| Formatting | Possible Semantic |
|-----------|------------------|
| **Bold** | Mandatory requirement, key principle |
| *Italic* | Defined term, emphasis, foreign term |
| Indented block | Example, application guidance |
| Grey/shaded box | Commentary, non-normative guidance |
| SMALL CAPS | Legal term, party name |
| Underline | Cross-reference, hyperlink |
| Numbered list | Sequential requirements |
| Bulleted list | Non-sequential options |

## Method

1. Sample 20+ sections from across the document
2. For each formatting type found, collect all instances
3. Analyze whether the formatting correlates with a semantic category
4. Assign confidence level (0-1) based on consistency
5. Cross-validate: does the same formatting always mean the same thing?

## Output

List of `FormattingSemantic` objects with formatting, semantic, and confidence.
