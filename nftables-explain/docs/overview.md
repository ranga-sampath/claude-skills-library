# Overview: nftables-explain — Claude Code Skill

## What This Skill Is

An **operational Claude Code skill** — invoked via `/nftables-explain` — that reads an `nft --json list ruleset` snapshot and produces a plain-English security analysis of the ruleset. Analysis runs natively inside Claude Code; no external API key is required.

## The Problem It Solves

nftables rulesets are more expressive than iptables but also more complex to read. A single `inet` table can contain rules for both IPv4 and IPv6. Named sets can contain thousands of IP addresses referenced by name. Conntrack directives (`ct state`, `ct direction`, `ct mark`, `ct zone`) encode nuanced packet classification logic that is not obvious from raw JSON. Address families (ip, ip6, inet, arp, bridge, netdev) govern which traffic each table sees.

This skill interprets all of that, producing a chain-by-chain explanation, set descriptions, and a plain-English security posture verdict — inside the Claude Code conversation.

## Architecture: Three Stages

```
nft --json list ruleset output (.json)
    │
    ▼
[Stage 1] Validate
    │  Check file exists, parser installed, python3 available
    ▼
[Stage 2] Parse  (nftables_parser.py)
    │  Convert nft JSON → structured JSON
    │  Normalise expressions: ct state, ICMP type, ports, addresses
    │  Extract sets, maps, chain call graph
    │  Detect unresolved set references
    ▼
[Stage 3] AI Analysis  (Claude Code — native)
       Reads structured JSON
       Applies expert analysis framework
       Returns: Address Families, Default Policies, Rule-by-rule explanation,
                Sets, Security Posture Summary, Notable Findings
```

**Stages 1–2** run in `nftables_parser.py` (Python stdlib only — no pip installs).

**Stage 3** runs natively inside Claude Code — no separate API call or API key.

## What the Parser Produces

The parser converts the raw `nft --json list ruleset` output into a structured JSON document containing:

- **`tables`** — keyed by `"<family> <name>"` (e.g. `"inet filter"`, `"ip nat"`). Each table contains:
  - **`chains`** — with hook, priority, policy, and fully parsed rules
  - **`sets`** — named sets and maps with their type and element list
- **`diagnostics`** — drop-policy chains, unresolved set references (`@setname` in a rule but no matching set definition), inet tables, sets referenced in rules
- **`nft_version`** / **`json_schema_version`** — from the nft JSON metadata

Each rule is normalised into structured fields:
- `verdict`, `protocol`, `src_addr`, `dst_addr`, `src_port`, `dst_port`
- `ct_state`, `ct_direction`, `ct_mark`, `ct_zone`
- `icmp_type`, `icmp_code`, `in_interface`, `out_interface`
- `set_references` — named sets referenced in this rule (e.g. `@blocklist`)
- `raw_expressions` — the original nft JSON expression list, for complex/opaque rules

## nftables vs iptables: Key Differences for Analysis

| Aspect | iptables | nftables |
|---|---|---|
| Input format | Text (`iptables-save`) | JSON (`nft --json list ruleset`) |
| Address families | Separate tools (iptables, ip6tables) | Single tool, per-table `family` field |
| `inet` family | Not available | Covers both IPv4 and IPv6 in one table |
| Named sets | Not native | First-class: `@setname` in rules |
| Conntrack | `-m state`/`-m conntrack` | `ct state`, `ct direction`, `ct mark`, `ct zone` |
| Rule syntax | Target field | Verdict field |
| Raw data | `raw_rule` string | `raw_expressions` list |

## Address Family Coverage

| Family | Traffic Covered |
|---|---|
| `ip` | IPv4 only |
| `ip6` | IPv6 only |
| `inet` | Both IPv4 and IPv6 — single ruleset governs both |
| `arp` | ARP packets |
| `bridge` | Bridged traffic (Docker, VMs) |
| `netdev` | Per-device (ingress/egress hooks, XDP-adjacent) |

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Parsing | Python stdlib | No pip installs; portable |
| AI analysis | Claude Code native | No separate API key |
| Expression normalisation | Per-field extraction + `raw_expressions` fallback | Maximises structured coverage; preserves opaque expressions for LLM inspection |
| Sets under each table | Yes | Sets are table-scoped in nftables; co-location makes lookup natural |

## What This Skill Intentionally Omits

| Omitted | Why |
|---|---|
| Live system querying | Takes a file snapshot — does not run `nft` commands directly |
| Map value resolution | Maps (verdict maps, nat maps) are identified but not fully expanded |
| Flowtable analysis | Flowtables are not yet parsed |
| Remediation commands | Analysis-only |
