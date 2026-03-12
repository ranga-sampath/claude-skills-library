# PCAP Forensic Engine — Claude Code Skill

An operational Claude Code skill that performs AI-powered network forensic analysis on `.pcap` packet captures. Drop a capture file, get a root cause analysis report.

## What It Does

Runs a four-stage pipeline entirely on your local machine:

1. **Validate** — checks the file, verifies tshark is installed
2. **Extract** — runs targeted tshark commands to pull protocol metadata (ARP, ICMP, TCP, DNS)
3. **Reduce** — compresses raw packet data into a compact Semantic JSON (up to 95% token reduction)
4. **Analyze** — Claude reads the Semantic JSON and performs expert-level forensic diagnosis natively — no external API call needed

Detects:
- ARP spoofing and silent hosts (L2)
- ICMP unreachable codes, PMTUD black holes, routing loops, redirect attacks (L3)
- TCP retransmission storms, zero-window stalls, RST teardowns, handshake failures (L4)
- DNS malware beaconing (DGA), SERVFAIL zones, tunneling indicators, slow resolvers (L7)
- Cross-protocol correlation (e.g., ARP unanswered + ICMP Host Unreachable = confirmed host down)

## Prerequisites

| Requirement | Install |
|---|---|
| Python 3.10+ | Usually pre-installed |
| tshark (Wireshark CLI) | `brew install wireshark` / `sudo apt install tshark` |
| Claude Code | [Install guide](https://docs.anthropic.com/en/docs/claude-code) |

No external Python packages required. The extractor uses Python standard library only.

## Installation

```bash
# 1. Clone the skills library
git clone https://github.com/ranga-sampath/claude-skills-library
cd claude-skills-library/pcap-forensics

# 2. Install the skill globally in Claude Code
mkdir -p ~/.claude/skills/pcap-forensics
cp .claude/skills/pcap-forensics/skill.md ~/.claude/skills/pcap-forensics/
cp .claude/skills/pcap-forensics/pcap_extractor.py ~/.claude/skills/pcap-forensics/

# 3. Verify tshark is available
tshark --version
```

That's it. No API keys. No virtual environments. No package installs.

## Usage

Open Claude Code in any directory and invoke:

```
# Single capture — forensic analysis
/pcap-forensics ~/captures/incident-2026-03-11.pcap

# Temporal compare — what changed between two captures?
/pcap-forensics ~/captures/baseline.pcap --compare ~/captures/after-change.pcap

# Endpoint correlation — where are packets being dropped between source and dest?
/pcap-forensics ~/captures/source-side.pcap --compare ~/captures/dest-side.pcap --mode endpoint-correlation
```

## Output

Each run produces two artifacts written to the same directory as the input file:

| Artifact | Description |
|---|---|
| `<capture>_semantic.json` | Structured protocol metadata — reusable for scripting or dashboards |
| Forensic report (inline) | Displayed in the Claude Code conversation |

The report includes:
- **Executive Summary** — 2-4 sentences, most critical finding first
- **Anomaly Table** — severity-ranked (CRITICAL / HIGH / MEDIUM / LOW / INFO) with frame references
- **Root Cause Analysis** — protocol-level explanation for HIGH/CRITICAL findings
- **Remediation** — specific CLI commands for each finding

## Privacy

The extractor pulls **metadata only** — IP addresses, port numbers, flags, timing, and counts. Packet payloads are never extracted or sent anywhere. The Semantic JSON never leaves your machine.

## Repository Structure

```
pcap-forensics/
├── .claude/skills/pcap-forensics/
│   ├── skill.md              # Claude Code skill definition + analysis framework
│   └── pcap_extractor.py     # tshark extraction + semantic reduction (Stages 1-3)
├── docs/
│   ├── overview.md           # Architecture and design decisions
│   ├── how_to_use.md         # Detailed usage guide with examples
│   └── test_plan.md          # Verification steps and test scenarios
├── examples/
│   └── sample_forensic_report.md   # Reference output
├── tests/
│   └── TEST_REPORT.md        # Manual test results
├── LICENSE
└── README.md
```

## Part of the Claude Skills Library

This skill is part of [claude-skills-library](https://github.com/ranga-sampath/claude-skills-library) — a curated collection of production-grade Claude Code skills.
