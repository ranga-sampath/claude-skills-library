"""
AI Extraction Engine Template

This template provides a complete AI-powered extraction pipeline.
Customize the EXTRACTION_SCHEMA and EXTRACTION_PROMPT for your use case.
"""

import io
import os
import json
import re
import time
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass
from pathlib import Path

# Image processing
from PIL import Image

# =============================================================================
# CONFIGURATION - Customize these for your use case
# =============================================================================

# LLM Provider: "gemini", "openai", or "claude"
LLM_PROVIDER = "gemini"

# Image optimization settings
MAX_IMAGE_WIDTH = 1024
JPEG_QUALITY = 85

# Cost tracking (Gemini Flash pricing)
PRICE_PER_1M_INPUT_TOKENS = 0.10  # USD
PRICE_PER_1M_OUTPUT_TOKENS = 0.40  # USD

# Your extraction schema - CUSTOMIZE THIS
EXTRACTION_SCHEMA = """
{
    "field1": "string (description)",
    "field2": "number",
    "field3": "YYYY-MM-DD",
    "category": "enum: Option1|Option2|Option3"
}
"""

# Extraction prompt template
EXTRACTION_PROMPT = """
Analyze this {media_type} and extract the following information.
Return ONLY a JSON object with these fields (use null for missing info):

{schema}

Rules:
- Return ONLY valid JSON, no other text
- Use null for any information not clearly visible
- Dates must be in YYYY-MM-DD format
- Numbers should be numeric values, not strings
- Copy text exactly as shown (serial numbers, codes)
{additional_context}
"""


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ExtractionResult:
    """Result of an AI extraction operation."""
    data: dict
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None
    extraction_time_ms: float = 0.0
    file_type: str = ""  # "image", "audio", "pdf"


# =============================================================================
# LLM CLIENT
# =============================================================================

def _get_client(api_key: Optional[str] = None):
    """Get the LLM client based on configured provider."""
    if LLM_PROVIDER == "gemini":
        from google import genai
        key = api_key or os.environ.get("GEMINI_API_KEY", "")
        return genai.Client(api_key=key) if key else None

    elif LLM_PROVIDER == "openai":
        from openai import OpenAI
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        return OpenAI(api_key=key) if key else None

    elif LLM_PROVIDER == "claude":
        import anthropic
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        return anthropic.Anthropic(api_key=key) if key else None

    return None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated cost in USD."""
    return (input_tokens * PRICE_PER_1M_INPUT_TOKENS +
            output_tokens * PRICE_PER_1M_OUTPUT_TOKENS) / 1_000_000


def _get_mime_type(suffix: str, file_type: str) -> str:
    """Get MIME type from file extension."""
    mime_map = {
        "image": {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        },
        "audio": {
            ".mp3": "audio/mp3",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
        },
        "pdf": {
            ".pdf": "application/pdf",
        },
    }
    return mime_map.get(file_type, {}).get(suffix.lower(), f"{file_type}/octet-stream")


def _resize_image_if_needed(file_data: bytes, suffix: str) -> tuple[bytes, str]:
    """Resize image to max width if needed. Returns (data, mime_type)."""
    try:
        img = Image.open(io.BytesIO(file_data))
        original_size = len(file_data)

        # Convert RGBA to RGB (JPEG doesn't support alpha)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Only resize if width exceeds max
        if img.width > MAX_IMAGE_WIDTH:
            ratio = MAX_IMAGE_WIDTH / img.width
            new_height = int(img.height * ratio)
            img = img.resize((MAX_IMAGE_WIDTH, new_height), Image.Resampling.LANCZOS)

        # Save as JPEG for optimal size
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=JPEG_QUALITY, optimize=True)
        resized_data = output.getvalue()

        # Only use resized if it's actually smaller
        if len(resized_data) < original_size:
            return resized_data, 'image/jpeg'

        return file_data, _get_mime_type(suffix, 'image')

    except Exception:
        return file_data, _get_mime_type(suffix, 'image')


def _friendly_error(raw: str) -> str:
    """Convert raw API errors to user-friendly messages."""
    lower = raw.lower()

    if "invalid_argument" in lower and "image" in lower:
        return "Could not process this image. The file may be corrupted or unreadable."
    if "invalid_argument" in lower and "audio" in lower:
        return "Could not process this audio. The file may be corrupted or unreadable."
    if "invalid_argument" in lower:
        return "Could not process this file. It may be corrupted or in an unsupported format."
    if "429" in raw or "resource_exhausted" in lower:
        return "AI service is temporarily busy. Please wait a moment and try again."
    if "403" in raw or "permission_denied" in lower:
        return "API key does not have permission. Check your API key configuration."
    if "quota" in lower:
        return "API quota exceeded. Try again later or check your billing."
    if "response has no text" in lower or "blocked" in lower:
        return "Could not process this file. The content may be unclear or unrecognizable."
    if "timeout" in lower or "deadline" in lower:
        return "Request timed out. Please try again."

    return f"Could not process file: {raw}"


def _parse_response(text: str) -> dict:
    """Parse JSON from LLM response using multiple strategies."""
    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code block
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find JSON object anywhere in text
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {"error": "Could not parse AI response"}


# =============================================================================
# MAIN EXTRACTION FUNCTION
# =============================================================================

def extract_from_file(file_path: str, api_key: Optional[str] = None) -> ExtractionResult:
    """Extract data from image, PDF, or audio file."""
    client = _get_client(api_key)
    if not client:
        return ExtractionResult(data={}, error="API key not configured")

    path = Path(file_path)
    if not path.exists():
        return ExtractionResult(data={}, error=f"File not found: {path}")

    suffix = path.suffix.lower()

    # Determine file type and prompt context
    if suffix == ".pdf":
        file_type = "pdf"
        media_desc = "PDF document"
        context = "Extract the requested information from this document."
    elif suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        file_type = "image"
        media_desc = "image"
        context = "Look for text, labels, numbers, and other visible information."
    elif suffix in (".mp3", ".wav", ".m4a", ".ogg", ".webm"):
        file_type = "audio"
        media_desc = "audio recording"
        context = "Listen for spoken information including names, numbers, and dates."
    else:
        return ExtractionResult(data={}, error=f"Unsupported file type: {suffix}")

    try:
        with open(path, "rb") as f:
            file_data = f.read()

        # Optimize images before sending to API
        if file_type == "image":
            file_data, mime_type = _resize_image_if_needed(file_data, suffix)
        else:
            mime_type = _get_mime_type(suffix, file_type)

        prompt = EXTRACTION_PROMPT.format(
            media_type=media_desc,
            schema=EXTRACTION_SCHEMA,
            additional_context=context
        )

        # Time the API call
        start_time = time.perf_counter()

        # Call the appropriate LLM
        if LLM_PROVIDER == "gemini":
            from google.genai import types
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[types.Part.from_bytes(data=file_data, mime_type=mime_type), prompt],
            )
            response_text = response.text
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0

        elif LLM_PROVIDER == "openai":
            import base64
            b64_data = base64.b64encode(file_data).decode()
            response = client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}}
                    ]
                }]
            )
            response_text = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

        elif LLM_PROVIDER == "claude":
            import base64
            b64_data = base64.b64encode(file_data).decode()
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64_data}},
                        {"type": "text", "text": prompt}
                    ]
                }]
            )
            response_text = response.content[0].text
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

        extraction_time_ms = (time.perf_counter() - start_time) * 1000
        cost = _calculate_cost(input_tokens, output_tokens)

        data = _parse_response(response_text)
        if "error" in data:
            return ExtractionResult(
                data={},
                error=data["error"],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                extraction_time_ms=extraction_time_ms,
                file_type=file_type
            )

        return ExtractionResult(
            data=data,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            extraction_time_ms=extraction_time_ms,
            file_type=file_type
        )

    except Exception as e:
        return ExtractionResult(data={}, error=_friendly_error(str(e)), file_type=file_type)


# =============================================================================
# VALIDATION AND PROCESSING
# =============================================================================

def process_extracted_data(data: dict) -> dict:
    """Validate and normalize extracted data. Customize for your schema."""
    processed = {}

    # Example: Process string fields
    for field in ["field1", "field2"]:
        if field in data:
            value = data.get(field)
            if value:
                processed[field] = str(value).strip()[:500]  # Sanitize and limit

    # Example: Process date fields
    if data.get("field3"):
        try:
            processed["field3"] = datetime.strptime(data["field3"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass

    # Example: Process numeric fields
    if data.get("field2"):
        try:
            processed["field2"] = float(data["field2"])
        except (ValueError, TypeError):
            pass

    return processed


# =============================================================================
# API CONNECTION TEST
# =============================================================================

def test_api_connection(api_key: Optional[str] = None) -> dict:
    """Test the API connection."""
    client = _get_client(api_key)
    if not client:
        return {"success": False, "error": "API key not configured"}

    try:
        if LLM_PROVIDER == "gemini":
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents="Reply with only: OK"
            )
            return {"success": True, "message": response.text.strip()}

        elif LLM_PROVIDER == "openai":
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Reply with only: OK"}],
                max_tokens=10
            )
            return {"success": True, "message": response.choices[0].message.content}

        elif LLM_PROVIDER == "claude":
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "Reply with only: OK"}]
            )
            return {"success": True, "message": response.content[0].text}

    except Exception as e:
        return {"success": False, "error": str(e)}
