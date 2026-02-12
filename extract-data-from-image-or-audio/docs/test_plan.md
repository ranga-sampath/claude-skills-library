# Test Plan — AI Extraction Pipeline

## Scope

This test plan covers the three core template modules:

| Module | File | Priority |
|--------|------|----------|
| AI Extraction Engine | `templates/ai_engine.py` | **Critical** |
| Database Models & Rate Limiting | `templates/database_models.py` | **High** |
| Streamlit UI Components | `templates/ui_components_streamlit.py` | **Medium** |

All tests use **pytest** with mocked external dependencies (LLM APIs, database sessions, PIL, Streamlit). No real API keys or network calls are required.

---

## 1. AI Extraction Engine (`ai_engine.py`)

### 1.1 Response Parsing — `_parse_response()` [CRITICAL]

The multi-strategy parser is the most fragile component. Failures here cause silent data loss.

| # | Test Case | Input | Expected Output | Priority |
|---|-----------|-------|-----------------|----------|
| 1.1.1 | Direct valid JSON | `'{"merchant": "Starbucks", "total": 5.75}'` | Parsed dict | Critical |
| 1.1.2 | JSON in markdown code block | `` ```json\n{"a": 1}\n``` `` | `{"a": 1}` | Critical |
| 1.1.3 | JSON in plain code block | `` ```\n{"a": 1}\n``` `` | `{"a": 1}` | Critical |
| 1.1.4 | JSON embedded in text | `"Here is the result: {\"a\": 1} hope this helps"` | `{"a": 1}` | High |
| 1.1.5 | Completely unparseable | `"I cannot process this image"` | `{"error": "Could not parse AI response"}` | Critical |
| 1.1.6 | Empty string | `""` | Error dict | High |
| 1.1.7 | Nested JSON objects | `'{"items": [{"name": "A", "qty": 2}]}'` | Parsed with nested list | High |
| 1.1.8 | JSON with null values | `'{"field1": null, "field2": "value"}'` | Parsed with None | High |
| 1.1.9 | Malformed JSON in code block | `` ```json\n{broken}\n``` `` | Falls through to strategy 3 or error | Medium |
| 1.1.10 | Multiple JSON objects in text | `'{"a":1} some text {"b":2}'` | Returns first match `{"a":1}` | Medium |
| 1.1.11 | JSON with unicode characters | `'{"name": "José García"}'` | Parsed with unicode intact | Medium |
| 1.1.12 | JSON with special chars in values | `'{"note": "price is $5.00 & tax"}'` | Parsed correctly | Medium |

### 1.2 Error Translation — `_friendly_error()` [HIGH]

Maps raw API errors to user-facing messages. Incorrect mapping confuses users.

| # | Test Case | Input | Expected Substring | Priority |
|---|-----------|-------|--------------------|----------|
| 1.2.1 | Invalid argument (image) | `"invalid_argument: bad image data"` | "Could not process this image" | High |
| 1.2.2 | Invalid argument (audio) | `"invalid_argument: audio format"` | "Could not process this audio" | High |
| 1.2.3 | Invalid argument (generic) | `"invalid_argument: something"` | "corrupted or in an unsupported format" | High |
| 1.2.4 | Rate limited (429) | `"Error 429: Too many requests"` | "temporarily busy" | High |
| 1.2.5 | Resource exhausted | `"RESOURCE_EXHAUSTED"` | "temporarily busy" | High |
| 1.2.6 | Permission denied (403) | `"403 Forbidden"` | "permission" | High |
| 1.2.7 | Quota exceeded | `"Quota limit reached"` | "quota exceeded" | High |
| 1.2.8 | No response text | `"response has no text"` | "unclear or unrecognizable" | Medium |
| 1.2.9 | Timeout error | `"Request timeout exceeded"` | "timed out" | Medium |
| 1.2.10 | Unknown error | `"Something completely new happened"` | "Could not process file:" | Medium |
| 1.2.11 | Empty string | `""` | "Could not process file:" | Low |
| 1.2.12 | Case sensitivity | `"INVALID_ARGUMENT: IMAGE"` | "Could not process this image" | Medium |

### 1.3 Cost Calculation — `_calculate_cost()` [MEDIUM]

| # | Test Case | Input Tokens | Output Tokens | Expected | Priority |
|---|-----------|-------------|---------------|----------|----------|
| 1.3.1 | Typical extraction | 1000 | 100 | $0.00014 | High |
| 1.3.2 | Zero tokens | 0 | 0 | $0.0 | Medium |
| 1.3.3 | Large token count | 1,000,000 | 1,000,000 | $0.50 | Medium |
| 1.3.4 | Input only | 500 | 0 | $0.00005 | Low |

### 1.4 MIME Type Resolution — `_get_mime_type()` [MEDIUM]

| # | Test Case | Suffix | File Type | Expected | Priority |
|---|-----------|--------|-----------|----------|----------|
| 1.4.1 | JPEG image | `.jpg` | `image` | `image/jpeg` | High |
| 1.4.2 | PNG image | `.png` | `image` | `image/png` | High |
| 1.4.3 | MP3 audio | `.mp3` | `audio` | `audio/mp3` | High |
| 1.4.4 | PDF document | `.pdf` | `pdf` | `application/pdf` | High |
| 1.4.5 | Unknown extension | `.xyz` | `image` | `image/octet-stream` | Medium |
| 1.4.6 | Case sensitivity | `.JPG` | `image` | `image/jpeg` | Medium |
| 1.4.7 | WAV audio | `.wav` | `audio` | `audio/wav` | Medium |
| 1.4.8 | WebP image | `.webp` | `image` | `image/webp` | Medium |
| 1.4.9 | Unknown file type | `.png` | `unknown` | `unknown/octet-stream` | Low |
| 1.4.10 | M4A audio | `.m4a` | `audio` | `audio/mp4` | Medium |

### 1.5 Image Optimization — `_resize_image_if_needed()` [HIGH]

| # | Test Case | Input | Expected | Priority |
|---|-----------|-------|----------|----------|
| 1.5.1 | Large RGB image (2048px) | 2048x1536 RGB | Resized to 1024px wide | Critical |
| 1.5.2 | Small image (800px) | 800x600 RGB | Not resized (width <= MAX) | High |
| 1.5.3 | RGBA image (transparency) | 1200x900 RGBA | Converted to RGB + resized | High |
| 1.5.4 | Palette mode image | 1200x900 P | Converted to RGB + resized | Medium |
| 1.5.5 | Exact max width | 1024x768 RGB | No resize, may still compress | Medium |
| 1.5.6 | Corrupted image data | Random bytes | Returns original data unchanged | High |
| 1.5.7 | Tiny image (100px) | 100x100 RGB | Returns original or compressed | Low |

### 1.6 File Extraction — `extract_from_file()` [CRITICAL]

| # | Test Case | Scenario | Expected | Priority |
|---|-----------|----------|----------|----------|
| 1.6.1 | No API key | No key configured | Error: "API key not configured" | Critical |
| 1.6.2 | File not found | Non-existent path | Error: "File not found" | Critical |
| 1.6.3 | Unsupported file type | `.txt` file | Error: "Unsupported file type" | High |
| 1.6.4 | Successful image extraction (Gemini) | Valid image + mocked Gemini | ExtractionResult with data | Critical |
| 1.6.5 | Successful PDF extraction | Valid PDF + mocked API | ExtractionResult with data | High |
| 1.6.6 | Successful audio extraction | Valid audio + mocked API | ExtractionResult with data | High |
| 1.6.7 | API exception | Mocked API throws | Friendly error returned | Critical |
| 1.6.8 | Parse failure from API | API returns garbage text | Error in result | High |
| 1.6.9 | Supported image extensions | `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif` | file_type = "image" | Medium |
| 1.6.10 | Supported audio extensions | `.mp3`, `.wav`, `.m4a`, `.ogg`, `.webm` | file_type = "audio" | Medium |

### 1.7 Data Processing — `process_extracted_data()` [MEDIUM]

| # | Test Case | Input | Expected | Priority |
|---|-----------|-------|----------|----------|
| 1.7.1 | Valid complete data | All fields present | Processed dict | High |
| 1.7.2 | String truncation | 600-char string | Truncated to 500 chars | Medium |
| 1.7.3 | Valid date parsing | `"2024-01-15"` | `date(2024, 1, 15)` | High |
| 1.7.4 | Invalid date format | `"January 15"` | Field omitted | Medium |
| 1.7.5 | Numeric conversion | `"42.5"` as field2 | `42.5` float | Medium |
| 1.7.6 | Invalid numeric | `"not a number"` | Field omitted | Medium |
| 1.7.7 | Empty/null fields | All None values | Empty dict | Medium |
| 1.7.8 | Whitespace stripping | `"  value  "` | `"value"` | Low |

### 1.8 API Connection Test — `test_api_connection()` [HIGH]

| # | Test Case | Scenario | Expected | Priority |
|---|-----------|----------|----------|----------|
| 1.8.1 | No API key | No key set | `{"success": False, "error": "API key not configured"}` | High |
| 1.8.2 | Gemini success | Mocked OK response | `{"success": True}` | High |
| 1.8.3 | API exception | Client throws | `{"success": False, "error": ...}` | High |

### 1.9 Client Initialization — `_get_client()` [MEDIUM]

| # | Test Case | Provider | Key | Expected | Priority |
|---|-----------|----------|-----|----------|----------|
| 1.9.1 | Gemini with key | gemini | "test-key" | Client object | High |
| 1.9.2 | No key provided | gemini | None/empty | None | High |
| 1.9.3 | Unknown provider | "unknown" | "key" | None | Medium |

---

## 2. Database Models (`database_models.py`)

### 2.1 Rate Limiting — Core Functions [CRITICAL]

| # | Test Case | Scenario | Expected | Priority |
|---|-----------|----------|----------|----------|
| 2.1.1 | No usage record | New user, no extractions today | Count = 0 | High |
| 2.1.2 | Existing usage | User with 5 extractions | Count = 5 | High |
| 2.1.3 | Can extract (under limit) | 5 of 20 used | `(True, 15)` | Critical |
| 2.1.4 | Cannot extract (at limit) | 20 of 20 used | `(False, 0)` | Critical |
| 2.1.5 | Admin higher limit | Admin user | Limit = 100 | High |
| 2.1.6 | Regular user limit | Non-admin | Limit = 20 | High |
| 2.1.7 | Increment from zero | New user | Count becomes 1, returns True | High |
| 2.1.8 | Increment at limit | At max count | Returns False, count unchanged | Critical |
| 2.1.9 | Increment existing record | User with existing record | Count incremented | High |

### 2.2 Usage Statistics — `get_extraction_usage_stats()` [MEDIUM]

| # | Test Case | Scenario | Expected | Priority |
|---|-----------|----------|----------|----------|
| 2.2.1 | Fresh user | No usage | `{today_count: 0, remaining: 20, limit_reached: False}` | Medium |
| 2.2.2 | Partial usage | 10 used | `{today_count: 10, remaining: 10}` | Medium |
| 2.2.3 | Limit reached | 20 used | `{limit_reached: True, remaining: 0}` | Medium |

### 2.3 Logging — `log_extraction()` [MEDIUM]

| # | Test Case | Scenario | Expected | Priority |
|---|-----------|----------|----------|----------|
| 2.3.1 | Successful extraction log | All fields provided | Record saved | Medium |
| 2.3.2 | Error message truncation | 600-char error | Truncated to 500 | Medium |
| 2.3.3 | Null error message | No error | `error_message` is None | Low |

### 2.4 Aggregate Statistics — `get_extraction_stats()` [LOW]

| # | Test Case | Scenario | Expected | Priority |
|---|-----------|----------|----------|----------|
| 2.4.1 | Empty log | No records | All zeros | Medium |
| 2.4.2 | With records | Multiple entries | Correct aggregation | Medium |

### 2.5 Model Definitions [MEDIUM]

| # | Test Case | Scenario | Expected | Priority |
|---|-----------|----------|----------|----------|
| 2.5.1 | ExtractionUsage table name | Check __tablename__ | `"extraction_usage"` | Medium |
| 2.5.2 | ExtractionLog table name | Check __tablename__ | `"extraction_log"` | Medium |
| 2.5.3 | ExtractionUsage columns | Check all columns exist | id, user_id, usage_date, extraction_count | Medium |
| 2.5.4 | ExtractionLog columns | Check all columns exist | All expected columns | Medium |

---

## 3. Streamlit UI Components (`ui_components_streamlit.py`)

### 3.1 File Upload — `render_file_uploader()` [HIGH]

| # | Test Case | Scenario | Expected | Priority |
|---|-----------|----------|----------|----------|
| 3.1.1 | No file uploaded | User hasn't selected a file | Returns `(None, None)` | High |
| 3.1.2 | File too large | 15MB file | Error displayed, returns `(None, None)` | High |
| 3.1.3 | Valid file upload | 1MB JPEG | Returns `(temp_path, filename)` | High |

### 3.2 Rate Limit Display — `render_rate_limit_status()` [MEDIUM]

| # | Test Case | Remaining | Limit | Expected Display | Priority |
|---|-----------|-----------|-------|------------------|----------|
| 3.2.1 | Limit reached | 0 | 20 | Warning message | High |
| 3.2.2 | Low remaining | 3 | 20 | Info message | Medium |
| 3.2.3 | Plenty remaining | 15 | 20 | Caption with count | Low |

### 3.3 Configuration Constants [LOW]

| # | Test Case | Check | Expected | Priority |
|---|-----------|-------|----------|----------|
| 3.3.1 | Allowed extensions | ALLOWED_EXTENSIONS list | Contains jpg, png, pdf, mp3, etc. | Medium |
| 3.3.2 | Max file size | MAX_FILE_SIZE_MB | 10 | Medium |

---

## Test Infrastructure

### Dependencies
```
pytest>=7.0
pytest-cov
Pillow
sqlalchemy
```

### Directory Structure
```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_ai_engine.py        # Tests for ai_engine.py
├── test_database_models.py  # Tests for database_models.py
├── test_ui_components.py    # Tests for ui_components_streamlit.py
└── TEST_REPORT.md           # Auto-generated report
```

### Running Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=templates --cov-report=term-missing

# Run specific module
python -m pytest tests/test_ai_engine.py -v
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM response format changes | Data loss / parse failures | Multi-strategy parser + comprehensive parse tests |
| API key leakage | Security breach | Tests verify keys are never logged or returned in results |
| Rate limiting bypass | API cost overrun | Tests verify limit enforcement at boundary conditions |
| Image processing crashes | User-facing errors | Tests verify graceful fallback on corrupted images |
| Cost miscalculation | Billing surprises | Tests verify cost formula accuracy |
