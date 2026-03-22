# nftables-diff-explain — Claude Code Skill

A Claude Code skill that compares two `nft --json list ruleset` snapshots and produces a plain-English explanation of what changed and what the security impact is.

## What It Does

Given two nftables JSON snapshots (before and after a change), the skill:

1. **Parses** both snapshots into structured form (Python stdlib only)
2. **Diffs** the two snapshots — rules added/removed, chains added/removed, policy changes, repositioned and in-place replaced rules
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
cd claude-skills-library/nftables-diff-explain

# 2. Copy to ~/.claude/skills/ — Claude Code discovers skills from this global directory,
#    making the skill available in every session regardless of working directory.
mkdir -p ~/.claude/skills/nftables-diff-explain
cp .claude/skills/nftables-diff-explain/skill.md ~/.claude/skills/nftables-diff-explain/
cp .claude/skills/nftables-diff-explain/nftables_parser.py ~/.claude/skills/nftables-diff-explain/
cp .claude/skills/nftables-diff-explain/nftables_diff.py ~/.claude/skills/nftables-diff-explain/
```

## Usage

```bash
# Capture baseline before a change
nft --json list ruleset > before.json

# ... make changes ...

# Capture current state
nft --json list ruleset > after.json

# Invoke the skill in Claude Code
/nftables-diff-explain before.json after.json
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
nftables-diff-explain/
├── .claude/skills/nftables-diff-explain/
│   ├── skill.md              # Claude Code skill definition + analysis framework
│   ├── nftables_parser.py    # nft JSON → structured JSON parser
│   └── nftables_diff.py      # Structured JSON diff engine
├── docs/
│   ├── overview.md           # Architecture, diff schema, rule identity, parse warnings
│   ├── how_to_use.md         # Installation, usage, troubleshooting
│   └── test_plan.md          # Test scenarios and ground truth verification
├── examples/
│   ├── fx-03-inet-drop-policy.json   # Sample before fixture
│   ├── fx-12-icmp-ct.json            # Sample after fixture
│   └── sample_diff_report.md         # Reference output
├── tests/                    # Differ unit tests (see netfilter-inspector source)
├── LICENSE
└── README.md
```

## Related Skills

- [`nftables-explain`](../nftables-explain/) — explain a single nftables snapshot
- [`iptables-explain`](../iptables-explain/) — same for iptables
- [`iptables-diff-explain`](../iptables-diff-explain/) — explain iptables diff

## Part of the Claude Skills Library

This skill is part of [claude-skills-library](https://github.com/ranga-sampath/claude-skills-library) — a curated collection of production-grade Claude Code skills for network and security engineering.
