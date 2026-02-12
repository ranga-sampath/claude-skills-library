"""Tests for templates/ui_components_streamlit.py

Streamlit components are tested by mocking the st module.
We focus on logic paths rather than visual rendering.

NOTE: The source module uses Python 3.10+ type syntax (X | Y).
      If running on Python <3.10, module import is skipped and tests
      are marked as such in the report.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Mock streamlit before importing the module
sys.modules["streamlit"] = MagicMock()

sys.path.insert(0, str(Path(__file__).parent.parent / "templates"))

# The source file uses `tuple[str, str] | tuple[None, None]` which requires
# Python 3.10+.  We attempt import and skip gracefully on older Python.
_IMPORT_ERROR = None
try:
    import ui_components_streamlit as ui
    from ui_components_streamlit import (
        ALLOWED_EXTENSIONS,
        MAX_FILE_SIZE_MB,
        render_file_uploader,
        render_rate_limit_status,
        render_extraction_error,
        render_extraction_metadata,
        render_extraction_flow,
        run_extraction_with_progress,
    )
except TypeError as exc:
    _IMPORT_ERROR = str(exc)
    # Provide fallback references so the file parses
    ui = None  # type: ignore
    ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "gif", "pdf", "mp3", "wav", "m4a"]
    MAX_FILE_SIZE_MB = 10

    def _noop(*a, **kw):  # type: ignore
        pass

    render_file_uploader = _noop
    render_rate_limit_status = _noop
    render_extraction_error = _noop
    render_extraction_metadata = _noop
    render_extraction_flow = _noop
    run_extraction_with_progress = _noop

needs_310 = pytest.mark.skipif(
    _IMPORT_ERROR is not None,
    reason=f"Source requires Python 3.10+ union syntax: {_IMPORT_ERROR}",
)


# =========================================================================
# 3.1  File Upload — render_file_uploader
# =========================================================================

@needs_310
class TestFileUploader:
    """Test file upload component logic."""

    def test_3_1_1_no_file_uploaded(self):
        import streamlit as st
        st.file_uploader.return_value = None

        path, name = render_file_uploader()
        assert path is None
        assert name is None

    def test_3_1_2_file_too_large(self):
        import streamlit as st
        mock_file = MagicMock()
        mock_file.size = 15 * 1024 * 1024  # 15MB
        mock_file.name = "big_file.jpg"
        st.file_uploader.return_value = mock_file

        path, name = render_file_uploader()
        st.error.assert_called()
        assert path is None
        assert name is None

    def test_3_1_3_valid_file_upload(self):
        import streamlit as st
        mock_file = MagicMock()
        mock_file.size = 1 * 1024 * 1024  # 1MB
        mock_file.name = "receipt.jpg"
        mock_file.getvalue.return_value = b"\xff\xd8" + b"\x00" * 100
        st.file_uploader.return_value = mock_file

        path, name = render_file_uploader()
        assert path is not None
        assert name == "receipt.jpg"
        # Clean up temp file
        if path:
            import os
            os.unlink(path)


# =========================================================================
# 3.2  Rate Limit Display
# =========================================================================

@needs_310
class TestRateLimitDisplay:
    """Test rate limit status rendering."""

    def test_3_2_1_limit_reached(self):
        import streamlit as st
        st.reset_mock()
        render_rate_limit_status(0, 20)
        st.warning.assert_called_once()

    def test_3_2_2_low_remaining(self):
        import streamlit as st
        st.reset_mock()
        render_rate_limit_status(3, 20)
        st.info.assert_called_once()

    def test_3_2_3_plenty_remaining(self):
        import streamlit as st
        st.reset_mock()
        render_rate_limit_status(15, 20)
        st.caption.assert_called_once()


# =========================================================================
# 3.3  Configuration Constants
# =========================================================================

@needs_310
class TestConfiguration:
    """Test UI configuration constants."""

    def test_3_3_1_allowed_extensions(self):
        expected = {"jpg", "jpeg", "png", "webp", "gif", "pdf", "mp3", "wav", "m4a"}
        actual = set(ALLOWED_EXTENSIONS)
        assert expected.issubset(actual)

    def test_3_3_2_max_file_size(self):
        assert MAX_FILE_SIZE_MB == 10


# =========================================================================
# 3.4  Extraction with Progress
# =========================================================================

@needs_310
class TestExtractionWithProgress:
    """Test extraction progress wrapper."""

    def test_run_extraction_calls_func(self):
        import streamlit as st
        mock_func = MagicMock(return_value="result")

        result = run_extraction_with_progress("/tmp/test.jpg", mock_func)
        mock_func.assert_called_once_with("/tmp/test.jpg")
        assert result == "result"


# =========================================================================
# 3.5  Error Display
# =========================================================================

@needs_310
class TestErrorDisplay:
    """Test error display component."""

    def test_render_error_shows_message(self):
        import streamlit as st
        st.reset_mock()
        render_extraction_error("Something went wrong")
        st.error.assert_called_once()
        call_arg = st.error.call_args[0][0]
        assert "Something went wrong" in call_arg


# =========================================================================
# 3.6  Metadata Display
# =========================================================================

@needs_310
class TestMetadataDisplay:
    """Test extraction metadata rendering."""

    def test_render_metadata_brief(self):
        import streamlit as st
        st.reset_mock()
        mock_result = MagicMock()
        mock_result.extraction_time_ms = 2500.0

        render_extraction_metadata(mock_result, show_details=False)
        st.caption.assert_called_once()

    def test_render_metadata_detailed(self):
        import streamlit as st
        st.reset_mock()
        mock_result = MagicMock()
        mock_result.extraction_time_ms = 2500.0
        mock_result.input_tokens = 1000
        mock_result.output_tokens = 100
        mock_result.cost_usd = 0.00014

        # st.columns returns mock columns
        mock_col1, mock_col2, mock_col3 = MagicMock(), MagicMock(), MagicMock()
        st.columns.return_value = [mock_col1, mock_col2, mock_col3]

        render_extraction_metadata(mock_result, show_details=True)
        st.columns.assert_called_once_with(3)
        mock_col1.caption.assert_called_once()
        mock_col2.caption.assert_called_once()
        mock_col3.caption.assert_called_once()
