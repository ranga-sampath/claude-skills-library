# Overview: iptables-explain — Claude Code Skill

## What This Skill Is

An **operational Claude Code skill** — invoked via `/iptables-explain` — that reads an `iptables-save` snapshot and produces a plain-English security analysis of the ruleset. Analysis runs natively inside Claude Code; no external API key is required.

## The Problem It Solves

iptables rulesets are difficult to read. A production host may have dozens of chains across multiple tables — filter, nat, raw, mangle — including user-defined chains from Docker, fail2ban, UFW, WireGuard, and other tools. Understanding the cumulative effect of these rules (what is actually permitted, what is blocked, what the overall security posture is) requires tracing evaluation order across the full chain tree, accounting for policy defaults, and recognising known patterns.

This skill does that interpretation automatically, inside the Claude Code conversation, without leaving the terminal.

## Architecture: Three Stages

```
iptables-save output (.txt)
    │
    ▼
[Stage 1] Validate
    │  Check file exists, parser installed, python3 available
    ▼
[Stage 2] Parse  (iptables_parser.py)
    │  Convert iptables-save text → structured JSON
    │  Detects framework (iptables-nft vs iptables-legacy)
    │  Resolves chain references, extracts diagnostics
    ▼
[Stage 3] AI Analysis  (Claude Code — native)
       Reads structured JSON
       Applies expert analysis framework
       Returns: Framework, Default Policies, Rule-by-rule explanation,
                Security Posture Summary, Notable Findings
```

**Stages 1–2** run in `iptables_parser.py` (Python stdlib only — no pip installs).

**Stage 3** runs natively inside Claude Code — Claude IS the analyst. No separate API call. No Gemini. No OpenAI.

## What the Parser Produces

The parser converts the raw `iptables-save` text into a structured JSON document containing:

- **`framework`** — `"iptables-nft"` or `"iptables-legacy"`, detected from the file header comment
- **`family`** — `"ipv4"` or `"ipv6"`
- **`tables`** — all tables (filter, nat, raw, mangle, security), each with their chains, policies, and rules
- **`diagnostics`** — pre-computed summary: drop-policy chains, user-defined chains and their callers, active fail2ban bans, DNAT/MASQUERADE rules, conntrack position warnings
- **`parse_warnings`** — any structural anomalies detected

The diagnostics section is the key accelerator: Claude gets a pre-computed call graph of user-defined chains and a summary of drop/nat rules without having to re-derive them from the raw rule list.

## Why Structured JSON Instead of Raw Text?

`iptables-save` output is a flat line-by-line format designed for machine round-tripping, not human reading. Sending it directly to Claude would work but requires the LLM to re-parse syntax, track chain references, and infer the call graph — work that a deterministic Python parser can do reliably in milliseconds.

The structured JSON:
- Pre-resolves every `-j <CHAIN>` jump to its target
- Flags unresolved references (chains jumped to but not defined)
- Normalises extension options (`match_extensions`, `target_params`) into structured fields
- Detects framework variant from the header comment

## Framework Detection

iptables exists in two variants on modern Linux:

| Variant | Header | Kernel Backend | Interaction with nft |
|---|---|---|---|
| `iptables-legacy` | `iptables-save v1.8.x` (no suffix) | Legacy xtables | Independent |
| `iptables-nft` | `iptables-save v1.8.x (nf_tables)` | nftables kernel | Shares nf_tables with native nft rules |

The parser detects `(nf_tables)` in the header comment and sets `framework` accordingly. On Ubuntu 20.04+, Debian 11+, and most current distributions, iptables-nft is the default. The distinction matters when native `nft` rules also exist on the host — both share the same kernel data path.

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Parsing | Python stdlib | No pip installs; portable; readable |
| AI analysis | Claude Code native | No separate API key; Claude IS the LLM |
| Single parser file | Yes | Easy to copy; no module dependencies |
| Framework detection | From header comment | More reliable than version inference |
| diagnostics section | Pre-computed | Reduces LLM work; improves accuracy |

## What This Skill Intentionally Omits

| Omitted | Why |
|---|---|
| IPv6 auto-analysis | ip6tables-save is a separate file; invoke once per family |
| Live system querying | Takes a file snapshot — does not run `iptables` commands directly |
| Remediation commands | Analysis-only; specific remediation depends on context |
| Counter-based traffic analysis | Use `iptables-save -c` and read counters if needed — supported by the parser |
