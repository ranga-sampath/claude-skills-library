# Business Card Reader Example

Extract contact information from business card photos.

## Schema

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

## Configuration

```python
LLM_PROVIDER = "gemini"
MAX_IMAGE_WIDTH = 1200  # Higher for small text
JPEG_QUALITY = 90
```

## Custom Rules

- Extract phone numbers with country code format
- For LinkedIn, extract full URL not just username
- Include all phone numbers if multiple are present
- Email addresses should be lowercase

## Sample Output

```json
{
  "name": "John Smith",
  "title": "Senior Software Engineer",
  "company": "Acme Corporation",
  "email": "john.smith@acme.com",
  "phone": "+1-555-123-4567",
  "website": "https://www.acme.com",
  "address": "123 Tech Park, San Francisco, CA 94105",
  "linkedin": "https://linkedin.com/in/johnsmith"
}
```

## Tips

- Ensure good lighting when photographing cards
- Avoid glare from glossy cards
- Keep the card flat and fully in frame
- Higher resolution helps with small text
