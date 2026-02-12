# Configuration Reference

All configurable options for the AI Extraction Pipeline skill.

---

## Core Configuration

### LLM Provider Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `provider` | string | `"gemini"` | LLM provider: `gemini`, `openai`, `claude` |
| `model` | string | varies | Specific model to use (see below) |
| `api_key_env` | string | varies | Environment variable name for API key |

**Default Models by Provider:**

| Provider | Default Model | Alternatives |
|----------|---------------|--------------|
| Gemini | `gemini-2.0-flash` | `gemini-1.5-pro` |
| OpenAI | `gpt-4-vision-preview` | `gpt-4o` |
| Claude | `claude-3-5-sonnet` | `claude-3-opus` |

---

### File Processing Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `allowed_file_types` | list | `["image", "pdf", "audio"]` | Enabled input types |
| `max_file_size_mb` | int | `10` | Maximum upload size |
| `allowed_extensions` | list | see below | Specific extensions |

**Default Allowed Extensions:**
```python
{
    "image": [".jpg", ".jpeg", ".png", ".webp", ".gif"],
    "pdf": [".pdf"],
    "audio": [".mp3", ".wav", ".m4a", ".ogg"]
}
```

---

### Image Optimization Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_image_width` | int | `1024` | Resize images wider than this |
| `jpeg_quality` | int | `85` | JPEG compression quality (1-100) |
| `optimize_images` | bool | `true` | Enable/disable optimization |

**Recommendations by Use Case:**

| Use Case | max_image_width | jpeg_quality |
|----------|-----------------|--------------|
| Receipts/invoices | 1024 | 85 |
| Business cards | 1200 | 90 |
| Documents/contracts | 1600 | 90 |
| Photos with small text | 2048 | 95 |
| Screenshots | 1024 | 90 |

---

### Rate Limiting Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `rate_limit_enabled` | bool | `true` | Enable per-user limits |
| `daily_limit` | int | `20` | Extractions per user per day |
| `admin_limit` | int | `100` | Extractions per admin per day |
| `admin_max_limit` | int | `250` | Maximum configurable admin limit |

---

### Cost Tracking Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `track_cost` | bool | `true` | Enable cost tracking |
| `price_per_1m_input` | float | `0.10` | USD per 1M input tokens |
| `price_per_1m_output` | float | `0.40` | USD per 1M output tokens |

**Default Pricing by Provider:**

| Provider | Input (per 1M) | Output (per 1M) |
|----------|----------------|-----------------|
| Gemini Flash | $0.10 | $0.40 |
| GPT-4 Vision | $10.00 | $30.00 |
| Claude Sonnet | $3.00 | $15.00 |

---

### Review Form Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `review_required` | bool | `true` | Require user review before save |
| `show_confidence` | bool | `false` | Show confidence scores |
| `show_raw_response` | bool | `false` | Show raw AI response (debug) |

---

## Prompt Configuration

### Prompt Template

```python
EXTRACTION_PROMPT = """
Analyze this {media_type} and extract the following information.
Return ONLY a JSON object with these fields (use null for missing info):

{schema}

Rules:
{rules}
{additional_context}
"""
```

### Default Rules

```python
DEFAULT_RULES = [
    "Return ONLY valid JSON, no other text",
    "Use null for any information not clearly visible",
    "Dates must be in YYYY-MM-DD format",
    "Numbers should be numeric values, not strings",
    "Copy text exactly as shown (serial numbers, codes)",
]
```

### Adding Custom Rules

```python
CUSTOM_RULES = [
    "If warranty is stated in years, convert to months",
    "Extract phone numbers with country code",
    "For handwritten text, make best effort",
]
```

---

## Error Messages Configuration

### Default Error Translations

```python
ERROR_TRANSLATIONS = {
    "invalid_argument": "Could not process this file. It may be corrupted or unreadable.",
    "resource_exhausted": "AI service is temporarily busy. Please try again in a moment.",
    "permission_denied": "API key does not have permission. Check your configuration.",
    "quota_exceeded": "API quota exceeded. Try again later or check your billing.",
    "parse_error": "Could not understand AI response. Please try again.",
    "timeout": "Request timed out. Please try again.",
}
```

### Customizing Error Messages

```python
# Override specific messages
ERROR_TRANSLATIONS["quota_exceeded"] = "Daily limit reached. Upgrade for more extractions."
```

---

## Framework-Specific Configuration

### Streamlit

```python
# .streamlit/secrets.toml
GEMINI_API_KEY = "your-api-key"

# Or environment variable
# export GEMINI_API_KEY="your-api-key"
```

### Flask

```python
# config.py
class Config:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
```

### FastAPI

```python
# settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gemini_api_key: str
    max_file_size: int = 10 * 1024 * 1024

    class Config:
        env_file = ".env"
```

---

## Database Configuration

### Rate Limiting Table Schema

```sql
CREATE TABLE extraction_usage (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(254) NOT NULL,
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
    extraction_count INTEGER DEFAULT 0
);
CREATE INDEX idx_usage_user_date ON extraction_usage(user_id, usage_date);
```

### Extraction Log Table (Optional)

```sql
CREATE TABLE extraction_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(254) NOT NULL,
    file_type VARCHAR(20),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd DECIMAL(10, 6),
    extraction_time_ms FLOAT,
    success BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key |
| OR `OPENAI_API_KEY` | OpenAI API key |
| OR `ANTHROPIC_API_KEY` | Anthropic API key |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `EXTRACTION_MAX_WIDTH` | 1024 | Override image max width |
| `EXTRACTION_DAILY_LIMIT` | 20 | Override daily limit |
| `EXTRACTION_DEBUG` | false | Enable debug logging |

---

## Complete Configuration Example

```python
# extraction_config.py

EXTRACTION_CONFIG = {
    # Provider
    "provider": "gemini",
    "model": "gemini-2.0-flash",
    "api_key_env": "GEMINI_API_KEY",

    # File handling
    "allowed_file_types": ["image", "pdf"],
    "max_file_size_mb": 10,

    # Image optimization
    "max_image_width": 1024,
    "jpeg_quality": 85,
    "optimize_images": True,

    # Rate limiting
    "rate_limit_enabled": True,
    "daily_limit": 20,
    "admin_limit": 100,

    # Cost tracking
    "track_cost": True,
    "price_per_1m_input": 0.10,
    "price_per_1m_output": 0.40,

    # UI
    "review_required": True,
    "show_confidence": False,

    # Custom rules
    "additional_rules": [
        "Copy serial numbers exactly as shown",
        "Convert warranty years to months",
    ],
}
```

---

## Validation

The skill validates configuration on startup:

```python
def validate_config(config: dict) -> list[str]:
    """Returns list of validation errors, empty if valid."""
    errors = []

    if config["provider"] not in ["gemini", "openai", "claude"]:
        errors.append(f"Invalid provider: {config['provider']}")

    if config["max_image_width"] < 256:
        errors.append("max_image_width must be at least 256")

    if config["jpeg_quality"] < 1 or config["jpeg_quality"] > 100:
        errors.append("jpeg_quality must be between 1 and 100")

    if config["daily_limit"] < 1:
        errors.append("daily_limit must be at least 1")

    return errors
```
