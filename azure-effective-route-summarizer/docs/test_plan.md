# Test Plan: azure-effective-route-summarizer Skill

## Fixture Index

All fixtures are in `fixtures/`. Each is a JSON file in the `az network nic show-effective-route-table` format.

| Fixture | Category | Description | Primary Behaviour Under Test |
|:--------|:---------|:------------|:-----------------------------|
| `fx-01-basic-vnet-local.json` | Basic | Simple VNet with system routes only | Happy path — target IP in a /24 VNetLocal route |
| `fx-02-udr-same-prefix.json` | Basic | UDR and system route at identical /24 prefix | Precedence: UDR (User) beats system (Default) at equal length |
| `fx-03-lpm-beats-udr.json` | Basic | /32 system route vs /24 UDR for same destination | LPM is absolute — /32 wins regardless of source |
| `fx-04-nva-udr.json` | Basic | UDR sending traffic to a Virtual Appliance | NVA warning: IP Forwarding and return path |
| `fx-05-minimal-routes.json` | Edge case | Minimal route table: VNetLocal for VNet address space (10.0.1.0/24) plus 0.0.0.0/0 Internet default — no UDRs or BGP | Catch-all wins for public IP; VNetLocal wins for VNet-local IP via LPM |
| `fx-06-bgp-vs-system.json` | Edge case | BGP /16 vs system /16 for same prefix length | Precedence: BGP (VirtualNetworkGateway) beats system Default |
| `fx-07-invalid-route.json` | Edge case | Route with state=Invalid mixed with Active routes | Invalid routes excluded from selection; flagged in output |
| `fx-08-host-route-slash32.json` | Boundary | /32 host route UDR for a single VM | Maximum prefix length; LPM winner regardless of competition |
| `fx-09-no-matching-route.json` | Boundary | Target IP not covered by any route | No match — explicit message; do not fabricate a result |
| `fx-10-blackhole-none-hop.json` | Boundary | Active route with nextHopType=None | Traffic blackholed; None hop flagged with explicit warning |
| `fx-11-multi-prefix-entry.json` | Boundary | Single entry with multiple addressPrefix values | Preprocessor expansion: each prefix becomes its own row |
| `fx-12-hub-spoke-production.json` | Production | Hub-spoke: UDR to NVA + BGP from ER + VNet peering | Combined LPM/precedence; NVA and ER routes coexist |
| `fx-13-vnet-peering-routes.json` | Production | Multiple VNet peerings, one disconnected | Active peering wins; Invalid peering excluded and flagged |
| `fx-14-bgp-tie-same-prefix.json` | Bug-prone | Two BGP routes with identical /24 prefix | AS Path tie-break cannot be determined from JSON — must flag |
| `fx-15-overlapping-udrs.json` | Bug-prone | UDRs at /16, /24, /28 all covering same target | LPM selects /28; /24 and /16 eliminated — must not select wrong one |

---

## Test Scenarios

### T1 — Basic VNetLocal, single-target mode (fx-01)

```
/azure-effective-route-summarizer fixtures/fx-01-basic-vnet-local.json --dst 10.0.1.50
```

**Expected:**
- Preprocessor: 5 routes, 0 invalid
- Candidates encompassing 10.0.1.50: `10.0.1.0/24` (/24 VNetLocal) and `0.0.0.0/0` (/0 Internet)
- LPM winner: `10.0.1.0/24` (prefix_length=24 > 0)
- Output table shows `10.0.1.0/24 VnetLocal Active ACTIVE (LPM)` and `0.0.0.0/0 Internet Active SHADOWED`
- No NVA warning (VnetLocal hop)
- No BGP tie-break flag

Audit mode cross-check:
```
/azure-effective-route-summarizer fixtures/fx-01-basic-vnet-local.json
```
**Expected:** Full table with 5 routes, no invalid routes, no notable findings.

---

### T2 — UDR precedence over system route at same prefix (fx-02)

```
/azure-effective-route-summarizer fixtures/fx-02-udr-same-prefix.json --dst 172.16.10.20
```

**Expected:**
- Two routes encompass 172.16.10.20: both are `/24` (equal prefix length)
  - `172.16.10.0/24` source=User (UDR), nextHopType=VirtualAppliance, state=Active
  - `172.16.10.0/24` source=Default (VNetLocal), state=Active
- LPM tie → apply precedence: User (Tier 1) beats Default (Tier 3)
- Winner: UDR `172.16.10.0/24` via VirtualAppliance
- Eliminated: system route with explicit reason "same prefix length; UDR takes precedence over system route"
- NVA warning emitted (VirtualAppliance hop)

---

### T3 — LPM beats UDR: /32 system route over /24 UDR (fx-03)

```
/azure-effective-route-summarizer fixtures/fx-03-lpm-beats-udr.json --dst 10.20.30.40
```

**Expected:**
- Three candidates for 10.20.30.40:
  - `10.20.30.40/32` source=Default, nextHopType=VnetLocal (system adds /32 host routes for special addresses)
  - `10.20.30.0/24` source=User, nextHopType=VirtualAppliance (UDR)
  - `10.20.0.0/16` source=User, nextHopType=VirtualAppliance (UDR)
- LPM winner: `/32` (prefix_length=32) — wins unconditionally
- Output must NOT select the UDR despite it being a User source
- Explicit note: "LPM is absolute — a /32 system route overrides any broader UDR"
- NVA warning NOT emitted (winner is VnetLocal, not VirtualAppliance)

---

### T4 — NVA route warning (fx-04)

```
/azure-effective-route-summarizer fixtures/fx-04-nva-udr.json --dst 192.168.5.10
```

**Expected:**
- Winner: `192.168.0.0/16` source=User, nextHopType=VirtualAppliance, next_hop_ip=10.0.0.4
- NVA warning emitted:
  - Verify IP Forwarding is enabled on the NVA NIC at 10.0.0.4
  - Confirm return path from 192.168.5.10 also routes through the same appliance
- No other candidates at longer prefix
- No BGP or invalid route flags

---

### T5 — Minimal route table (fx-05)

The fixture `fx-05-minimal-routes.json` contains two routes: `10.0.1.0/24 VnetLocal Default Active` and `0.0.0.0/0 Internet Default Active`. No UDRs, no BGP.

```
/azure-effective-route-summarizer fixtures/fx-05-minimal-routes.json --dst 8.8.8.8
```

**Expected:**
- Only `0.0.0.0/0` encompasses 8.8.8.8 (nextHopType=Internet, source=Default)
- Winner: `0.0.0.0/0` (only candidate — trivial LPM)
- Output notes this is the catch-all default route; no more-specific route exists
- is_zero_route=true flagged in output

```
/azure-effective-route-summarizer fixtures/fx-05-minimal-routes.json --dst 10.0.1.50
```

**Expected:**
- `10.0.1.0/24` VnetLocal and `0.0.0.0/0` Internet both encompass 10.0.1.50
- LPM winner: `10.0.1.0/24` (prefix_length=24 > 0)
- 0.0.0.0/0 shown as eliminated candidate with reason "shorter prefix (0 < 24)"

---

### T6 — BGP beats system route at same prefix length (fx-06)

```
/azure-effective-route-summarizer fixtures/fx-06-bgp-vs-system.json --dst 10.100.5.30
```

**Expected:**
- Two /16 candidates for 10.100.5.30:
  - `10.100.0.0/16` source=VirtualNetworkGateway (BGP), nextHopType=VirtualNetworkGateway
  - `10.100.0.0/16` source=Default, nextHopType=None (blackhole placeholder being overridden by BGP)
- LPM tie (both /16) → precedence: VirtualNetworkGateway (Tier 2) beats Default (Tier 3)
- Winner: BGP route
- Eliminated: system route with reason "BGP (VirtualNetworkGateway) takes precedence over system Default at equal prefix length"

---

### T7 — Invalid route excluded from selection (fx-07)

```
/azure-effective-route-summarizer fixtures/fx-07-invalid-route.json --dst 10.200.1.50
```

**Expected:**
- Two routes encompass 10.200.1.50:
  - `10.200.1.0/24` source=Default, state=Invalid (peering disconnected)
  - `0.0.0.0/0` source=Default, state=Active, nextHopType=Internet
- Invalid route must NOT appear in the candidate selection — excluded before LPM
- Winner: `0.0.0.0/0` (only Active candidate)
- Warning: "A more specific route `10.200.1.0/24` exists but has state=Invalid (VNet peering likely disconnected). Traffic falls to the catch-all default route."
- Audit mode: Invalid routes listed in a separate "Invalid Routes" section

---

### T8 — /32 host route as LPM winner (fx-08)

```
/azure-effective-route-summarizer fixtures/fx-08-host-route-slash32.json --dst 10.5.10.100
```

**Expected:**
- Candidates: `/32` (UDR for that exact host), `/24` (UDR, VirtualAppliance), `/0` (Internet)
- LPM winner: `/32` (prefix_length=32, maximum specificity)
- The /32 is source=User — consistent with the fact that the UDR was intended for this specific host
- The /24 UDR is eliminated despite being the same source tier
- NVA warning emitted if /32 UDR also has VirtualAppliance hop; not emitted if VnetLocal

Boundary check: confirm prefix_length=32 parsed correctly from "10.5.10.100/32".

---

### T9 — No matching route (fx-09)

```
/azure-effective-route-summarizer fixtures/fx-09-no-matching-route.json --dst 203.0.113.1
```

**Expected:**
- No route in the table encompasses 203.0.113.1 — the table contains only RFC 1918 prefixes and no 0.0.0.0/0
- Output: "No route found for destination 203.0.113.1. The effective route table contains no prefix that encompasses this address. Traffic to this destination will be dropped."
- Do NOT fabricate a result or assume a default route exists
- Skill must not hallucinate a VNetLocal or Internet route that isn't there

---

### T10 — Blackhole: nextHopType=None (fx-10)

```
/azure-effective-route-summarizer fixtures/fx-10-blackhole-none-hop.json --dst 10.30.0.50
```

**Expected:**
- Winner: `10.30.0.0/16` source=Default, nextHopType=None, state=Active
- Winner is the LPM candidate but it is a blackhole
- Mandatory warning: "WARNING: The winning route has nextHopType=None. Azure will silently drop all traffic to this destination. Common causes: (1) a VNet peering was deleted leaving behind a stale None route, (2) the route table was explicitly configured with a None hop to block traffic."
- Verdict label: **BLACKHOLED** (not ACTIVE)

---

### T11 — Multi-prefix expansion (fx-11)

```
/azure-effective-route-summarizer fixtures/fx-11-multi-prefix-entry.json --dst 172.20.5.10
```

**Expected:**
- The raw fixture has one entry with `addressPrefix: ["172.20.0.0/16", "172.20.5.0/24"]`
- Preprocessor expands to two separate rows
- 172.20.5.0/24 (prefix_length=24) encompasses 172.20.5.10 — LPM winner over /16
- parse_warnings: none (multi-prefix expansion is handled silently)
- Both expanded routes appear in audit mode table

---

### T12 — Hub-spoke production (fx-12)

Audit mode:
```
/azure-effective-route-summarizer fixtures/fx-12-hub-spoke-production.json
```

**Expected:**
- UDR `0.0.0.0/0` via NVA (10.1.0.4) at /0 — sends all non-VNet traffic through hub firewall
- BGP routes from ExpressRoute covering 192.168.0.0/16 (on-premises)
- VNetLocal routes for hub (10.1.0.0/16) and spoke (10.2.0.0/16) address spaces
- NVA warning for 0.0.0.0/0 UDR
- No invalid routes

Single-target cross-check: destination in on-prem range
```
/azure-effective-route-summarizer fixtures/fx-12-hub-spoke-production.json --dst 192.168.10.50
```
**Expected:**
- BGP /16 and /0 UDR both cover 192.168.10.50
- BGP /16 (prefix_length=16) beats UDR /0 (prefix_length=0) via LPM — even though UDR has higher precedence
- Winner: BGP 192.168.0.0/16 → VirtualNetworkGateway

Single-target cross-check: destination on the internet
```
/azure-effective-route-summarizer fixtures/fx-12-hub-spoke-production.json --dst 8.8.8.8
```
**Expected:**
- Only /0 UDR covers 8.8.8.8 (internet address)
- Winner: UDR `0.0.0.0/0` via VirtualAppliance (NVA)
- NVA warning emitted

---

### T13 — VNet peering with one disconnected (fx-13)

```
/azure-effective-route-summarizer fixtures/fx-13-vnet-peering-routes.json --dst 10.3.5.20
```

**Expected:**
- Two candidates for 10.3.5.20:
  - `10.3.0.0/16` source=Default, nextHopType=VnetPeering, state=Active (peering-b, healthy)
  - `10.3.5.0/24` source=Default, nextHopType=VnetPeering, state=Invalid (peering-c, disconnected)
- Invalid route excluded from selection
- Winner: `10.3.0.0/16` (only Active candidate)
- Warning: "A more specific route `10.3.5.0/24` via VnetPeering is present but state=Invalid — the peering is likely disconnected."

---

### T14 — BGP tie — two paths, same prefix (fx-14)

```
/azure-effective-route-summarizer fixtures/fx-14-bgp-tie-same-prefix.json --dst 10.50.0.100
```

**Expected:**
- Two routes: both `10.50.0.0/24`, both source=VirtualNetworkGateway, both state=Active
- LPM: both are /24 — tie
- Precedence: both are VirtualNetworkGateway (Tier 2) — tie
- BGP tie-break: AS Path length needed — NOT in the JSON
- Output: "Two BGP routes with identical prefix `10.50.0.0/24` exist. Azure will use AS Path length to select between them, but this information is not available in the effective route table. Check the VPN/ExpressRoute gateway BGP peer status."
- Do NOT fabricate a winner; present both routes as candidates

---

### T15 — Overlapping UDRs at /16, /24, /28 (fx-15)

```
/azure-effective-route-summarizer fixtures/fx-15-overlapping-udrs.json --dst 10.0.1.130
```

**Expected:**
- Three UDRs cover 10.0.1.130:
  - `10.0.0.0/16` source=User, nextHopType=VirtualAppliance, next_hop_ip=10.100.0.4
  - `10.0.1.0/24` source=User, nextHopType=VirtualAppliance, next_hop_ip=10.100.0.5
  - `10.0.1.128/28` source=User, nextHopType=VnetLocal (specific subnet override)
- LPM winner: `10.0.1.128/28` (prefix_length=28 > 24 > 16)
- The /28 sends traffic to VnetLocal despite /16 and /24 pointing to different NVAs
- Eliminated: /24 with "shorter prefix (24 < 28)"; /16 with "shorter prefix (16 < 28)"
- This is the classic "specific subnet override" pattern — must be flagged as intentional design

Also test a destination that falls in /24 but outside /28:
```
/azure-effective-route-summarizer fixtures/fx-15-overlapping-udrs.json --dst 10.0.1.50
```
**Expected:**
- 10.0.1.50 is in `10.0.1.0/24` and `10.0.0.0/16` but NOT in `10.0.1.128/28`
- Candidates: /24 and /16 (both User, both VirtualAppliance)
- LPM winner: /24 (prefix_length=24 > 16)
- Winner points to 10.100.0.5; /16 points to 10.100.0.4 — different NVAs, flagged

---

## Accuracy Checklist

Before considering the skill validated, verify each of the following:

- [ ] T1: VNetLocal /24 beats Internet /0 via LPM; audit shows all 5 routes cleanly
- [ ] T2: UDR wins at equal /24 via source precedence; system route reason stated explicitly
- [ ] T3: /32 system route wins over /24 UDR; output explicitly warns LPM beats precedence
- [ ] T4: NVA warning emitted with NVA IP and IP Forwarding reminder
- [ ] T5: catch-all /0 wins for public IP (8.8.8.8) with is_zero_route flagged; VNetLocal /24 wins for VNet-local IP (10.0.1.50) via LPM over /0
- [ ] T6: BGP (VirtualNetworkGateway) beats Default at equal /16; reason stated
- [ ] T7: Invalid route excluded from selection; warning names the affected prefix and likely cause
- [ ] T8: /32 parsed correctly; /32 wins as LPM; NVA warning conditional on /32 hop type
- [ ] T9: No match produces explicit "no route found" message — no hallucinated route
- [ ] T10: None hop winner labelled BLACKHOLED; mandatory warning with causes listed
- [ ] T11: Multi-prefix expanded to two rows; /24 wins over /16 for target in /24 range
- [ ] T12: BGP /16 beats UDR /0 via LPM for on-prem target; UDR /0 wins for internet target
- [ ] T13: Invalid peering excluded; warning names the disconnected peering prefix
- [ ] T14: BGP tie declared explicitly; no fabricated winner; user directed to gateway BGP status
- [ ] T15: /28 wins for target in /28 range; /24 wins for target outside /28 but inside /24

---

## Real Fixture Capture (Optional)

```bash
# List NICs in a resource group
az network nic list \
  --resource-group <rg-name> \
  --query "[].{name:name, vm:virtualMachine.id}" \
  -o table

# Capture effective routes for a specific NIC
az network nic show-effective-route-table \
  --name <nic-name> \
  --resource-group <rg-name> \
  -o json > fixtures/fx-real-<vm-name>.json
```

Store real fixtures with the `fx-real-` prefix to distinguish them from synthetic ones.
