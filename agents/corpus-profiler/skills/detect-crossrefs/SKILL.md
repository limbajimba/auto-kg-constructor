---
name: detect-crossrefs
description: >
  Detect and classify cross-reference patterns in a document corpus.
  Distinguishes internal, external, and ambiguous references.
---

# Detect Cross-Reference Patterns

Systematically find every way the document references other parts of itself or external documents.

## Reference Types

### Internal (within same document)
- Explicit: "see paragraph 12.3", "as set out in Section 5"
- Relative: "the preceding paragraph", "the following table"
- Named: "the recognition criteria in Section 2"

### External (to other documents)
- Standard references: "as defined in IFRS for SMEs"
- Legal references: "under Companies Act 2006 s.393"
- Regulatory references: "in accordance with SI 2015/980"

### Ambiguous (needs context to resolve)
- "the requirements of this section"
- "the accounting policy required by this FRS"
- "other relevant legislation"

## Method

1. Scan all text for reference-indicator phrases ("see", "refer to", "in accordance with", "as defined in", etc.)
2. Extract the full reference expression
3. Classify as internal/external/ambiguous
4. Derive regex patterns for each category
5. Test resolution: can the target be identified programmatically?

## Output

List of `CrossRefPattern` objects with pattern, example, and ref_type.
