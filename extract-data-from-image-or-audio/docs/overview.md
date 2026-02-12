# AI Extraction Pipeline — Overview

## Problem Statement

When building applications that use AI to extract structured data from user uploads, developers face multiple challenges:

1. **Prompt Engineering** — Crafting prompts that consistently return valid JSON
2. **Response Parsing** — AI responses vary in format (raw JSON, markdown blocks, mixed text)
3. **Cost Optimization** — Large images consume excessive tokens; need preprocessing
4. **Error Handling** — API errors are cryptic; users need friendly messages
5. **Trust Calibration** — Users may blindly trust AI output; need verification step
6. **Rate Limiting** — Prevent API abuse without blocking legitimate users
7. **Observability** — Track extraction success, latency, and cost

This skill solves all of these in a cohesive, production-ready package.

---

## Core Pattern: The Safety Net

**Key Principle:** Never auto-save AI results. Always present extracted data in an editable form, letting users verify and correct before committing.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ User Upload  │────►│ AI Extraction│────►│ Review Form  │────►│ Save to DB   │
│ (file)       │     │ (structured) │     │ (editable)   │     │ (confirmed)  │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                            │                    ▲
                            │                    │
                            └────────────────────┘
                              User can correct
                              any AI mistakes
```

**Why This Matters:**
- AI extraction is 80-95% accurate, not 100%
- Incorrect data saved without review causes downstream problems
- Users feel in control and trust the system more
- Creates implicit feedback loop (users learn what AI gets wrong)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Your Application                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  File Upload    │  │  Review Form    │  │  Data Storage       │  │
│  │  Component      │  │  Component      │  │  (your database)    │  │
│  └────────┬────────┘  └────────▲────────┘  └──────────▲──────────┘  │
│           │                    │                      │              │
│           ▼                    │                      │              │
│  ┌─────────────────────────────┴──────────────────────┴──────────┐  │
│  │                     ai_engine.py                               │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │  │
│  │  │ Preprocessor │  │ LLM Client   │  │ Response Parser      │ │  │
│  │  │ (optimize)   │  │ (API call)   │  │ (JSON extraction)    │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   LLM Provider      │
                         │ (Gemini/OpenAI/     │
                         │  Claude)            │
                         └─────────────────────┘
```

---

## Generated Components

### 1. Extraction Engine (`ai_engine.py`)

Core module containing:

```python
@dataclass
class ExtractionResult:
    data: dict                    # Extracted fields
    input_tokens: int             # Token usage
    output_tokens: int
    cost_usd: float              # Estimated cost
    extraction_time_ms: float    # Latency
    file_type: str               # "image", "pdf", "audio"
    error: Optional[str]         # Error message if failed

def extract_from_file(file_path: str, api_key: str = None) -> ExtractionResult
def process_extracted_data(data: dict) -> dict  # Validate & normalize
def test_api_connection(api_key: str = None) -> dict
```

### 2. Image Optimization

Reduces API costs by 50-75%:

```python
MAX_IMAGE_WIDTH = 1024      # Configurable
JPEG_QUALITY = 85           # Configurable

def _resize_image_if_needed(file_data: bytes, suffix: str) -> tuple[bytes, str]
```

### 3. Prompt Templates

Structured prompts with JSON schema:

```python
EXTRACTION_PROMPT = """
Analyze this {media_type} and extract the following information.
Return ONLY a JSON object with these fields (use null for missing info):

{schema}

Rules:
{rules}
"""
```

### 4. Multi-Strategy Response Parser

Handles varying AI response formats:

```python
def _parse_response(text: str) -> dict:
    # Strategy 1: Direct JSON parse
    # Strategy 2: Extract from markdown code block
    # Strategy 3: Regex find JSON object
    # Fallback: Return error
```

### 5. Error Translation

Converts API errors to user-friendly messages:

```python
def _friendly_error(raw: str) -> str:
    # "invalid_argument" → "Could not process this file..."
    # "429" → "AI service is busy, please try again..."
    # "quota" → "API quota exceeded..."
```

### 6. Rate Limiting

Per-user daily limits:

```python
class ExtractionUsage(Base):
    owner_email = Column(String, index=True)
    usage_date = Column(Date)
    extraction_count = Column(Integer)

def can_extract(user_id: str) -> tuple[bool, int]  # (allowed, remaining)
def increment_extraction_count(user_id: str) -> bool
```

### 7. Review Form Component

Pre-populated editable form (framework-specific):

```python
def render_review_form(extracted_data: dict):
    # Display all fields from schema
    # Pre-populate with extracted values
    # Allow user edits
    # Validate on submit
```

---

## Supported Input Types

| Type | Extensions | Processing |
|------|------------|------------|
| **Images** | .jpg, .jpeg, .png, .webp, .gif | Resize + compress |
| **PDFs** | .pdf | Direct to API |
| **Audio** | .mp3, .wav, .m4a, .ogg | Direct to API (Gemini) |

---

## LLM Provider Comparison

| Provider | Strengths | Limitations | Cost |
|----------|-----------|-------------|------|
| **Gemini Flash** | Native audio, fastest, cheapest | Slightly lower accuracy | $0.10/1M input |
| **GPT-4 Vision** | Highest accuracy | No native audio, expensive | $10/1M input |
| **Claude Vision** | Large context, good reasoning | No audio support | $3/1M input |

**Recommendation:** Start with Gemini Flash for cost efficiency. Switch to GPT-4 if accuracy is critical.

---

## Security Considerations

1. **File Validation** — Check type, size, sanitize filename
2. **API Key Protection** — Environment variables only, never logged
3. **Rate Limiting** — Prevent abuse, per-user tracking
4. **Input Sanitization** — Clean all extracted text before storage
5. **No Auto-Execute** — Extracted data never auto-saved or executed

---

## Performance Characteristics

| Metric | Typical Range | Optimization |
|--------|---------------|--------------|
| Image extraction | 2-5 seconds | Reduce image size |
| PDF extraction | 3-8 seconds | Limit page count |
| Audio extraction | 5-15 seconds | Compress audio |
| Token usage | 500-2000 input | Image optimization |
| Cost per extraction | $0.0001-0.001 | Use Gemini Flash |

---

## Design Decisions

### Why Mandatory Review Form?

- AI is accurate but not perfect (80-95% depending on input quality)
- Cost of incorrect data > cost of user verification time
- Builds user trust through transparency
- Creates implicit quality feedback loop

### Why Image Optimization?

- 4000×3000 phone photo = ~5000 tokens
- 1024×768 resized = ~1500 tokens (70% reduction)
- No loss in extraction accuracy for text/receipts
- Significant cost savings at scale

### Why Multi-Strategy Parsing?

- LLMs don't always follow JSON-only instructions
- Sometimes wrap in markdown blocks
- Sometimes add explanatory text
- Robust parsing handles all cases gracefully

---

## Related Documentation

- [How to Use](how_to_use.md) — Step-by-step usage guide
- [Configuration](configuration.md) — All customization options
