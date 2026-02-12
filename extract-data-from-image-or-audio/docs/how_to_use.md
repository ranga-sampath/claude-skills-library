# How to Use the AI Extraction Pipeline Skill

This guide provides practical instructions for using the AI Extraction Pipeline skill in your applications.

---

## Quick Start

### Step 1: Install the Skill

Copy the skill to your Claude Code skills directory:

```bash
mkdir -p your-project/.claude/skills
cp -r ai-extraction-skill/.claude/skills/ai_extraction your-project/.claude/skills/
```

### Step 2: Invoke the Skill

In your project, start Claude Code and run:

```
/ai-extraction
```

### Step 3: Answer the Prompts

Claude will ask you a series of questions to customize the pipeline.

### Step 4: Configure API Keys

Add your LLM provider API key to environment variables:

```bash
# For Gemini
export GEMINI_API_KEY="your-api-key"

# For OpenAI
export OPENAI_API_KEY="your-api-key"
```

### Step 5: Test and Integrate

Run the test connection, try a sample extraction, verify the review form works.

---

## Required Inputs

When invoking the skill, be prepared to provide:

| Input | Required | Description | Example |
|-------|----------|-------------|---------|
| **Extraction Schema** | Yes | JSON structure of fields to extract | See examples below |
| **LLM Provider** | Yes | Which AI service to use | `gemini`, `openai`, `claude` |
| **File Types** | Yes | What users will upload | `image`, `pdf`, `audio`, `all` |
| **Framework** | Yes | Your application framework | `streamlit`, `flask`, `fastapi` |
| **Rate Limit** | No | Daily extractions per user | Default: 20 |
| **Admin Limit** | No | Daily extractions for admin | Default: 100 |

---

## Defining Your Extraction Schema

The schema tells the AI what data to extract. Define it as a JSON object with field names, types, and optional descriptions.

### Schema Format

```json
{
  "field_name": "type (description)",
  "another_field": "type",
  "enum_field": "enum: Option1|Option2|Option3"
}
```

### Supported Types

| Type | Description | Example Output |
|------|-------------|----------------|
| `string` | Free text | `"Apple iPhone 15"` |
| `number` | Integer or decimal | `999.99` |
| `date` | Date in YYYY-MM-DD | `"2024-01-15"` |
| `boolean` | True/false | `true` |
| `enum` | One of specified values | `"Electronics"` |
| `array` | List of items | `[{"name": "Item 1"}, ...]` |

---

## Example Use Cases

### Example 1: Receipt Scanner

**Use Case:** Extract purchase details from receipt photos for expense tracking.

**Schema:**
```json
{
  "merchant": "string (store or business name)",
  "date": "YYYY-MM-DD (purchase date)",
  "total": "number (total amount paid)",
  "currency": "string (3-letter code like USD, EUR, INR)",
  "payment_method": "string (cash, card, UPI, etc.)",
  "category": "enum: Food|Transport|Shopping|Entertainment|Utilities|Other",
  "items": "array of {name, quantity, unit_price}"
}
```

**Sample Output:**
```json
{
  "merchant": "Whole Foods Market",
  "date": "2024-01-15",
  "total": 47.83,
  "currency": "USD",
  "payment_method": "Credit Card",
  "category": "Food",
  "items": [
    {"name": "Organic Bananas", "quantity": 1, "unit_price": 2.99},
    {"name": "Almond Milk", "quantity": 2, "unit_price": 4.49}
  ]
}
```

---

### Example 2: Warranty Tracker

**Use Case:** Extract product warranty information from receipts, warranty cards, or product labels.

**Schema:**
```json
{
  "brand": "string (manufacturer or brand name)",
  "model": "string (product model name/number)",
  "serial_number": "string (exact serial number if visible)",
  "purchase_date": "YYYY-MM-DD",
  "warranty_duration_months": "number (warranty period in months)",
  "purchase_price": "number (price paid)",
  "source": "string (store or seller name)",
  "category": "enum: Tech|Kitchen|Home|Automotive|Other",
  "notes": "string (any additional relevant info)"
}
```

**Sample Output:**
```json
{
  "brand": "Sony",
  "model": "WH-1000XM5",
  "serial_number": "S01-2847561",
  "purchase_date": "2024-01-10",
  "warranty_duration_months": 24,
  "purchase_price": 349.99,
  "source": "Best Buy",
  "category": "Tech",
  "notes": "Extended warranty available for purchase"
}
```

**Recommendations:**
- Add rule: "Copy serial numbers exactly as shown, including dashes and letters"
- Add rule: "If warranty is stated in years, convert to months (2 years = 24)"

---

### Example 3: Business Card Reader

**Use Case:** Extract contact information from business card photos.

**Schema:**
```json
{
  "name": "string (full name)",
  "title": "string (job title)",
  "company": "string (company name)",
  "email": "string (email address)",
  "phone": "string (phone number with country code)",
  "website": "string (company website URL)",
  "address": "string (office address if visible)",
  "linkedin": "string (LinkedIn URL if present)"
}
```

**Recommendations:**
- Set `max_image_width: 1200` (higher resolution for small text)
- Add rule: "Extract phone numbers with country code format"
- Add rule: "For LinkedIn, extract full URL not just username"

---

### Example 4: Invoice Processor

**Use Case:** Extract invoice details from PDF invoices for accounting.

**Schema:**
```json
{
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "vendor_name": "string",
  "vendor_address": "string",
  "subtotal": "number",
  "tax_amount": "number",
  "tax_rate": "number (percentage)",
  "total": "number",
  "currency": "string",
  "line_items": "array of {description, quantity, unit_price, amount}",
  "payment_terms": "string (Net 30, Due on Receipt, etc.)"
}
```

---

### Example 5: Medical Prescription Reader

**Use Case:** Extract medication details from prescription images.

**Schema:**
```json
{
  "patient_name": "string",
  "doctor_name": "string",
  "hospital": "string (hospital or clinic name)",
  "date": "YYYY-MM-DD",
  "medications": "array of {name, dosage, frequency, duration, instructions}",
  "diagnosis": "string (if mentioned)",
  "follow_up_date": "YYYY-MM-DD (if mentioned)"
}
```

**Recommendations:**
- Always enable `review_required: true` (critical for medical data)
- Add rule: "Copy medication names exactly as written"
- Add rule: "Include dosage units (mg, ml, etc.)"

---

### Example 6: Voice Memo Transcriber

**Use Case:** Extract action items and notes from voice recordings.

**Schema:**
```json
{
  "summary": "string (2-3 sentence summary)",
  "action_items": "array of {task, assignee, due_date}",
  "decisions_made": "array of strings",
  "topics_discussed": "array of strings",
  "follow_up_required": "boolean",
  "meeting_date": "YYYY-MM-DD (if mentioned)",
  "participants": "array of strings (names mentioned)"
}
```

**Recommendations:**
- Use Gemini (native audio support)
- Add rule: "If due date is relative (next week, tomorrow), calculate actual date"

---

## Execution Flow

### Phase 1: File Upload
```
User selects file → Validate type/size → Store temporarily
```

### Phase 2: Preprocessing
```
Image? → Resize to max_width, compress as JPEG
PDF? → Pass directly (API handles natively)
Audio? → Pass directly (Gemini handles natively)
```

### Phase 3: API Call
```
Build prompt with schema → Send to LLM → Receive response
Track: input_tokens, output_tokens, latency
```

### Phase 4: Response Parsing
```
Try JSON.parse → Try markdown block → Try regex → Return error
```

### Phase 5: Review Form
```
Display extracted data in editable form → User corrects if needed → Submit
```

### Phase 6: Save
```
Validate required fields → Sanitize strings → Save to database
```

---

## Output Structure

Every extraction returns an `ExtractionResult`:

```python
@dataclass
class ExtractionResult:
    data: dict                    # Extracted fields (your schema)
    input_tokens: int             # Tokens sent to API
    output_tokens: int            # Tokens in response
    cost_usd: float              # Estimated cost
    extraction_time_ms: float    # End-to-end latency
    file_type: str               # "image", "pdf", or "audio"
    error: Optional[str]         # Error message if failed
```

**Success Example:**
```python
ExtractionResult(
    data={"merchant": "Starbucks", "total": 5.75, ...},
    input_tokens=1247,
    output_tokens=89,
    cost_usd=0.00016,
    extraction_time_ms=2340.5,
    file_type="image",
    error=None
)
```

**Failure Example:**
```python
ExtractionResult(
    data={},
    input_tokens=0,
    output_tokens=0,
    cost_usd=0.0,
    extraction_time_ms=0,
    file_type="image",
    error="Could not process this image. The file may be corrupted."
)
```

---

## Recommendations

### Schema Design

1. **Be specific in descriptions** — "date of purchase" not just "date"
2. **Use enums for categories** — Reduces AI ambiguity
3. **Mark optional fields** — Add "(if visible)" to descriptions
4. **Limit array fields** — Specify max items if relevant

### Provider Selection

| Provider | Best For | Cost |
|----------|----------|------|
| **Gemini Flash** | Most use cases, audio | Lowest |
| **GPT-4 Vision** | Complex layouts | Higher |
| **Claude Vision** | Long documents | Medium |

### Image Optimization Settings

| Use Case | max_width | Quality |
|----------|-----------|---------|
| Receipts | 1024 | 85 |
| Business cards | 1200 | 90 |
| Documents | 1600 | 90 |
| Small text photos | 2048 | 95 |

### Rate Limiting

| User Type | Recommended Limit |
|-----------|-------------------|
| Free tier | 10-20/day |
| Paid tier | 50-100/day |
| Admin | 100-250/day |

---

## Troubleshooting

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| Empty extraction | Image too small/blurry | Increase max_width |
| Wrong field values | Ambiguous schema | Add specific descriptions |
| JSON parse errors | Complex response | Simplify schema |
| High token usage | Large images | Reduce max_width |
| Rate limit errors | Quota exceeded | Show limit message to user |

---

## Pre-Launch Checklist

- [ ] API key configured in environment/secrets
- [ ] Test connection endpoint works
- [ ] Sample extraction returns expected fields
- [ ] Review form displays all fields
- [ ] User can edit and save corrected data
- [ ] Rate limiting prevents abuse
- [ ] Error messages are user-friendly
- [ ] Cost tracking is recording (if enabled)
- [ ] Mobile upload works (if applicable)

---

## Next Steps After Generation

1. **Test with real data** — Use actual documents from your domain
2. **Refine the schema** — Add/remove fields based on extraction quality
3. **Tune the prompt** — Add rules for edge cases
4. **Monitor costs** — Check token usage after first 100 extractions
5. **Gather feedback** — Ask users if review form catches errors
