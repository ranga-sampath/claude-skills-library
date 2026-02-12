# Test Report — AI Extraction Pipeline

| Field | Value |
|-------|-------|
| **Date & Time** | 2026-02-12 17:45 IST |
| **Python Version** | 3.9.6 |
| **Test Framework** | pytest 8.4.2 |
| **Platform** | macOS Darwin 25.2.0 (arm64) |
| **Total Duration** | 0.26s |

---

## Summary

| Metric | Count |
|--------|-------|
| **Total tests collected** | 108 |
| **Passed** | 95 |
| **Failed** | 1 |
| **Skipped** | 12 |
| **Pass rate (executed)** | **98.96%** (95/96) |

---

## Results by Module

### 1. AI Extraction Engine (`test_ai_engine.py`) — 72 tests

| Test Group | Tests | Passed | Failed | Status |
|------------|-------|--------|--------|--------|
| 1.1 Response Parsing (`_parse_response`) | 12 | 12 | 0 | PASS |
| 1.2 Error Translation (`_friendly_error`) | 12 | 12 | 0 | PASS |
| 1.3 Cost Calculation (`_calculate_cost`) | 4 | 4 | 0 | PASS |
| 1.4 MIME Type Resolution (`_get_mime_type`) | 10 | 10 | 0 | PASS |
| 1.5 Image Optimization (`_resize_image_if_needed`) | 7 | 6 | **1** | **FAIL** |
| 1.6 File Extraction (`extract_from_file`) | 10 | 10 | 0 | PASS |
| 1.7 Data Processing (`process_extracted_data`) | 8 | 8 | 0 | PASS |
| 1.8 API Connection (`test_api_connection`) | 3 | 3 | 0 | PASS |
| 1.9 Client Init (`_get_client`) | 3 | 3 | 0 | PASS |
| ExtractionResult dataclass | 2 | 2 | 0 | PASS |
| **Subtotal** | **71** | **70** | **1** | |

### 2. Database Models (`test_database_models.py`) — 25 tests

| Test Group | Tests | Passed | Failed | Status |
|------------|-------|--------|--------|--------|
| 2.1 Rate Limiting (core) | 9 | 9 | 0 | PASS |
| 2.2 Usage Statistics | 3 | 3 | 0 | PASS |
| 2.3 Logging | 3 | 3 | 0 | PASS |
| 2.4 Aggregate Statistics | 2 | 2 | 0 | PASS |
| 2.5 Model Definitions | 4 | 4 | 0 | PASS |
| Edge Cases | 4 | 4 | 0 | PASS |
| **Subtotal** | **25** | **25** | **0** | |

### 3. Streamlit UI Components (`test_ui_components.py`) — 12 tests

| Test Group | Tests | Passed | Skipped | Status |
|------------|-------|--------|---------|--------|
| 3.1 File Upload | 3 | 0 | 3 | SKIPPED |
| 3.2 Rate Limit Display | 3 | 0 | 3 | SKIPPED |
| 3.3 Configuration | 2 | 0 | 2 | SKIPPED |
| 3.4 Extraction Progress | 1 | 0 | 1 | SKIPPED |
| 3.5 Error Display | 1 | 0 | 1 | SKIPPED |
| 3.6 Metadata Display | 2 | 0 | 2 | SKIPPED |
| **Subtotal** | **12** | **0** | **12** | |

> **Skip reason:** `ui_components_streamlit.py` uses Python 3.10+ union type syntax (`tuple[str, str] | tuple[None, None]`) which is not supported on the test environment (Python 3.9.6). These tests are expected to pass on Python 3.10+.

---

## Failures

### FAIL-001: Palette-mode image not resized when JPEG conversion produces larger output

| Field | Detail |
|-------|--------|
| **Test** | `test_1_5_4_palette_mode_converted` |
| **File** | `templates/ai_engine.py:136` — `_resize_image_if_needed()` |
| **Severity** | **Medium** |
| **Category** | Logic Bug — Image Optimization |

**What happened:**
A 1200x900 palette-mode (P) PNG image was passed to `_resize_image_if_needed()`. The function correctly converts it to RGB and resizes it to 1024px wide. However, the final size-comparison check (`len(resized_data) < original_size`) fails because the palette-mode PNG is extremely compact (solid-color palette encoding), and the resized JPEG is actually larger in bytes. The function discards the resized result and returns the **original unresized** 1200px image.

**Expected:** Image resized to <= 1024px wide.
**Actual:** Original 1200px image returned unchanged.

**Root cause:**
```python
# Line 160-161 in ai_engine.py
if len(resized_data) < original_size:
    return resized_data, 'image/jpeg'
return file_data, _get_mime_type(suffix, 'image')  # <-- returns original
```

The size-comparison heuristic optimizes for API cost (smaller payload = fewer tokens), but it does not account for the `MAX_IMAGE_WIDTH` constraint. When the compressed JPEG is larger than the original, the function prioritizes byte size over dimension limits.

**Impact:** Oversized images in compact formats (palette-mode PNGs, small solid-color images) may be sent to the LLM API without resizing. This could lead to:
- Higher-than-expected token usage
- Potential API rejection for images exceeding provider size limits

**Suggested fix:**
```python
# Always return resized if dimensions were reduced, regardless of byte size
was_resized = (img.width != original_width)
if was_resized or len(resized_data) < original_size:
    return resized_data, 'image/jpeg'
```

---

## Skipped Tests — Categorized

### SKIP-001: Streamlit UI component tests (12 tests)

| Field | Detail |
|-------|--------|
| **Severity** | **Low** |
| **Category** | Environment Compatibility |

**Reason:** The source file `ui_components_streamlit.py` uses Python 3.10+ union type syntax (`X | Y`) in type annotations. The test environment runs Python 3.9.6 where this syntax raises `TypeError` at import time.

**Impact:** UI component logic (file upload validation, rate limit display, error rendering) remains untested in this environment. The tests are structurally complete and expected to pass on Python 3.10+.

**Recommendation:** Run these tests on Python 3.10+ or add `from __future__ import annotations` to the source file for backward compatibility.

---

## Issue Summary

| ID | Severity | Category | Test | Description |
|----|----------|----------|------|-------------|
| FAIL-001 | **Medium** | Logic Bug | `test_1_5_4` | Palette-mode images skip resizing when JPEG is larger than original |
| SKIP-001 | **Low** | Compatibility | 12 UI tests | Python 3.10+ syntax prevents import on Python 3.9 |

---

## Coverage Highlights

### Fully covered (all tests passing):

- **Response parsing** — All 3 parse strategies + edge cases (12/12)
- **Error translation** — All 10 error patterns + edge cases (12/12)
- **Cost calculation** — Zero, typical, large, input-only (4/4)
- **MIME type mapping** — All file types + unknown/edge cases (10/10)
- **File extraction** — Success paths for image/PDF/audio, all error paths (10/10)
- **Rate limiting** — Under/at/over limit, admin vs regular, cross-day, multi-user (13/13)
- **Data processing** — Validation, truncation, type conversion, nulls (8/8)
- **Database models** — Schema structure, logging, aggregate stats (9/9)

### Key edge cases validated:

- Unicode characters in JSON responses
- Malformed JSON falling through parse strategies
- Corrupted image data returning gracefully
- Rate limit boundary conditions (exactly at limit)
- Yesterday's usage not counting against today
- Multiple users with independent rate limits
- Empty strings and null values throughout

---

## How to Reproduce

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run only the failing test
python3 -m pytest tests/test_ai_engine.py::TestResizeImage::test_1_5_4_palette_mode_converted -v

# Run with coverage (requires Python 3.10+ for full coverage)
python3 -m pytest tests/ -v --cov=templates --cov-report=term-missing
```

---

## Test Environment

| Component | Version |
|-----------|---------|
| Python | 3.9.6 |
| pytest | 8.4.2 |
| pytest-cov | 7.0.0 |
| Pillow | 11.2.1 |
| SQLAlchemy | 2.0.46 |
| OS | macOS Darwin 25.2.0 |
