"""Proof-of-concept configuration.

All paths, settings, and tunables in one place.
Reads from environment variables with sensible defaults.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPORA_DIR = PROJECT_ROOT / "corpora"
PROOF_DIR = PROJECT_ROOT / "proof"
OUTPUT_DIR = PROOF_DIR / "outputs"

# --- Document under test ---
FRS102_PDF = CORPORA_DIR / "frs102.pdf"
FRS102_DOWNLOAD_URL = (
    "https://www.frc.org.uk/documents/7668/FRS_102_September_2024_tmKYWO6.pdf"
)

# --- Neo4j ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "changeme")

# --- Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "4"))
GEMINI_RETRY_BASE_SECONDS = float(os.getenv("GEMINI_RETRY_BASE_SECONDS", "2.0"))

# --- Parsing ---
PARSE_TIMEOUT_SECONDS = int(os.getenv("PARSE_TIMEOUT_SECONDS", "1800"))  # 30 min max
MAX_PDF_SIZE_MB = int(os.getenv("MAX_PDF_SIZE_MB", "50"))
PARSE_CACHE_DIR = OUTPUT_DIR / "cache"
MAX_PAGES_PER_CHUNK = int(os.getenv("MAX_PAGES_PER_CHUNK", "10"))

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
