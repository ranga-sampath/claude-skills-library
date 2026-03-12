# Overview: PCAP Forensic Engine — Claude Code Skill

## What This Skill Is

An **operational Claude Code skill** — invoked via `/pcap-forensics` — that performs agentic network forensic analysis on packet capture files. Unlike code-generation skills (which produce application code), this skill executes a local pipeline and returns a diagnostic report directly inside the Claude Code conversation.

## The Problem It Solves

Network engineers routinely capture traffic with tcpdump or Wireshark when diagnosing incidents. The diagnostic bottleneck is not capturing — it's interpretation. A 30-second capture on a busy network can contain tens of thousands of packets across multiple protocols. Reading them manually takes hours. Expert-level cross-protocol correlation (e.g., connecting an unanswered ARP to an ICMP Host Unreachable to a TCP retransmission storm) is knowledge-intensive work that most engineers have to look up.

This skill does that interpretation in seconds, without leaving Claude Code.

## Architecture: Four Stages

```
.pcap file
    │
    ▼
[Stage 1] Validate
    │  Check file, verify tshark on PATH
    ▼
[Stage 2] Extract (tshark)
    │  Run targeted tshark commands per protocol
    │  ARP | ICMP | TCP | DNS
    ▼
[Stage 3] Semantic Reduction
    │  Compress raw packets → compact Semantic JSON
    │  Count, group, aggregate, surface anomalies only
    │  Saves <capture>_semantic.json to disk
    ▼
[Stage 4] AI Forensic Analysis (Claude Code — native)
       Reads Semantic JSON
       Applies expert diagnostic framework
       Returns: Executive Summary + Anomaly Table + RCA + Remediation
```

**Stages 1-3** run in `pcap_extractor.py` (Python + tshark, standard library only).

**Stage 4** runs natively inside Claude Code — no separate API call. Claude IS the AI analyst.

## Why Semantic JSON?

A raw 10MB pcap can contain hundreds of thousands of packets. Sending that directly to an LLM would be prohibitively expensive (millions of tokens) and would exceed any context window. The Semantic JSON is the critical bridge — it aggregates, summarizes, and filters to produce a compact representation containing everything needed for accurate diagnosis in under 5,000 tokens.

Reduction strategies:
- **Count, don't list** — "TCP retransmissions: 47" instead of listing all 47 packets
- **Group by conversation** — aggregate per TCP stream, per DNS query name, per ICMP sequence
- **Surface anomalies only** — include individual packet details only for statistical outliers
- **Timing summaries** — min/median/max/p95 instead of raw delta arrays

## Protocol Coverage

| Layer | Protocol | What's Detected |
|---|---|---|
| L2 | ARP | IP-MAC conflicts (spoofing), silent hosts, gratuitous ARP floods |
| L3 | ICMP | Host/network unreachable, PMTUD black holes, routing loops (TTL exceeded), redirect attacks |
| L4 | TCP | Retransmission storms, zero-window stalls, handshake failures, RST teardowns, duplicate ACKs, out-of-order |
| L7 | DNS | DGA malware beaconing, SERVFAIL zones, DNS tunneling indicators, slow resolvers, rogue servers |

Cross-protocol correlation catches what single-protocol analysis misses — e.g., connecting ARP unanswered + ICMP Host Unreachable into a confirmed host-down verdict.

## Comparison Modes

**Temporal** (`--compare`, default): Two captures from the same segment at different times. Identifies what changed — regressions, improvements, new issues, resolved issues. Normalizes by rate/ratio rather than raw packet count.

**Endpoint Correlation** (`--compare --mode endpoint-correlation`): Two captures from source and destination endpoints of the same path, taken simultaneously. Identifies where packets are being dropped, delayed, or altered in transit.

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Packet parsing | tshark via subprocess | Battle-tested; avoids reinventing pcap parsing; surgical field extraction |
| AI analysis | Claude Code native | Claude IS the AI; no separate API call or API key required |
| External dependencies | None (stdlib only) | Simpler install; no pip/uv required |
| Single file extractor | Yes | Portable; readable top-to-bottom; easy to copy |
| Privacy | Metadata only | tshark extracts headers and flags — no payload content ever extracted |

## What This Skill Intentionally Omits

| Omitted | Why |
|---|---|
| Web UI | CLI is simpler; no auth, no hosting |
| Database | No persistent state; each run is independent |
| Additional protocols (HTTP, TLS, DHCP) | Additive in future versions; ARP/ICMP/TCP/DNS covers >90% of real incidents |
| Automated test pcaps | Sample pcaps from the source project (`nw-forensics/agentic-pcap-forensic-engine`) can be used directly |
