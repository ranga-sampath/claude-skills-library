"""Tests for templates/ai_engine.py"""

import io
import os
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent / "templates"))

# Pre-mock google.genai so ai_engine can be imported without the real package
_mock_genai = MagicMock()
_mock_google = MagicMock()
_mock_google.genai = _mock_genai
sys.modules.setdefault("google", _mock_google)
sys.modules.setdefault("google.genai", _mock_genai)
sys.modules.setdefault("google.genai.types", MagicMock())

import ai_engine
from ai_engine import (
    ExtractionResult,
    _calculate_cost,
    _friendly_error,
    _get_mime_type,
    _parse_response,
    _resize_image_if_needed,
    extract_from_file,
    process_extracted_data,
)

# Rename import to avoid pytest collecting it as a test function
_test_api_connection = ai_engine.test_api_connection


# =========================================================================
# 1.1  _parse_response  — Multi-strategy JSON parser
# =========================================================================

class TestParseResponse:
    """Test the multi-strategy JSON response parser."""

    def test_1_1_1_direct_valid_json(self):
        result = _parse_response('{"merchant": "Starbucks", "total": 5.75}')
        assert result == {"merchant": "Starbucks", "total": 5.75}

    def test_1_1_2_json_in_markdown_code_block(self):
        text = '```json\n{"a": 1}\n```'
        assert _parse_response(text) == {"a": 1}

    def test_1_1_3_json_in_plain_code_block(self):
        text = '```\n{"a": 1}\n```'
        assert _parse_response(text) == {"a": 1}

    def test_1_1_4_json_embedded_in_text(self):
        text = 'Here is the result: {"a": 1} hope this helps'
        assert _parse_response(text) == {"a": 1}

    def test_1_1_5_completely_unparseable(self):
        result = _parse_response("I cannot process this image")
        assert "error" in result

    def test_1_1_6_empty_string(self):
        result = _parse_response("")
        assert "error" in result

    def test_1_1_7_nested_json(self):
        text = '{"items": [{"name": "A", "qty": 2}]}'
        result = _parse_response(text)
        assert result["items"] == [{"name": "A", "qty": 2}]

    def test_1_1_8_json_with_null_values(self):
        text = '{"field1": null, "field2": "value"}'
        result = _parse_response(text)
        assert result["field1"] is None
        assert result["field2"] == "value"

    def test_1_1_9_malformed_json_in_code_block(self):
        text = '```json\n{broken json}\n```'
        result = _parse_response(text)
        # Should fall through to strategy 3 or return error
        assert isinstance(result, dict)

    def test_1_1_10_multiple_json_objects(self):
        text = '{"a":1} some text {"b":2}'
        result = _parse_response(text)
        # Strategy 1 will fail, strategy 3 regex finds first match
        assert isinstance(result, dict)

    def test_1_1_11_unicode_characters(self):
        text = '{"name": "José García"}'
        result = _parse_response(text)
        assert result["name"] == "José García"

    def test_1_1_12_special_chars_in_values(self):
        text = '{"note": "price is $5.00 & tax"}'
        result = _parse_response(text)
        assert result["note"] == "price is $5.00 & tax"


# =========================================================================
# 1.2  _friendly_error  — Error translation
# =========================================================================

class TestFriendlyError:
    """Test user-friendly error message conversion."""

    def test_1_2_1_invalid_argument_image(self):
        msg = _friendly_error("invalid_argument: bad image data")
        assert "Could not process this image" in msg

    def test_1_2_2_invalid_argument_audio(self):
        msg = _friendly_error("invalid_argument: audio format error")
        assert "Could not process this audio" in msg

    def test_1_2_3_invalid_argument_generic(self):
        msg = _friendly_error("invalid_argument: something unexpected")
        assert "corrupted or in an unsupported format" in msg

    def test_1_2_4_rate_limited_429(self):
        msg = _friendly_error("Error 429: Too many requests")
        assert "temporarily busy" in msg

    def test_1_2_5_resource_exhausted(self):
        msg = _friendly_error("RESOURCE_EXHAUSTED: quota depleted")
        assert "temporarily busy" in msg

    def test_1_2_6_permission_denied_403(self):
        msg = _friendly_error("403 Forbidden")
        assert "permission" in msg.lower()

    def test_1_2_7_quota_exceeded(self):
        msg = _friendly_error("Quota limit reached for today")
        assert "quota" in msg.lower()

    def test_1_2_8_no_response_text(self):
        msg = _friendly_error("response has no text available")
        assert "unclear or unrecognizable" in msg

    def test_1_2_9_timeout_error(self):
        msg = _friendly_error("Request timeout exceeded after 30s")
        assert "timed out" in msg

    def test_1_2_10_unknown_error(self):
        msg = _friendly_error("Something completely new happened")
        assert "Could not process file:" in msg

    def test_1_2_11_empty_string(self):
        msg = _friendly_error("")
        assert "Could not process file:" in msg

    def test_1_2_12_case_sensitivity(self):
        msg = _friendly_error("INVALID_ARGUMENT: IMAGE data corrupt")
        assert "Could not process this image" in msg


# =========================================================================
# 1.3  _calculate_cost
# =========================================================================

class TestCalculateCost:
    """Test cost calculation accuracy."""

    def test_1_3_1_typical_extraction(self):
        # (1000 * 0.10 + 100 * 0.40) / 1_000_000 = 0.00014
        cost = _calculate_cost(1000, 100)
        assert abs(cost - 0.00014) < 1e-10

    def test_1_3_2_zero_tokens(self):
        assert _calculate_cost(0, 0) == 0.0

    def test_1_3_3_large_token_count(self):
        cost = _calculate_cost(1_000_000, 1_000_000)
        assert abs(cost - 0.50) < 1e-10

    def test_1_3_4_input_only(self):
        cost = _calculate_cost(500, 0)
        assert abs(cost - 0.00005) < 1e-10


# =========================================================================
# 1.4  _get_mime_type
# =========================================================================

class TestGetMimeType:
    """Test MIME type resolution."""

    def test_1_4_1_jpeg_image(self):
        assert _get_mime_type(".jpg", "image") == "image/jpeg"

    def test_1_4_2_png_image(self):
        assert _get_mime_type(".png", "image") == "image/png"

    def test_1_4_3_mp3_audio(self):
        assert _get_mime_type(".mp3", "audio") == "audio/mp3"

    def test_1_4_4_pdf_document(self):
        assert _get_mime_type(".pdf", "pdf") == "application/pdf"

    def test_1_4_5_unknown_extension(self):
        assert _get_mime_type(".xyz", "image") == "image/octet-stream"

    def test_1_4_6_case_sensitivity(self):
        assert _get_mime_type(".JPG", "image") == "image/jpeg"

    def test_1_4_7_wav_audio(self):
        assert _get_mime_type(".wav", "audio") == "audio/wav"

    def test_1_4_8_webp_image(self):
        assert _get_mime_type(".webp", "image") == "image/webp"

    def test_1_4_9_unknown_file_type(self):
        assert _get_mime_type(".png", "unknown") == "unknown/octet-stream"

    def test_1_4_10_m4a_audio(self):
        assert _get_mime_type(".m4a", "audio") == "audio/mp4"


# =========================================================================
# 1.5  _resize_image_if_needed
# =========================================================================

class TestResizeImage:
    """Test image optimization/resize logic."""

    def test_1_5_1_large_rgb_resized(self, large_rgb_image):
        data, mime = _resize_image_if_needed(large_rgb_image, ".jpg")
        img = Image.open(io.BytesIO(data))
        assert img.width <= 1024

    def test_1_5_2_small_image_not_resized(self, small_rgb_image):
        data, mime = _resize_image_if_needed(small_rgb_image, ".jpg")
        img = Image.open(io.BytesIO(data))
        assert img.width <= 800

    def test_1_5_3_rgba_converted_and_resized(self, rgba_image):
        data, mime = _resize_image_if_needed(rgba_image, ".png")
        img = Image.open(io.BytesIO(data))
        assert img.width <= 1024

    def test_1_5_4_palette_mode_converted(self):
        """Palette-mode image (1200px wide) is converted to RGB and resized."""
        img = Image.new("RGB", (1200, 900), "red")
        img = img.convert("P")  # Convert to palette mode
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        palette_data = buf.getvalue()

        data, mime = _resize_image_if_needed(palette_data, ".png")
        result_img = Image.open(io.BytesIO(data))
        assert result_img.width <= 1024

    def test_1_5_5_exact_max_width(self):
        img = Image.new("RGB", (1024, 768), "blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        data = buf.getvalue()

        result_data, mime = _resize_image_if_needed(data, ".jpg")
        result_img = Image.open(io.BytesIO(result_data))
        assert result_img.width <= 1024

    def test_1_5_6_corrupted_data_returns_original(self):
        corrupted = b"not_an_image_at_all"
        data, mime = _resize_image_if_needed(corrupted, ".jpg")
        assert data == corrupted

    def test_1_5_7_tiny_image(self):
        img = Image.new("RGB", (100, 100), "green")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        data = buf.getvalue()

        result_data, mime = _resize_image_if_needed(data, ".jpg")
        result_img = Image.open(io.BytesIO(result_data))
        assert result_img.width <= 100


# =========================================================================
# 1.6  extract_from_file
# =========================================================================

class TestExtractFromFile:
    """Test the main extraction function."""

    def _make_mock_gemini_response(self, json_text=None):
        """Helper to create a mock Gemini response."""
        resp = MagicMock()
        resp.text = json_text or '{"field1": "test_value", "field2": 42, "field3": "2024-01-15"}'
        resp.usage_metadata.prompt_token_count = 1000
        resp.usage_metadata.candidates_token_count = 100
        return resp

    def test_1_6_1_no_api_key(self, tmp_image_file):
        with patch.object(ai_engine, "_get_client", return_value=None):
            result = extract_from_file(tmp_image_file, api_key=None)
            assert result.error is not None
            assert "API key" in result.error or "not configured" in result.error

    def test_1_6_2_file_not_found(self):
        with patch.object(ai_engine, "_get_client", return_value=MagicMock()):
            result = extract_from_file("/nonexistent/file.jpg")
            assert result.error is not None
            assert "not found" in result.error.lower()

    def test_1_6_3_unsupported_file_type(self, tmp_txt_file):
        with patch.object(ai_engine, "_get_client", return_value=MagicMock()):
            result = extract_from_file(tmp_txt_file)
            assert result.error is not None
            assert "Unsupported" in result.error

    def test_1_6_4_successful_gemini_extraction(self, tmp_image_file):
        mock_response = self._make_mock_gemini_response()
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch.object(ai_engine, "LLM_PROVIDER", "gemini"):
            with patch.object(ai_engine, "_get_client", return_value=mock_client):
                result = extract_from_file(tmp_image_file)

        assert result.error is None
        assert result.data["field1"] == "test_value"
        assert result.data["field2"] == 42
        assert result.input_tokens == 1000
        assert result.output_tokens == 100
        assert result.cost_usd > 0
        assert result.extraction_time_ms > 0
        assert result.file_type == "image"

    def test_1_6_5_successful_pdf_extraction(self, tmp_pdf_file):
        mock_response = self._make_mock_gemini_response()
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch.object(ai_engine, "LLM_PROVIDER", "gemini"):
            with patch.object(ai_engine, "_get_client", return_value=mock_client):
                result = extract_from_file(tmp_pdf_file)

        assert result.error is None
        assert result.file_type == "pdf"

    def test_1_6_6_successful_audio_extraction(self, tmp_audio_file):
        mock_response = self._make_mock_gemini_response()
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch.object(ai_engine, "LLM_PROVIDER", "gemini"):
            with patch.object(ai_engine, "_get_client", return_value=mock_client):
                result = extract_from_file(tmp_audio_file)

        assert result.error is None
        assert result.file_type == "audio"

    def test_1_6_7_api_exception(self, tmp_image_file):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429: rate limited")

        with patch.object(ai_engine, "LLM_PROVIDER", "gemini"):
            with patch.object(ai_engine, "_get_client", return_value=mock_client):
                result = extract_from_file(tmp_image_file)

        assert result.error is not None
        assert result.file_type == "image"

    def test_1_6_8_parse_failure(self, tmp_image_file):
        mock_response = self._make_mock_gemini_response("I cannot parse this image at all")
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch.object(ai_engine, "LLM_PROVIDER", "gemini"):
            with patch.object(ai_engine, "_get_client", return_value=mock_client):
                result = extract_from_file(tmp_image_file)

        assert result.error is not None

    def test_1_6_9_image_extensions(self):
        """All image extensions map to file_type 'image'."""
        for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                img = Image.new("RGB", (10, 10), "red")
                fmt = "PNG" if ext in (".png", ".webp", ".gif") else "JPEG"
                img.save(f, format=fmt)
                path = f.name

            mock_response = self._make_mock_gemini_response('{"test": true}')
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response

            with patch.object(ai_engine, "LLM_PROVIDER", "gemini"):
                with patch.object(ai_engine, "_get_client", return_value=mock_client):
                    result = extract_from_file(path)
            assert result.file_type == "image", f"Failed for extension {ext}"
            os.unlink(path)

    def test_1_6_10_audio_extensions(self):
        """All audio extensions map to file_type 'audio'."""
        for ext in [".mp3", ".wav", ".m4a", ".ogg", ".webm"]:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                f.write(b"\x00" * 100)
                path = f.name

            mock_response = self._make_mock_gemini_response('{"test": true}')
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response

            with patch.object(ai_engine, "LLM_PROVIDER", "gemini"):
                with patch.object(ai_engine, "_get_client", return_value=mock_client):
                    result = extract_from_file(path)
            assert result.file_type == "audio", f"Failed for extension {ext}"
            os.unlink(path)


# =========================================================================
# 1.7  process_extracted_data
# =========================================================================

class TestProcessExtractedData:
    """Test data validation and normalization."""

    def test_1_7_1_valid_complete_data(self):
        data = {"field1": "test", "field2": "42.5", "field3": "2024-01-15"}
        result = process_extracted_data(data)
        assert result["field1"] == "test"
        assert result["field2"] == 42.5
        assert result["field3"] == date(2024, 1, 15)

    def test_1_7_2_string_truncation(self):
        data = {"field1": "x" * 600}
        result = process_extracted_data(data)
        assert len(result["field1"]) == 500

    def test_1_7_3_valid_date(self):
        data = {"field3": "2024-06-30"}
        result = process_extracted_data(data)
        assert result["field3"] == date(2024, 6, 30)

    def test_1_7_4_invalid_date_format(self):
        data = {"field3": "January 15th, 2024"}
        result = process_extracted_data(data)
        assert "field3" not in result

    def test_1_7_5_numeric_conversion(self):
        data = {"field2": "42.5"}
        result = process_extracted_data(data)
        assert result["field2"] == 42.5

    def test_1_7_6_invalid_numeric(self):
        data = {"field2": "not a number"}
        result = process_extracted_data(data)
        # field2 is processed as string first, then float conversion fails
        # The string version remains from the first loop
        assert "field2" in result

    def test_1_7_7_empty_null_fields(self):
        data = {"field1": None, "field2": None, "field3": None}
        result = process_extracted_data(data)
        assert "field3" not in result

    def test_1_7_8_whitespace_stripping(self):
        data = {"field1": "  value  "}
        result = process_extracted_data(data)
        assert result["field1"] == "value"


# =========================================================================
# 1.8  test_api_connection
# =========================================================================

class TestApiConnection:
    """Test API connection verification."""

    def test_1_8_1_no_api_key(self):
        with patch.object(ai_engine, "_get_client", return_value=None):
            result = _test_api_connection(api_key=None)
            assert result["success"] is False
            assert "not configured" in result["error"].lower()

    def test_1_8_2_gemini_success(self):
        mock_response = MagicMock()
        mock_response.text = "OK"
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch.object(ai_engine, "LLM_PROVIDER", "gemini"):
            with patch.object(ai_engine, "_get_client", return_value=mock_client):
                result = _test_api_connection()
        assert result["success"] is True
        assert result["message"] == "OK"

    def test_1_8_3_api_exception(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("Connection refused")

        with patch.object(ai_engine, "LLM_PROVIDER", "gemini"):
            with patch.object(ai_engine, "_get_client", return_value=mock_client):
                result = _test_api_connection()
        assert result["success"] is False
        assert "Connection refused" in result["error"]


# =========================================================================
# 1.9  _get_client
# =========================================================================

class TestGetClient:
    """Test LLM client initialization."""

    def test_1_9_1_gemini_with_key(self):
        with patch.object(ai_engine, "LLM_PROVIDER", "gemini"):
            from ai_engine import _get_client
            client = _get_client(api_key="test-key")
            # With google.genai mocked, Client() returns a MagicMock
            assert client is not None

    def test_1_9_2_no_key_returns_none(self):
        with patch.object(ai_engine, "LLM_PROVIDER", "gemini"):
            with patch.dict(os.environ, {}, clear=True):
                from ai_engine import _get_client
                client = _get_client(api_key="")
                assert client is None

    def test_1_9_3_unknown_provider(self):
        with patch.object(ai_engine, "LLM_PROVIDER", "unknown_provider"):
            from ai_engine import _get_client
            client = _get_client(api_key="test-key")
            assert client is None


# =========================================================================
# ExtractionResult dataclass
# =========================================================================

class TestExtractionResult:
    """Test the ExtractionResult dataclass."""

    def test_defaults(self):
        result = ExtractionResult(data={"a": 1})
        assert result.data == {"a": 1}
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.cost_usd == 0.0
        assert result.error is None
        assert result.extraction_time_ms == 0.0
        assert result.file_type == ""

    def test_with_error(self):
        result = ExtractionResult(data={}, error="Something failed")
        assert result.error == "Something failed"
        assert result.data == {}
