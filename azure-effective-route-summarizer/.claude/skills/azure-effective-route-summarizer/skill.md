---
name: azure-effective-route-summarizer
description: Use when the user provides `az network nic show-effective-route-table` JSON and asks why traffic is taking an unexpected path, which route wins for a destination IP, if traffic is being blackholed, or wants to verify BGP or UDR routes are active. Trigger phrases include "which route wins", "why is traffic bypassing the firewall", "blackhole route", "effective routes for this NIC", "route table analysis", "BGP route active", "why is my traffic not going through the NVA", "check my routing". Do NOT use for NSG rule questions (use azure-security-rule-resolver), route table design or configuration, or general Azure networking questions without a route table JSON file.
---

# azure-effective-route-summarizer — Claude Code Skill

## Description

Resolves the Azure route selection algorithm against a specific destination IP and returns a deterministic Winning Route verdict — or audits the full effective route table for anomalies. Input is the JSON output of `az network nic show-effective-route-table`.

## When to Use

Invoke when the user:
- Provides `az network nic show-effective-route-table` JSON and asks why traffic is taking an unexpected path
- Asks "why is my traffic bypassing the firewall?" or "which route wins for this IP?"
- Suspects a blackhole (traffic disappearing silently)
- Wants to verify that BGP or UDR routes are active and winning as expected
- Uses `/azure-effective-route-summarizer` explicitly

## Invocation

```
# Single-target mode — find the winning route for a specific destination IP
/azure-effective-route-summarizer <routes.json> --dst <IP>

# Audit mode — full route table analysis, no specific destination
/azure-effective-route-summarizer <routes.json>
```

**Arguments:**
- `FILE` — required. Path to the JSON output of `az network nic show-effective-route-table`.
- `--dst <IP>` — optional. The destination IP to evaluate. If provided: Single-target mode. If omitted: Audit mode.

---

## Execution Steps

### Step 1 — Parse Arguments

Extract from the invocation:
- `FILE` — required
- `--dst <IP>` — optional

If no `FILE` is provided, respond with usage and stop:
```
Usage:
  /azure-effective-route-summarizer <routes.json> [--dst <IP>]

To capture the input:
  az network nic show-effective-route-table \
    --resource-group <RG> --name <NIC_NAME> -o json > routes.json
```

If `--dst` is provided, validate that it is a valid IPv4 address. If not:
```
Error: --dst must be a valid IPv4 address (e.g. 10.50.1.10).
```
Stop.

---

### Step 2 — Pre-flight Checks

Run these checks using Bash. Fail fast with a clear message.

**Check 1: File exists**
```bash
test -f "<FILE>" && echo "OK" || echo "NOT_FOUND"
```
If NOT_FOUND: `Error: File not found: <FILE>`  Stop.

**Check 2: Preprocessor is installed**
```bash
ls ~/.claude/skills/azure-effective-route-summarizer/route_preprocessor.py 2>/dev/null && echo "FOUND" || echo "NOT_FOUND"
```
If NOT_FOUND:
```
Error: route_preprocessor.py not found at ~/.claude/skills/azure-effective-route-summarizer/
Install it by copying it from the skill repo:
  cp <repo>/azure-effective-route-summarizer/.claude/skills/azure-effective-route-summarizer/route_preprocessor.py \
     ~/.claude/skills/azure-effective-route-summarizer/
```
Stop.

**Check 3: python3 is available**
```bash
python3 --version 2>&1
```
If not found: `Error: python3 is not installed or not on PATH.`  Stop.

---

### Step 3 — Preprocess the JSON

```bash
python3 ~/.claude/skills/azure-effective-route-summarizer/route_preprocessor.py "<FILE>"
```

Capture the JSON output. If the preprocessor exits non-zero or the output contains an `"error"` key:
```
Error: Failed to parse <FILE>.
Ensure the file is the output of: az network nic show-effective-route-table -o json
Detail: <error message from preprocessor>
```
Stop.

If `parse_warnings` is non-empty, display each warning before proceeding.

---

### Step 4 — Analyse

Apply the analysis framework below based on the mode (Single-target or Audit).

---

## Analysis Framework

### Azure Route Selection Algorithm

Azure selects exactly one route per packet. Apply the following algorithm in strict order. Never skip a step.

#### Step A — Filter by CIDR containment (Single-target mode only)

From the full route list, keep only routes where:
1. `state == "Active"` (case-insensitive; the preprocessor normalises to title-case) — Invalid and Unknown routes are NEVER selected
2. The destination IP falls within the route's prefix (standard CIDR containment)

If no Active routes encompass the destination IP, output:
```
No route found for destination <IP>.
The effective route table contains no Active prefix that encompasses this address.
Traffic to this destination will be dropped.
```
Stop. Do not fabricate a route.

#### Step B — Longest Prefix Match (LPM)

Among the candidate routes, the route with the highest `prefix_length` wins unconditionally.

- `/32` beats `/24` beats `/16` beats `/8` beats `0.0.0.0/0`
- LPM is absolute — a `/32` system route beats a `/24` UDR, regardless of source
- If exactly one candidate remains after LPM, it is the winner. Proceed to output.
- If multiple candidates share the same maximum prefix_length, proceed to Step C.

#### Step C — Source Precedence (equal prefix length only)

Apply the following tier order. The lowest tier number wins.

| Tier | Source Field Value | Route Type |
|:-----|:-------------------|:-----------|
| 1 | `User` | User Defined Route (UDR) |
| 2 | `VirtualNetworkGateway` | BGP route from VPN or ExpressRoute |
| 3 | `Default` | Azure system route |
| 4 | `Unknown` | Flag as a parse anomaly |

If a Tier 1 (UDR) route exists among the tied candidates, it wins. Report the reason: "UDR takes precedence over all other sources at equal prefix length."

If only Tier 2 and Tier 3 routes are tied, the Tier 2 (BGP) route wins. Report: "BGP (VirtualNetworkGateway) takes precedence over system Default at equal prefix length."

If exactly one candidate remains after precedence, it is the winner. Proceed to output.

#### Step D — BGP Tie-Breaker (two or more BGP routes, same prefix)

When multiple `VirtualNetworkGateway` routes share the same prefix (identical CIDR string — which implies identical prefix_length), Azure uses AS Path length (shortest wins). **AS Path is not present in the effective route table JSON.** Do NOT fabricate a winner.

Output:
```
BGP tie detected: <N> routes with identical prefix <prefix>.
Azure uses AS Path length to select between them, but this is not available in the effective route table.
Check the VPN/ExpressRoute gateway BGP peer status:
  az network vnet-gateway list-bgp-peer-status --name <gateway-name> --resource-group <rg-name>
Present both routes in the output table and label them TIED (BGP).
```

### NVA Warning

**Single-target mode:** When the winning route has `next_hop_type == "VirtualAppliance"`, emit this warning block immediately after the output table:

```
⚠️  NVA Route Warning
The winning route sends traffic to a Virtual Appliance at <next_hop_ip>.
Verify:
  1. IP Forwarding is enabled on the NVA NIC:
       az network nic show --name <nva-nic> --resource-group <rg> --query "enableIpForwarding"
  2. The return path from the destination also routes through the same appliance.
     Asymmetric routing through NVAs causes silent packet drops.
```

**Audit mode:** Do not emit the warning block. Instead, list all Active VirtualAppliance routes under "NVA routes" in the Notable Findings section (the audit template already specifies this). The warning block is for a confirmed winning route only.

### Blackhole Detection

When the winning route has `next_hop_type == "None"`, emit this warning:

```
🔴  BLACKHOLE WARNING
The winning route has nextHopType=None. Azure silently drops all traffic to this destination.
Common causes:
  1. A VNet peering was deleted, leaving a stale None route in the effective table.
  2. The route table was explicitly configured with a None next hop to block this prefix.
Verify: az network nic show-effective-route-table and check for peering or gateway health.
```

### Invalid Route Warning

When a more specific route (longer prefix_length) exists but has `state == "Invalid"`, emit a warning after the result:

```
⚠️  A more specific route <prefix> (/<length>) is present but has state=Invalid.
Traffic that should have matched this more specific prefix is falling to the broader <winning prefix>.
Common causes: VNet peering disconnected, ExpressRoute circuit not provisioned, gateway reprovisioning.
```

---

## Single-Target Mode Output

```markdown
## 🗺️ Effective Route Summary (Target: <IP>)

| Destination | Len | Next Hop Type | Next Hop IP | Source | Status | Reason |
|:------------|:----|:--------------|:------------|:-------|:-------|:-------|
| 10.50.1.0/24 | /24 | VnetLocal | — | Default | **ACTIVE (LPM)** | Longest prefix match |
| 10.50.0.0/16 | /16 | VirtualAppliance | 10.0.0.4 | User | SHADOWED | Shorter prefix (/16 < /24) |
| 0.0.0.0/0 | /0 | Internet | — | Default | SHADOWED | Shorter prefix (/0 < /24) |

**Selection logic:** <one sentence explaining exactly why the winner was chosen>

**Actionable next step:** <specific remediation if the result is unexpected>

<NVA warning block if applicable>
<Blackhole warning block if applicable>
<Invalid route warning if applicable>
```

**Status labels:**

| Label | Meaning |
|:------|:--------|
| `ACTIVE (LPM)` | Winner via longest prefix match |
| `ACTIVE (Precedence)` | Winner via source precedence after LPM tie |
| `BLACKHOLED` | Winner is a None hop — traffic dropped |
| `TIED (BGP)` | BGP tie — AS Path needed to determine winner |
| `SHADOWED` | Active but not selected — longer prefix or higher-precedence route wins |
| `INVALID` | Not eligible for selection — state=Invalid |

**Notes:**
- Show all routes that were candidates (encompassed the destination IP), whether Active or Invalid.
- Routes that do not encompass the destination IP at all are not shown in single-target mode.
- If the winning route is the `0.0.0.0/0` catch-all, note explicitly: "No more specific route exists — traffic matched the default route."

---

## Audit Mode Output

```markdown
## 📋 Effective Route Table Audit

**Total routes:** <N>  |  **Active:** <X>  |  **Invalid:** <Y>

### Route Table

| Destination | Len | Next Hop Type | Next Hop IP | Source | State | Name |
|:------------|:----|:--------------|:------------|:-------|:------|:-----|
| 10.0.0.0/16 | /16 | VnetLocal | — | Default | Active | — |
| 10.50.0.0/24 | /24 | VirtualAppliance | 10.0.0.4 | User | Active | route-to-firewall |
| 10.200.0.0/16 | /16 | VnetPeering | — | Default | **Invalid** | — |
| 0.0.0.0/0 | /0 | Internet | — | Default | Active | — |

### ⚠️ Invalid Routes

List routes with state=Invalid here with the likely cause.

### 🔎 Notable Findings

- **NVA routes:** <list any Active routes with next_hop_type=VirtualAppliance, with the NVA IP and route name>
- **Blackhole routes:** <list any Active routes with next_hop_type=None>
- **BGP routes:** <count and prefixes of VirtualNetworkGateway routes; note if any are Invalid>
- **Default route (0.0.0.0/0):** <present/absent; type and source>
- **Shadowed by specificity:** <any notable cases where a broad UDR is overridden by a more specific system route — the LPM beats UDR scenario that surprises engineers>
```

**Notes on audit mode:**
- Sort table by prefix_length descending (most specific first), then alphabetically by prefix within each length.
- Bold `Invalid` in the State column.
- Omit Notable Findings sub-headings that have nothing to report.
- If the table is very large (>30 routes), group by source type (User, VirtualNetworkGateway, Default) with sub-headings.

---

## Known Limitations

State these when relevant:

| Limitation | When to flag |
|:-----------|:-------------|
| **BGP AS Path** | Two BGP routes with identical prefix — AS Path not in JSON; flag and direct user to gateway BGP status |
| **Virtual WAN** | Hub-and-Spoke using Azure Virtual WAN — spoke NIC routes do not reflect routing decisions inside the managed hub; flag when VirtualNetworkGateway routes are absent but expected |
| **No matching route** | If no Active route encompasses the destination — do not fabricate a result; state explicitly that traffic will be dropped |
| **NSG evaluation** | This skill covers routing only. If the winning route is correct but traffic is still blocked, the cause may be an NSG rule — use `azure-security-rule-resolver` |
| **OS firewall** | An OS-level firewall (iptables/nftables/Windows Firewall) may block traffic even if routing and NSGs are correct |
