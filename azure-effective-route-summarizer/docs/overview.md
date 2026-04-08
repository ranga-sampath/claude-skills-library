# Overview: azure-effective-route-summarizer — Claude Code Skill

## What This Skill Is

An **operational Claude Code skill** — invoked via `/azure-effective-route-summarizer` — that reads the JSON output of `az network nic show-effective-route-table` and applies the Azure route selection algorithm to identify the single winning route for a target destination IP, explain why all competing routes were eliminated, and surface routing anomalies across the full table.

## The Problem It Solves

The Azure effective route table for a production NIC routinely contains 30–150 entries: system defaults, VNet peering routes, UDRs, BGP prefixes from ExpressRoute or VPN, and Service Endpoint routes — all mixed together. When traffic is misbehaving (bypassing a firewall, blackholing, taking an unexpected path), an engineer must mentally apply a multi-step selection algorithm across all those entries to find the one route Azure actually used.

The algorithm is not obvious. LPM is absolute — a /32 system route beats a /24 UDR, which surprises engineers who assume UDRs always win. BGP routes from ExpressRoute beat system defaults but lose to UDRs. Invalid routes (peering disconnected, gateway removed) look valid in the table but are never used. LLMs processing large JSON files often hallucinate the middle — missing the exact entry that explains the behaviour.

This skill forces a systematic scan, applies the correct priority order, and returns a deterministic single-winning-route answer with a named reason for every eliminated competitor.

## Architecture: Three Stages

```
az network nic show-effective-route-table output (JSON file)
    │
    ▼
[Stage 1] Validate
    │  Check file exists, preprocessor installed, python3 available
    ▼
[Stage 2] Preprocess  (route_preprocessor.py)
    │  Parse JSON → normalised flat route list
    │  Expand multi-prefix entries (one row per prefix)
    │  Parse prefix_length for each CIDR
    │  Flag invalid routes
    │  Produce parse_warnings for anomalies
    ▼
[Stage 3] AI Analysis  (Claude Code — native)
       Reads normalised route list
       Single-target mode: CIDR filter → LPM → precedence → verdict
       Audit mode: full table, anomaly detection, NVA warnings, invalid routes
```

**Stages 1–2** run in `route_preprocessor.py` (Python stdlib only — no pip installs).

**Stage 3** runs natively inside Claude Code — Claude IS the analyst.

### Stage 1 Validation Failures

| Failure | Skill Output |
|:--------|:-------------|
| File path does not exist | `Error: File not found — <path>` — skill halts |
| `python3` not available | `Error: python3 is required but was not found in PATH` — skill halts |
| `route_preprocessor.py` not in skill directory | `Error: route_preprocessor.py not found at <expected path>` — skill halts |
| File is not valid effective route table JSON | `Error: Not a valid effective route table — <reason>` — skill halts |

Validation failures produce a single-line error message and stop. No partial output is emitted.

### Stage 3 Output Contract

Stage 3 always produces human-readable markdown. It does not emit structured JSON. The output has two forms:

**Single-target mode (`--dst` provided):**
- One "Winning Route" section: the selected route, its hop type, and the selection reason (LPM or precedence)
- One "Eliminated Candidates" table: each competing route with a named reason for elimination
- Conditional warnings: NVA IP Forwarding reminder (when winner is VirtualAppliance), BGP tie flag (when tie is unresolvable), blackhole warning (when winner has `nextHopType: None`)
- Verdict label: `ACTIVE`, `BLACKHOLED`, or `BGP TIE — UNDETERMINED`

**Audit mode (no `--dst`):**
- Full normalised route table
- "Invalid Routes" section (if any)
- "NVA Routes" section listing all VirtualAppliance hops
- Findings summary

In both modes, if `parse_warnings` is non-empty, Claude must surface each warning before the analysis results.

## Azure Route Selection Algorithm

Azure selects exactly one route per destination. The algorithm applies in strict order:

### Step 1 — Longest Prefix Match (LPM)

The route whose address prefix encompasses the destination IP **and** has the longest prefix mask wins outright, regardless of source or type.

- A `/32` host route beats `/24` beats `/16` beats `0.0.0.0/0`
- LPM is absolute — a `/32` system default beats a `/24` UDR
- If only one route encompasses the destination, it wins trivially

### Step 2 — Precedence (equal prefix length only)

When two or more routes share the exact same prefix length and both encompass the destination, Azure applies a fixed precedence by source:

| Tier | Source Field | Description |
|:-----|:-------------|:------------|
| 1 | `User` | User Defined Routes (UDR) — attached to the subnet via route table |
| 2 | `VirtualNetworkGateway` | BGP routes — learned from VPN Gateway or ExpressRoute |
| 3 | `Default` | System routes — VNetLocal, Internet, VNet peering routes, and service endpoint routes all carry `source: Default` and fall in this tier |

A UDR at the same prefix length beats BGP, which beats any system route.

### Step 3 — BGP Tie-Breaker (same prefix, multiple BGP paths)

When two BGP routes have identical prefix lengths and both are from `VirtualNetworkGateway`, Azure uses AS Path length — shortest path wins. **This information is not present in the effective route table JSON.** When detected, the skill flags the ambiguity and asks the user to check the gateway.

### Invalid Routes Are Never Selected

Routes with `state: "Invalid"` are present in the table (peering disconnected, gateway removed, etc.) but Azure never uses them. The skill explicitly excludes them from analysis and flags them as a potential source of confusion.

## What the Preprocessor Produces

`route_preprocessor.py` converts the raw `az network nic show-effective-route-table` JSON into a normalised flat list:

```json
{
  "route_count": 12,
  "routes": [
    {
      "prefix": "10.50.1.0/24",
      "prefix_length": 24,
      "next_hop_type": "VnetLocal",
      "next_hop_ip": null,
      "source": "Default",
      "state": "Active",
      "route_name": null,
      "is_zero_route": false
    },
    {
      "prefix": "10.50.0.0/16",
      "prefix_length": 16,
      "next_hop_type": "VirtualAppliance",
      "next_hop_ip": "10.0.0.4",
      "source": "User",
      "state": "Active",
      "route_name": "route-to-firewall",
      "is_zero_route": false
    },
    {
      "prefix": "0.0.0.0/0",
      "prefix_length": 0,
      "next_hop_type": "Internet",
      "next_hop_ip": null,
      "source": "Default",
      "state": "Active",
      "route_name": null,
      "is_zero_route": true
    }
  ],
  "invalid_route_count": 1,
  "parse_warnings": []
}
```

Key fields:

| Field | Source | Purpose |
|:------|:-------|:--------|
| `prefix` | `addressPrefix[i]` | Normalised CIDR string |
| `prefix_length` | Parsed from prefix | Used for LPM comparison |
| `next_hop_type` | `nextHopType` | Routing action Azure will take |
| `next_hop_ip` | `nextHopIpAddress[0]` or null | Relevant for VirtualAppliance hops; see Multi-hop note below |
| `source` | `source` | Used for precedence tier |
| `state` | `state` | Active vs Invalid |
| `route_name` | `name` | Populated for UDRs; null for system routes |
| `is_zero_route` | `prefix == "0.0.0.0/0"` | Default route flag; ensures catch-all behavior is explicitly surfaced in output |

**Multi-hop note:** If a route entry contains more than one value in `nextHopIpAddress` (uncommon; seen on some VirtualNetworkGateway ECMP paths), the preprocessor takes the first address and emits a `parse_warning`. The analysis proceeds on the first address; the engineer should confirm the full ECMP set at the gateway.

## Multi-Prefix Entries

The raw Azure API can return a single route entry with multiple CIDRs in the `addressPrefix` array (common for VNet peering entries that aggregate multiple address spaces). The preprocessor expands each prefix into its own row, carrying forward all other fields, so the analysis framework always works with one-prefix-per-row.

## Supported Input Formats

| Format | Description |
|:-------|:------------|
| `{"value": [...]}` | Standard `az network nic show-effective-route-table -o json` output |
| `{"effectiveRoutes": [...]}` | Alternative field name seen in some SDK/portal exports |
| Raw list `[...]` | Direct array (e.g., from a scripted extraction) |

## NextHopType Reference

| Value | Meaning | IP Forwarding Note |
|:------|:--------|:-------------------|
| `VnetLocal` | Route stays within this VNet | — |
| `VnetPeering` | Routes via a peered VNet | — |
| `VirtualAppliance` | Routes via an NVA/firewall | NVA NIC must have IP Forwarding enabled |
| `VirtualNetworkGateway` | Routes via VPN/ER gateway | — |
| `Internet` | Routes via Azure's internet edge | — |
| `None` | Traffic is explicitly blackholed | No forwarding — packets dropped |

## NVA Asymmetry Warning

When the winning route has `next_hop_type == "VirtualAppliance"`, the skill emits a mandatory warning: verify that IP Forwarding is enabled on the NVA's NIC and confirm the return path routes through the same appliance. Asymmetric routing through NVAs is a frequent cause of silent connectivity failures — traffic reaches the destination but response packets take a different path, bypassing stateful inspection.

## Design Decisions

| Decision | Choice | Reason |
|:---------|:-------|:-------|
| Parsing | Python stdlib | No pip installs; portable |
| Multi-prefix expansion | Per-row in preprocessor | Keeps analysis framework simple — always one prefix per route |
| Invalid route handling | Include in output, flag separately | Engineers need to see them to understand "why not this route" |
| BGP tie-break | Flag, don't guess | AS Path is not in the JSON; fabricating a winner would be a hallucination |
| Zero route | Flag with `is_zero_route` | Catch-all behaviour deserves explicit callout |
| AI analysis | Claude Code native | No separate API key; Claude IS the analyst |

## What This Skill Intentionally Omits

| Omitted | Why |
|:--------|:----|
| NSG evaluation | An NSG may block traffic even if the route is correct — use `azure-security-rule-resolver` |
| Live Azure CLI execution | Takes a JSON file — does not call Azure APIs directly |
| Virtual WAN hub routing | Hub-managed routes are not visible on spoke NIC effective routes; flagged as a limitation |
| AS Path details | Not present in effective route table output |
| Route table assignment | Which subnet has which route table — not in the NIC output |
