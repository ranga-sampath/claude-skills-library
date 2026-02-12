# AI Extraction Pipeline Skill

A reusable Claude Code skill for building AI-powered data extraction pipelines with the "Safety Net" pattern.

## What This Skill Does

Generates a complete pipeline for extracting structured data from user uploads (images, PDFs, audio) using LLMs, with mandatory user review before saving.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ User Upload  │────►│ AI Extraction│────►│ Review Form  │────►│ Save to DB   │
│ (file)       │     │ (structured) │     │ (editable)   │     │ (confirmed)  │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

## Key Features

- **Multi-format support** — Images, PDFs, and audio files
- **Multiple LLM providers** — Gemini, OpenAI, Claude
- **Image optimization** — Automatic resize/compress to reduce API costs
- **Safety Net pattern** — Users always verify AI output before saving
- **Rate limiting** — Per-user daily limits to prevent API abuse
- **Cost tracking** — Token usage and estimated cost per extraction
- **Error handling** — User-friendly error messages

## Quick Start

### Option 1: Use as Claude Code Skill

Copy the skill definition to your project:

```bash
mkdir -p .claude/skills
cp -r ai-extraction-skill/.claude/skills/ai_extraction .claude/skills/
```

Then invoke in Claude Code:

```
/ai-extraction
```

### Option 2: Use Templates Directly

Copy the template files and customize for your use case:

```bash
cp ai-extraction-skill/templates/* your-project/
```

## Documentation

- [Skill Overview](docs/overview.md) — Architecture, components, and design decisions
- [How to Use](docs/how_to_use.md) — Step-by-step guide with examples
- [Configuration](docs/configuration.md) — All customization options

## Examples

| Example | Description |
|---------|-------------|
| [Receipt Scanner](examples/receipt_scanner/) | Extract purchase details from receipt photos |
| [Warranty Tracker](examples/warranty_tracker/) | Extract product warranty info from receipts/documents |
| [Business Card Reader](examples/business_card_reader/) | Extract contact info from business cards |

## Supported Frameworks

- Streamlit (primary)
- Flask
- FastAPI

## Supported LLM Providers

| Provider | Image | PDF | Audio | Cost |
|----------|-------|-----|-------|------|
| Google Gemini | ✅ | ✅ | ✅ | Lowest |
| OpenAI GPT-4 | ✅ | ✅ | Via Whisper | Higher |
| Anthropic Claude | ✅ | ✅ | ❌ | Medium |

## Requirements

- Python 3.10+
- LLM provider API key
- Web framework (Streamlit, Flask, or FastAPI)

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read the documentation before submitting PRs.
