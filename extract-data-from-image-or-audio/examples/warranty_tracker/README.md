# Warranty Tracker Example

Extract product warranty information from receipts, warranty cards, or product labels.

## Schema

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

## Configuration

```python
LLM_PROVIDER = "gemini"
MAX_IMAGE_WIDTH = 1024
JPEG_QUALITY = 85
```

## Custom Rules

- Copy serial numbers exactly as shown, including dashes and letters
- If warranty is stated in years, convert to months (2 years = 24)
- Look for extended warranty information

## Sample Output

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

## Supported File Types

- Receipt images (JPG, PNG)
- Warranty card photos
- Product label photos
- PDF warranty documents
- Voice memos describing purchases
