"""Document parser package.

Re-exports the key types for convenient imports:
    from proof.parser import GeminiParser, ParseResult
"""

from proof.parser.gemini import GeminiParser
from proof.parser.models import (
    DocumentMetadata,
    DocumentOutline,
    OutlineEntry,
)
from proof.parser.protocol import ParseResult, ParserProtocol

__all__ = [
    "DocumentMetadata",
    "DocumentOutline",
    "GeminiParser",
    "OutlineEntry",
    "ParseResult",
    "ParserProtocol",
]
