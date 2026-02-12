# Receipt Scanner Example

Extract purchase details from receipt photos for expense tracking.

## Schema

```json
{
  "merchant": "string (store or business name)",
  "date": "YYYY-MM-DD (purchase date)",
  "total": "number (total amount paid)",
  "currency": "string (3-letter code)",
  "payment_method": "string (cash, card, UPI)",
  "category": "enum: Food|Transport|Shopping|Entertainment|Utilities|Other",
  "items": "array of {name, quantity, unit_price}"
}
```

## Configuration

```python
LLM_PROVIDER = "gemini"
MAX_IMAGE_WIDTH = 1024
JPEG_QUALITY = 85
```

## Custom Rules

- Extract line items if visible
- Identify payment method from receipt
- Currency should be 3-letter ISO code

## Sample Output

```json
{
  "merchant": "Whole Foods Market",
  "date": "2024-01-15",
  "total": 47.83,
  "currency": "USD",
  "payment_method": "Credit Card",
  "category": "Food",
  "items": [
    {"name": "Organic Bananas", "quantity": 1, "unit_price": 2.99}
  ]
}
```
