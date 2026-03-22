# iptables-explain — Claude Code Skill

A Claude Code skill that reads an `iptables-save` snapshot and produces a plain-English security analysis of the ruleset.

## What It Does

Given an `iptables-save` output file, the skill:

1. **Parses** the snapshot into structured JSON — detects framework (`iptables-nft` vs `iptables-legacy`), resolves chain call graphs, extracts diagnostics
2. **Analyses** the ruleset natively using Claude — no external API key required
3. **Explains** in plain English: framework, default policies, chain-by-chain rule breakdown, fail2ban bans, Docker topology, overall security posture

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
cd claude-skills-library/iptables-explain

# 2. Copy to ~/.claude/skills/ — Claude Code discovers skills from this global directory,
#    making the skill available in every session regardless of working directory.
mkdir -p ~/.claude/skills/iptables-explain
cp .claude/skills/iptables-explain/skill.md ~/.claude/skills/iptables-explain/
cp .claude/skills/iptables-explain/iptables_parser.py ~/.claude/skills/iptables-explain/
```

## Usage

```bash
# Capture iptables state
iptables-save > current.txt

# Invoke the skill in Claude Code
/iptables-explain current.txt
```

## Output

The report is displayed inline in the Claude Code conversation:

| Section | Content |
|---|---|
| **Framework** | `iptables-nft` or `iptables-legacy` with explanation |
| **Default Policies** | Chain → policy table; DROP policies highlighted |
| **Rules** | Chain-by-chain plain-English explanation |
| **Security Posture Summary** | 2-4 sentence verdict |
| **Notable Findings** | Anything warranting attention |

See `examples/sample_explain_report.md` for a reference output.

## Repository Structure

```
iptables-explain/
├── .claude/skills/iptables-explain/
│   ├── skill.md              # Claude Code skill definition + analysis framework
│   └── iptables_parser.py    # iptables-save → structured JSON parser
├── docs/
│   ├── overview.md           # Architecture, parser output schema, design decisions
│   ├── how_to_use.md         # Installation, usage, troubleshooting
│   └── test_plan.md          # Test scenarios and ground truth verification
├── examples/
│   ├── ubuntu2404-docker-fail2ban.txt   # Sample input fixture
│   └── sample_explain_report.md        # Reference output
├── LICENSE
└── README.md
```

## Related Skills

- [`iptables-diff-explain`](../iptables-diff-explain/) — explain what changed between two iptables snapshots
- [`nftables-explain`](../nftables-explain/) — same for native nftables
- [`nftables-diff-explain`](../nftables-diff-explain/) — explain nftables diff

## Part of the Claude Skills Library

This skill is part of [claude-skills-library](https://github.com/ranga-sampath/claude-skills-library) — a curated collection of production-grade Claude Code skills for network and security engineering.
