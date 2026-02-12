"""Shared fixtures for AI Extraction Pipeline tests."""

import io
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add templates to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "templates"))

from database_models import Base


# ---------------------------------------------------------------------------
# Image fixtures
# ---------------------------------------------------------------------------

def _make_image(width: int, height: int, mode: str = "RGB") -> bytes:
    """Create a test image and return its bytes."""
    img = Image.new(mode, (width, height), color="red")
    buf = io.BytesIO()
    fmt = "PNG" if mode in ("RGBA", "P") else "JPEG"
    if mode == "P":
        img = img.convert("P")
    img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture
def large_rgb_image():
    """2048x1536 RGB image (larger than MAX_IMAGE_WIDTH)."""
    return _make_image(2048, 1536, "RGB")


@pytest.fixture
def small_rgb_image():
    """800x600 RGB image (smaller than MAX_IMAGE_WIDTH)."""
    return _make_image(800, 600, "RGB")


@pytest.fixture
def rgba_image():
    """1200x900 RGBA image with transparency."""
    return _make_image(1200, 900, "RGBA")


@pytest.fixture
def palette_image():
    """1200x900 palette-mode image."""
    return _make_image(1200, 900, "P")


# ---------------------------------------------------------------------------
# Temp file fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_image_file(large_rgb_image):
    """Write a test image to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(large_rgb_image)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def tmp_pdf_file():
    """Write minimal PDF bytes to a temp file."""
    content = b"%PDF-1.4 minimal test content"
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(content)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def tmp_audio_file():
    """Write dummy audio bytes to a temp file."""
    content = b"\x00" * 1024  # dummy bytes
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(content)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def tmp_txt_file():
    """Write a .txt file (unsupported type)."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"hello")
        path = f.name
    yield path
    os.unlink(path)


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    """Create an in-memory SQLite database and return a session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# Mock LLM client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_gemini_response():
    """A mocked Gemini API response."""
    response = MagicMock()
    response.text = '{"field1": "test_value", "field2": 42, "field3": "2024-01-15"}'
    response.usage_metadata.prompt_token_count = 1000
    response.usage_metadata.candidates_token_count = 100
    return response
