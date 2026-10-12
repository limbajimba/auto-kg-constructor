"""Tests for extraction Pydantic models.

Validates roundtrip serialization and the Gemini constraint
that no fields have non-None default values.

Phase 1 models (outline) are still Pydantic — tested here.
Phase 2 is now schema-less (raw dicts) — no Pydantic models to test.
"""

from __future__ import annotations

from pydantic_core import PydanticUndefined

from proof.parser.models import (
    DocumentMetadata,
    DocumentOutline,
    OutlineEntry,
)


def test_outline_entry_roundtrip():
    entry = OutlineEntry(
        number="11",
        title="Basic Financial Instruments",
        level=2,
        page_start=100,
        page_end=120,
        parent_number=None,
        element_type="section",
    )
    data = entry.model_dump(mode="json")
    restored = OutlineEntry.model_validate(data)
    assert restored.number == "11"
    assert restored.parent_number is None


def test_document_outline_roundtrip():
    outline = DocumentOutline(
        metadata=DocumentMetadata(
            title="FRS 102",
            subtitle=None,
            version="January 2024",
            effective_date="2024-01-01",
            issuing_body="Financial Reporting Council",
            total_pages=400,
            document_type="standard",
        ),
        entries=[
            OutlineEntry(
                number="11",
                title="Basic Financial Instruments",
                level=2,
                page_start=100,
                page_end=120,
                parent_number=None,
                element_type="section",
            ),
        ],
    )
    data = outline.model_dump(mode="json")
    restored = DocumentOutline.model_validate(data)
    assert restored.metadata.title == "FRS 102"
    assert len(restored.entries) == 1


def test_no_default_values_in_phase1_models():
    """Verify no Phase 1 model fields have non-None default values.

    Gemini's response_schema does not support Pydantic defaults.
    Fields must be either required (PydanticUndefined) or Optional (default=None).
    """
    models = [
        OutlineEntry,
        DocumentMetadata,
        DocumentOutline,
    ]
    for model_cls in models:
        for name, field_info in model_cls.model_fields.items():
            default = field_info.default
            assert default is PydanticUndefined or default is None, (
                f"{model_cls.__name__}.{name} has default={default!r} — "
                f"not supported by Gemini response_schema"
            )


def test_json_schema_generation():
    """Verify JSON schemas can be generated (what Gemini receives)."""
    schema1 = DocumentOutline.model_json_schema()
    assert "properties" in schema1
    assert "metadata" in schema1["properties"]
    assert "entries" in schema1["properties"]


def test_schema_spec_roundtrip():
    """Test SchemaSpec to_dict / from_dict roundtrip."""
    from proof.schema import EdgeTypeSpec, NodeTypeSpec, SchemaSpec

    spec = SchemaSpec(
        node_types=[
            NodeTypeSpec(name="Document", description="Root", properties=["title"]),
            NodeTypeSpec(name="Section", description="A section", properties=["number"]),
        ],
        edge_types=[
            EdgeTypeSpec(name="HAS_PART", description="Hierarchy", properties=["order"]),
        ],
    )
    data = spec.to_dict()
    restored = SchemaSpec.from_dict(data)
    assert len(restored.node_types) == 2
    assert len(restored.edge_types) == 1
    assert restored.node_types[0].label == "Document"
    assert restored.edge_types[0].rel_type == "HAS_PART"


def test_schema_spec_prompt_fragment():
    """Test that to_prompt_fragment produces useful text."""
    from proof.schema import EdgeTypeSpec, NodeTypeSpec, SchemaSpec

    spec = SchemaSpec(
        node_types=[NodeTypeSpec(name="Paragraph", description="A paragraph", properties=["text"])],
        edge_types=[EdgeTypeSpec(name="REFERENCES", description="A ref")],
    )
    fragment = spec.to_prompt_fragment()
    assert "Paragraph" in fragment
    assert "REFERENCES" in fragment
    assert "text" in fragment
