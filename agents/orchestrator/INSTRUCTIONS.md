# Orchestrator — Operating Manual

You coordinate the full corpus-to-knowledge-graph pipeline.

## Pipeline Flow

```
raw documents
    ↓
[Docling parsing]           ← doc-parser module
    ↓
parsed_documents
    ↓
[corpus-profiler agent]     ← discovers patterns
    ↓
corpus_profile
    ↓
[pipeline-generator agent]  ← writes extraction code
    ↓
extraction_pipeline
    ↓
[kg-builder agent]          ← populates Neo4j
    ↓
knowledge_graph
    ↓
[validator agent]           ← quality check
    ↓
validation_report
    ↓
[mcp-server-generator]      ← if validation passes
    ↓
mcp_server
```

## Error Handling

- If corpus-profiler produces low-confidence patterns → flag for human review
- If pipeline-generator code fails tests → retry with error context
- If validator fails → analyze failures, route back to kg-builder or pipeline-generator
- Maximum 3 retry loops before escalating to human

## Execution Log

Every pipeline run produces an execution log with:
- Timestamp for each phase
- Agent inputs/outputs
- Metrics from each phase
- Final status
