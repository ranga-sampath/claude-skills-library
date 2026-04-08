# Sample Skill Output — azure-effective-route-summarizer

Real output captured from three fixture runs. No values fabricated.

---

## Example 1 — Single-Target: UDR Precedence Over System Route

**Fixture:** `fixtures/fx-02-udr-same-prefix.json`
**Command:** `/azure-effective-route-summarizer fixtures/fx-02-udr-same-prefix.json --dst 172.16.10.20`
**Scenario:** A UDR and a system VnetLocal route share the identical /24 prefix. LPM ties; source precedence resolves it.

---

## 🗺️ Effective Route Summary (Target: 172.16.10.20)

| Destination | Len | Next Hop Type | Next Hop IP | Source | Status | Reason |
|:------------|:----|:--------------|:------------|:-------|:-------|:-------|
| 172.16.10.0/24 | /24 | VirtualAppliance | 10.0.0.4 | User | **ACTIVE (Precedence)** | UDR takes precedence over system Default at equal prefix length |
| 172.16.10.0/24 | /24 | VnetLocal | — | Default | SHADOWED | Same prefix length (/24); lower source precedence (Default < User) |
| 172.16.0.0/16 | /16 | VnetLocal | — | Default | SHADOWED | Shorter prefix (/16 < /24) |
| 0.0.0.0/0 | /0 | Internet | — | Default | SHADOWED | Shorter prefix (/0 < /24) |

**Selection logic:** Both `172.16.10.0/24` routes tied on LPM; the UDR (`route-to-nva`, source=User, Tier 1) wins over the system VnetLocal route (source=Default, Tier 3) via source precedence.

**Actionable next step:** Traffic to 172.16.10.20 is being sent to the NVA at 10.0.0.4. If this is unexpected, check whether this UDR was intentionally added to this subnet's route table — a system VnetLocal route for this same /24 exists and would have been the default path without it.

⚠️ **NVA Route Warning**
The winning route sends traffic to a Virtual Appliance at **10.0.0.4**.
Verify:
1. IP Forwarding is enabled on the NVA NIC:
   ```
   az network nic show --name <nva-nic> --resource-group <rg> --query "enableIpForwarding"
   ```
2. The return path from 172.16.10.20 also routes through the same appliance. Asymmetric routing through NVAs causes silent packet drops.

---

## Example 2 — Single-Target: LPM Across Overlapping UDRs

**Fixture:** `fixtures/fx-15-overlapping-udrs.json`
**Command:** `/azure-effective-route-summarizer fixtures/fx-15-overlapping-udrs.json --dst 10.0.1.130`
**Scenario:** Three UDRs at /16, /24, and /28 all cover the destination. The /28 wins unconditionally via LPM — bypassing both NVAs that the broader UDRs point to.

---

## 🗺️ Effective Route Summary (Target: 10.0.1.130)

| Destination | Len | Next Hop Type | Next Hop IP | Source | Status | Reason |
|:------------|:----|:--------------|:------------|:-------|:-------|:-------|
| 10.0.1.128/28 | /28 | VnetLocal | — | User | **ACTIVE (LPM)** | Longest prefix match — most specific route wins unconditionally |
| 10.0.1.0/24 | /24 | VirtualAppliance | 10.100.0.5 | User | SHADOWED | Shorter prefix (/24 < /28) |
| 10.0.0.0/16 | /16 | VirtualAppliance | 10.100.0.4 | User | SHADOWED | Shorter prefix (/16 < /28) |
| 10.0.0.0/8 | /8 | VnetLocal | — | Default | SHADOWED | Shorter prefix (/8 < /28) |
| 0.0.0.0/0 | /0 | Internet | — | Default | SHADOWED | Shorter prefix (/0 < /28) |

**Selection logic:** `10.0.1.128/28` wins by LPM with prefix_length=28 — the highest specificity in the table. LPM is absolute; the two competing UDRs at /24 and /16 are both eliminated before source precedence is even considered.

**Actionable next step:** This is operating as designed — `route-sensitive-hosts-local` deliberately exempts the 10.0.1.128/28 block from NVA inspection by routing it directly via VnetLocal, while the broader /24 (`route-subnet-via-nva-b`) and /16 (`route-broad-via-nva-a`) send other traffic through two different NVAs. If this exemption is unintentional, remove or narrow the /28 UDR.

> ⚠️ **Notable engineering observation:** This table has three UDRs with three different next hops — `10.100.0.4` (/16), `10.100.0.5` (/24), and VnetLocal (/28). Traffic to 10.0.1.128/28 bypasses both NVAs entirely. Any security inspection policy applied at those NVAs does not apply to hosts in this /28. Confirm this is intentional.

---

## Example 3 — Audit Mode: Hub-Spoke Production Topology

**Fixture:** `fixtures/fx-12-hub-spoke-production.json`
**Command:** `/azure-effective-route-summarizer fixtures/fx-12-hub-spoke-production.json`
**Scenario:** Hub-spoke topology with a forced-tunnel UDR to an NVA, two BGP routes from ExpressRoute/VPN, and three VNet peering routes. No `--dst` — full table audit.

---

## 📋 Effective Route Table Audit

**Total routes:** 6  |  **Active:** 6  |  **Invalid:** 0

### Route Table

| Destination | Len | Next Hop Type | Next Hop IP | Source | State | Name |
|:------------|:----|:--------------|:------------|:-------|:------|:-----|
| 192.168.10.0/24 | /24 | VirtualNetworkGateway | 10.1.255.4 | VirtualNetworkGateway | Active | — |
| 10.1.0.0/16 | /16 | VnetLocal | — | Default | Active | — |
| 10.2.0.0/16 | /16 | VnetPeering | — | Default | Active | — |
| 10.3.0.0/16 | /16 | VnetPeering | — | Default | Active | — |
| 192.168.0.0/16 | /16 | VirtualNetworkGateway | 10.1.255.4 | VirtualNetworkGateway | Active | — |
| 0.0.0.0/0 | /0 | VirtualAppliance | 10.1.0.4 | User | Active | route-all-to-hub-nva |

### 🔎 Notable Findings

- **NVA routes:** `0.0.0.0/0` → NVA at **10.1.0.4** (`route-all-to-hub-nva`). All traffic not matched by a more specific route is sent to the hub firewall. This is the standard hub-spoke forced-tunnelling pattern.

- **BGP routes (2):** Both learned via gateway at `10.1.255.4` — on-premises ranges advertised via ExpressRoute or VPN:
  - `192.168.0.0/16` — aggregate on-premises prefix
  - `192.168.10.0/24` — more specific subnet advertisement

- **Default route (0.0.0.0/0):** Present — UDR (`route-all-to-hub-nva`), via VirtualAppliance. All unmatched traffic (internet, unknown destinations) is forced through the hub NVA.

- **Shadowed by specificity — critical interaction:** The UDR `0.0.0.0/0` would normally catch all traffic including on-premises (192.168.x.x). It does **not** — the BGP route `192.168.0.0/16` (prefix_length=16) beats the UDR `0.0.0.0/0` (prefix_length=0) via LPM. On-premises traffic bypasses the NVA entirely and goes directly to the gateway at `10.1.255.4`. This is expected behaviour in hub-spoke with ExpressRoute, but if the intent is for on-premises traffic to also traverse the NVA for inspection, a UDR for `192.168.0.0/16` pointing to the NVA is required to override the BGP route via source precedence.

- **BGP specificity within on-prem range:** Traffic to `192.168.10.x` matches the more specific BGP `/24` rather than the `/16` aggregate — both go to the same gateway (`10.1.255.4`), so there is no operational difference here unless the gateway routes them differently internally.

**Known limitation:** If this hub is an Azure Virtual WAN managed hub rather than a self-managed hub VNet, the routing decisions within the hub are not reflected in these spoke NIC effective routes. The routes shown only govern how traffic leaves this spoke NIC — what happens inside the vWAN hub is opaque to this output.
