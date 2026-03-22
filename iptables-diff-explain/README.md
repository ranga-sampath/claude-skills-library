# iptables-diff-explain — Claude Code Skill

A Claude Code skill that compares two `iptables-save` snapshots and produces a plain-English explanation of what changed and what the security impact is.

## What It Does

Given two `iptables-save` output files (before and after a change), the skill:

1. **Parses** both snapshots into structured JSON (Python stdlib only)
2. **Diffs** the two snapshots — rules added/removed, chains added/removed, policy changes, repositioned rules
3. **Explains** in plain English: what changed, whether it tightens or loosens the posture, and what to verify

No external API key required — analysis is performed natively by Claude.

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
cd claude-skills-library/iptables-diff-explain

# 2. Copy to ~/.claude/skills/ — Claude Code discovers skills from this global directory,
#    making the skill available in every session regardless of working directory.
mkdir -p ~/.claude/skills/iptables-diff-explain
cp .claude/skills/iptables-diff-explain/skill.md ~/.claude/skills/iptables-diff-explain/
cp .claude/skills/iptables-diff-explain/iptables_parser.py ~/.claude/skills/iptables-diff-explain/
cp .claude/skills/iptables-diff-explain/iptables_diff.py ~/.claude/skills/iptables-diff-explain/
```

## Usage

```bash
# Capture baseline before a change
iptables-save > before.txt

# ... make changes ...

# Capture current state
iptables-save > after.txt

# Invoke the skill in Claude Code
/iptables-diff-explain before.txt after.txt
```

## Output

The report is displayed inline in the Claude Code conversation:

| Section | Content |
|---|---|
| **Change Summary** | Count of what changed, nature of the change |
| **Policy Changes** | Default policy changes — highest impact, always led first |
| **Rules Added / Removed** | What each rule change permits or blocks |
| **Chains Added / Removed** | Chain purpose with full rule contents |
| **Overall Assessment** | Tightening or loosening verdict with blast radius |
| **Recommended Actions** | Specific verification steps (critical changes only) |

See `examples/sample_diff_report.md` for a reference output.

## Repository Structure

```
iptables-diff-explain/
├── .claude/skills/iptables-diff-explain/
│   ├── skill.md              # Claude Code skill definition + analysis framework
│   ├── iptables_parser.py    # iptables-save → structured JSON parser
│   └── iptables_diff.py      # Structured JSON diff engine
├── docs/
│   ├── overview.md           # Architecture, diff schema, change detection logic
│   ├── how_to_use.md         # Installation, usage, troubleshooting
│   └── test_plan.md          # Test scenarios and ground truth verification
├── examples/
│   ├── ubuntu2404-clean.txt          # Sample before fixture
│   ├── ubuntu2404-cis-hardened.txt   # Sample after fixture
│   └── sample_diff_report.md         # Reference output
├── LICENSE
└── README.md
```

## Related Skills

- [`iptables-explain`](../iptables-explain/) — explain a single iptables snapshot
- [`nftables-explain`](../nftables-explain/) — same for native nftables
- [`nftables-diff-explain`](../nftables-diff-explain/) — explain nftables diff

## Part of the Claude Skills Library

This skill is part of [claude-skills-library](https://github.com/ranga-sampath/claude-skills-library) — a curated collection of production-grade Claude Code skills for network and security engineering.
