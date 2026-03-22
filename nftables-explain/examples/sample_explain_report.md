# nftables Ruleset Explanation
*AI-generated analysis — verify against raw snapshot before acting on findings.*
*Scope: nftables rules only. Azure NSG, cloud firewall, and routing table not included.*

> **Sample input:** `fx-03-inet-drop-policy.json`
> **Command:** `/nftables-explain fx-03-inet-drop-policy.json`

---

## Address Families Covered

**`inet`** — covers both IPv4 and IPv6 in a single table (`inet/filter`). No separate `ip` or `ip6` tables present. This is the recommended approach for dual-stack hosts as a single ruleset governs both families.

## Default Policies

| Chain | Hook | Priority | Policy |
|---|---|---|---|
| **input** | input | filter (0) | **drop** |
| **forward** | forward | filter (0) | **drop** |
| output | output | filter (0) | accept |

Both `input` and `forward` default to **drop** — this is a **default-deny** posture. Every inbound packet and every forwarded packet not matched by an explicit accept rule is silently discarded. Output from the host is fully permitted.

## Rules

### filter (inet)

#### input chain (hook: input, priority: 0, policy: drop)

- **Rule 1 — Established/Related:** `ct state established,related` → **accept**. Allows return traffic for connections this host initiated outbound (DNS replies, HTTP responses to curl/apt, etc.). Without this, the output accept policy would be one-way — packets would leave but replies would be dropped.

- **Rule 2 — ICMP:** All ICMP packets → **accept**. Permits all ICMP types inbound (ping, unreachable, TTL exceeded, etc.). No type filtering — all ICMP is admitted.

- **Rule 3 — SSH:** TCP, destination port 22, `ct state new` → **accept**. Permits new inbound SSH connections from any source IP. Subsequent packets on the same session are handled by Rule 1 (established).

#### forward chain (hook: forward, priority: 0, policy: drop)

No rules. Combined with the drop default, this completely disables packet forwarding between interfaces. This host does not act as a router or gateway.

#### output chain (hook: output, priority: 0, policy: accept)

No rules. All outbound traffic from the host is permitted without restriction.

## Security Posture Summary

This is a **default-deny inbound, default-deny forward** configuration using a single `inet` table covering both IPv4 and IPv6. The host accepts only return traffic for established sessions, all ICMP, and new SSH connections — everything else inbound is silently dropped. There is no NAT, no custom chains, and no named sets. The ruleset is clean and minimal, consistent with a CIS-style hardened baseline for a dual-stack host.

## Notable Findings

- **All ICMP accepted without type filtering:** Rule 2 accepts all ICMP regardless of type. This includes ICMP redirect (type 5) and timestamp request (type 13), which are sometimes restricted on hardened hosts. Consider narrowing to `icmp type echo-request` if the environment warrants tighter ICMP controls.
- **SSH open to all sources:** TCP/22 is permitted from any IP address. On a public-facing host, consider restricting SSH to known admin CIDR ranges or adding a rate-limit rule before the accept.
- **No OUTPUT restrictions:** Outbound traffic is unrestricted. Egress filtering is not required for most deployments but provides defence-in-depth against a compromised host reaching arbitrary external destinations.
- **IPv6 ICMP (ICMPv6) also accepted:** The `inet` family ICMP rule covers both ICMP (IPv4) and ICMPv6. This is typically correct — ICMPv6 is required for IPv6 link operation (neighbor discovery, router advertisements) and should not be blocked.
