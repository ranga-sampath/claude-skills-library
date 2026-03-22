# nftables-explain — Claude Code Skill

A Claude Code skill that reads an `nft --json list ruleset` snapshot and produces a plain-English security analysis of the ruleset.

## What It Does

Given an nftables JSON snapshot, the skill:

1. **Parses** the nft JSON into structured form — normalises conntrack directives, ICMP types, named sets, and address families (Python stdlib only)
2. **Analyses** the ruleset natively using Claude — no external API key required
3. **Explains** in plain English: address families, default policies, chain-by-chain rules, named sets, and overall security posture

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | Usually pre-installed |
| Claude Code | [Install guide](https://docs.anthropic.com/en/docs/claude-code) |

No external Python packages required. No LLM API key required beyond Claude Code itself.

## Installation

```bash
# 1. Clone the skills library
git clone https://github.com/ranga-sampath/claude-skills-library
cd claude-skills-library/nftables-explain

# 2. Copy to ~/.claude/skills/ — Claude Code discovers skills from this global directory,
#    making the skill available in every session regardless of working directory.
mkdir -p ~/.claude/skills/nftables-explain
cp .claude/skills/nftables-explain/skill.md ~/.claude/skills/nftables-explain/
cp .claude/skills/nftables-explain/nftables_parser.py ~/.claude/skills/nftables-explain/
```

## Usage

```bash
# Capture nftables state
nft --json list ruleset > current.json

# Invoke the skill in Claude Code
/nftables-explain current.json
```

## Output

The report is displayed inline in the Claude Code conversation:

| Section | Content |
|---|---|
| **Address Families Covered** | ip, ip6, inet, arp, bridge, netdev |
| **Default Policies** | Hook chain → policy; drop policies highlighted |
| **Rules** | Chain-by-chain plain-English explanation |
| **Sets** | Named sets — contents and how they are used |
| **Security Posture Summary** | 2-4 sentence verdict |
| **Notable Findings** | Anything warranting attention |

See `examples/sample_explain_report.md` for a reference output.

## Repository Structure

```
nftables-explain/
├── .claude/skills/nftables-explain/
│   ├── skill.md              # Claude Code skill definition + analysis framework
│   └── nftables_parser.py    # nft JSON → structured JSON parser
├── docs/
│   ├── overview.md           # Architecture, parser output schema, design decisions
│   ├── how_to_use.md         # Installation, usage, troubleshooting
│   └── test_plan.md          # Test scenarios and ground truth verification
├── examples/
│   ├── fx-03-inet-drop-policy.json   # Sample input fixture
│   └── sample_explain_report.md      # Reference output
├── tests/                    # Parser unit tests (see netfilter-inspector source)
├── LICENSE
└── README.md
```

## Related Skills

- [`nftables-diff-explain`](../nftables-diff-explain/) — explain what changed between two nftables snapshots
- [`iptables-explain`](../iptables-explain/) — same for iptables
- [`iptables-diff-explain`](../iptables-diff-explain/) — explain iptables diff

## Part of the Claude Skills Library

This skill is part of [claude-skills-library](https://github.com/ranga-sampath/claude-skills-library) — a curated collection of production-grade Claude Code skills for network and security engineering.
