---
name: detect-numbering
description: >
  Detect and classify numbering schemes in a document corpus.
  Produces regex patterns that match section/paragraph numbers.
---

# Detect Numbering Schemes

Given parsed document content, systematically identify all numbering patterns.

## Common Patterns to Check

1. **Decimal hierarchical**: `1.2.3`, `12.3A`, `12.3.1`
2. **Roman numeral parts**: `Part I`, `Part II`
3. **Letter suffixes**: `12.3A`, `12.3B` (inserted paragraphs)
4. **Chapter-based**: `Chapter 1`, `Ch. 1`
5. **Section-based**: `Section 12`, `s.12`
6. **Appendix-based**: `Appendix A`, `App. 1`

## Method

1. Extract all text that appears to be a heading or section marker
2. Cluster by pattern similarity
3. For each cluster, derive a regex
4. Validate the regex against the full document
5. Order patterns by hierarchy level (broadest → most specific)

## Output

List of `NumberingScheme` objects with pattern, example, and description.
