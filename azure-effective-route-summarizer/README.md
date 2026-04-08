# azure-effective-route-summarizer — Claude Code Skill

A Claude Code skill that reads the JSON output of `az network nic show-effective-route-table` and applies the Azure route selection algorithm to identify the single winning route for a target destination IP — explaining exactly why every competing route was eliminated.

## What It Does

Given the effective route table JSON for an Azure NIC, the skill:

1. **Parses** the JSON into a normalised flat route list — one row per prefix, expanded from multi-prefix entries, with invalid routes flagged
2. **Analyses** in two modes: **Single-target mode** (`--dst <IP>`) applies LPM → precedence → BGP tie-break and returns the Winning Route with per-candidate elimination reasons; **Audit mode** (no `--dst`) produces a full sorted route table with NVA warnings, blackhole detection, and invalid route callouts
3. **Explains** the result in plain English — prefix lengths, source tiers, next hop IPs, and actionable next steps

## Prerequisites

| Requirement | Notes |
|:------------|:------|
| Python 3.10+ | Usually pre-installed |
| Claude Code | [Install guide](https://docs.anthropic.com/en/docs/claude-code) |
| Azure CLI | Only needed to capture input; not required at analysis time |

No external Python packages required.

## Installation

```bash
# 1. Clone the skills library
git clone https://github.com/ranga-sampath/claude-skills-library
cd claude-skills-library/azure-effective-route-summarizer

# 2. Copy to ~/.claude/skills/ — Claude Code discovers skills from this global directory,
#    making the skill available in every session regardless of working directory.
mkdir -p ~/.claude/skills/azure-effective-route-summarizer
cp .claude/skills/azure-effective-route-summarizer/skill.md \
   ~/.claude/skills/azure-effective-route-summarizer/
cp .claude/skills/azure-effective-route-summarizer/route_preprocessor.py \
   ~/.claude/skills/azure-effective-route-summarizer/
```

## Usage

```bash
# Capture the effective route table for a NIC
az network nic show-effective-route-table \
  --name <nic-name> \
  --resource-group <rg-name> \
  -o json > routes.json

# Single-target mode — which route wins for this destination IP?
/azure-effective-route-summarizer routes.json --dst 10.50.1.10

# Audit mode — full route table analysis
/azure-effective-route-summarizer routes.json
```

## Output

| Mode | Content |
|:-----|:--------|
| **Single-target** | Winning Route table with all candidates, LPM/precedence reason, NVA and blackhole warnings |
| **Audit** | Full sorted route table, invalid route section, notable findings (NVA routes, blackholes, BGP state) |

## Repository Structure

```
azure-effective-route-summarizer/
├── .claude/skills/azure-effective-route-summarizer/
│   ├── skill.md                    # Claude Code skill definition + analysis framework
│   └── route_preprocessor.py       # az network nic show-effective-route-table JSON → normalised JSON
├── docs/
│   ├── overview.md                 # Architecture, preprocessor schema, design decisions
│   ├── how_to_use.md               # Installation, usage, workflows, troubleshooting
│   └── test_plan.md                # 15 test scenarios, fixture index, expected verdicts
├── fixtures/                       # 15 synthetic test fixtures (see docs/test_plan.md)
│   ├── fx-01-basic-vnet-local.json
│   ├── fx-02-udr-same-prefix.json
│   ├── fx-03-lpm-beats-udr.json
│   ├── fx-04-nva-udr.json
│   ├── fx-05-minimal-routes.json
│   ├── fx-06-bgp-vs-system.json
│   ├── fx-07-invalid-route.json
│   ├── fx-08-host-route-slash32.json
│   ├── fx-09-no-matching-route.json
│   ├── fx-10-blackhole-none-hop.json
│   ├── fx-11-multi-prefix-entry.json
│   ├── fx-12-hub-spoke-production.json
│   ├── fx-13-vnet-peering-routes.json
│   ├── fx-14-bgp-tie-same-prefix.json
│   └── fx-15-overlapping-udrs.json
├── examples/
│   └── sample_resolver_report.md  # Reference output for both modes (real run output)
├── LICENSE
└── README.md
```

## Route Selection Algorithm

The skill applies the Azure algorithm in strict order:

1. **Filter** — Active routes only; routes with `state=Invalid` are never eligible
2. **Longest Prefix Match** — highest `prefix_length` wins unconditionally (`/32` beats `/24` beats `/0`)
3. **Source Precedence** (tied prefix lengths only) — UDR > BGP > System Default
4. **BGP Tie-Breaker** (two BGP routes, same prefix) — AS Path length; not in JSON → flagged, not guessed

## Related Skills

- [`azure-security-rule-resolver`](../azure-security-rule-resolver/) — evaluate Azure NSG rules once routing is confirmed correct
- [`iptables-explain`](../iptables-explain/) — Linux firewall analysis for traffic blocked inside the VM
- [`pcap-forensics`](../pcap-forensics/) — packet-level evidence for drops not explained by routing or NSG

## Part of the Claude Skills Library

This skill is part of [claude-skills-library](https://github.com/ranga-sampath/claude-skills-library) — a curated collection of production-grade Claude Code skills for network and security engineering.
