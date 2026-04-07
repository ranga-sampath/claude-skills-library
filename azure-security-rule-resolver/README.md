# azure-security-rule-resolver — Claude Code Skill

A Claude Code skill that reads the JSON output of `az network nic list-effective-nsg` and resolves the Azure dual-gate NSG evaluation model to produce a definitive Allow/Deny verdict or a full security audit.

## What It Does

Given the effective NSG JSON for an Azure NIC, the skill:

1. **Parses** the JSON into a structured gate model — identifies subnet NSG and NIC NSG from the `association` field, normalises rules by priority, detects shadowed rules
2. **Analyses** in two modes: **Verdict mode** (all three tuple args provided) traces exact Azure evaluation order and returns Allow/Deny with the specific matching rule; **Audit mode** (any arg missing) produces per-gate rule tables with shadow detection and notable findings
3. **Explains** the result in plain English — gate names, rule names, priority numbers, actionable next steps

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | Usually pre-installed |
| Claude Code | [Install guide](https://docs.anthropic.com/en/docs/claude-code) |
| Azure CLI | Only needed to capture input; not required at analysis time |

No external Python packages required. No LLM API key required beyond Claude Code itself.

## Installation

```bash
# 1. Clone the skills library
git clone https://github.com/ranga-sampath/claude-skills-library
cd claude-skills-library/azure-security-rule-resolver

# 2. Copy to ~/.claude/skills/ — Claude Code discovers skills from this global directory,
#    making the skill available in every session regardless of working directory.
mkdir -p ~/.claude/skills/azure-security-rule-resolver
cp .claude/skills/azure-security-rule-resolver/skill.md ~/.claude/skills/azure-security-rule-resolver/
cp .claude/skills/azure-security-rule-resolver/nsg_preprocessor.py ~/.claude/skills/azure-security-rule-resolver/
```

## Usage

```bash
# Capture effective NSG state for a NIC
az network nic list-effective-nsg \
  --name <nic-name> \
  --resource-group <rg-name> \
  -o json > effective-nsg.json

# Verdict mode — is this specific traffic allowed?
/azure-security-rule-resolver effective-nsg.json \
  --src 10.0.1.5 \
  --dst 10.0.2.10:5432 \
  --proto tcp

# Audit mode — full rule analysis
/azure-security-rule-resolver effective-nsg.json
```

## Output

| Mode | Content |
|---|---|
| **Verdict** | Gate evaluation table, Final Verdict (ALLOWED/DENIED), root cause rule, actionable next step |
| **Audit** | Per-gate rule tables, shadowed rule callouts, service tag flags, notable findings |

See `examples/sample_resolver_report.md` for reference output.

## Repository Structure

```
azure-security-rule-resolver/
├── .claude/skills/azure-security-rule-resolver/
│   ├── skill.md                    # Claude Code skill definition + analysis framework
│   └── nsg_preprocessor.py         # az network nic list-effective-nsg JSON → structured JSON
├── docs/
│   ├── overview.md                 # Architecture, preprocessor output schema, design decisions
│   ├── how_to_use.md               # Installation, usage, workflows, troubleshooting
│   └── test_plan.md                # Test scenarios, fixture index, expected verdicts
├── examples/
│   └── sample_resolver_report.md   # Reference output for both modes
├── fixtures/                       # 10 synthetic test fixtures (see docs/test_plan.md)
├── proposed-skill.md
└── README.md
```

## Related Skills

- [`iptables-explain`](../iptables-explain/) — Linux NSG equivalent for iptables rulesets
- [`iptables-diff-explain`](../iptables-diff-explain/) — explain what changed between two iptables snapshots
- [`nftables-explain`](../nftables-explain/) — same for native nftables

## Part of the Claude Skills Library

This skill is part of [claude-skills-library](https://github.com/ranga-sampath/claude-skills-library) — a curated collection of production-grade Claude Code skills for network and security engineering.
