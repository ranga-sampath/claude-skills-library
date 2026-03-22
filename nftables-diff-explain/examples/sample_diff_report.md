# nftables Ruleset Change Explanation
*AI-generated analysis — verify against raw diff and snapshots before acting on findings.*
*Scope: nftables rules only. Azure NSG, cloud firewall, and routing table not included.*

> **Sample input:** `fx-03-inet-drop-policy.json` (before) → `fx-12-icmp-ct.json` (after)
> **Command:** `/nftables-diff-explain fx-03-inet-drop-policy.json fx-12-icmp-ct.json`

---

## Change Summary

7 rules added, 3 rules removed, 2 chains removed. The change replaces a broad stateful conntrack rule and a generic ICMP permit with a more targeted set of ICMP-type-specific rules and advanced conntrack directives (ct direction, ct mark, ct zone).

## Security Impact

### Policy Changes

None — `inet/filter/input` retains a **drop** default policy throughout. The `forward` and `output` chains were removed (see Chains Removed below), but these had no rules and their removal has no effect on traffic behaviour.

### Rules Added

Seven rules added to `inet/filter/input`:

- **IPv4 ping (ICMP echo-request) → accept** *(comment: "allow IPv4 ping")*
  Replaces the broad all-ICMP accept with a specific echo-request permit. Tightening — only ping is accepted for IPv4 ICMP.

- **IPv6 ping (ICMPv6 echo-request) → accept** *(comment: "allow IPv6 ping")*
  Explicit IPv6 ping permit. Required since the baseline only permitted IPv4 ICMP.

- **ICMPv6 neighbor solicitation → accept** *(comment: "IPv6 neighbor discovery — required for link operation")*
  Permits NDP (Neighbor Discovery Protocol) packets. Required for IPv6 link-layer address resolution. Without this, IPv6 connectivity breaks on a drop-default host.

- **ICMP, type != redirect → accept** *(comment: "block ICMP redirect — tests icmp_type != negation")*
  Accepts all IPv4 ICMP packets **except** ICMP redirect (type 5). Effectively: ping, unreachable, TTL exceeded, etc. are all permitted; redirect is blocked. ICMP redirect is a known attack vector for traffic hijacking — blocking it is correct hardening.

- **ct mark 0x1 → accept** *(comment: "accept policy-marked traffic from ct mark 0x1")*
  Accepts traffic whose conntrack entry has been marked with value 1 (e.g. by a policy routing rule or `nft` `meta mark set` statement). Enables integration with a policy-based routing or QoS layer — traffic that an upstream rule has explicitly approved bypasses further input filtering.

- **TCP dport 22, ct direction original → accept** *(comment: "accept established in original direction on SSH")*
  Accepts TCP port 22 packets in the **original** conntrack direction (client-to-server). This replaces the simpler `ct state new` SSH rule — it permits both new connections and subsequent client-to-server packets in the same session, without requiring a separate `ct state established` rule for the SSH conversation.

- **ct zone 1 → drop** *(comment: "drop traffic in zone 1 — tests ct_zone")*
  Explicitly drops all traffic belonging to conntrack zone 1. Used to isolate traffic from a specific network segment or VRF from being processed by this rule table.

### Rules Removed

Three rules removed from `inet/filter/input`:

- **ct state established,related → accept** (removed)
  The broad stateful conntrack passthrough is gone. Traffic that was previously accepted because it belonged to an established session now requires a more specific rule (e.g. the new `ct direction original` SSH rule, or the `ct mark` rule). **Any established inbound session not covered by the new specific rules will be dropped** — see Notable Findings.

- **All ICMP → accept** (removed)
  Replaced by the more specific IPv4 ping, ICMPv6 ping, ND solicitation, and non-redirect ICMP rules. Tightening overall.

- **TCP dport 22, ct state new → accept** (removed)
  Replaced by the `ct direction original` SSH rule, which covers both new and established-direction packets without needing a separate `ct state established` rule for SSH return traffic.

### Chains Added / Removed

**Removed:** `inet/filter/forward` (DROP default, 0 rules) and `inet/filter/output` (ACCEPT default, 0 rules).

Both chains were empty. Removing base chains from the table deregisters their hooks — packets that would have traversed these paths now bypass this table entirely. Since forward had a DROP default and no rules, the practical effect of its removal is that **forwarded packets are now no longer dropped by this table** (they pass freely or are handled by another table). This is a **loosening** of the forward posture.

### Parse Warnings

The diff engine reported three parse warnings:
> *"Handle 5/6/7 in inet/filter/input has different expression_hash between baseline and current — possible parser bug or malformed input; recording as remove+add"*

This indicates that handles 5, 6, and 7 exist in both snapshots but with different rule content — the rules were **replaced in-place** (same handle, new expression). The diff correctly records them as remove+add. This is expected behaviour when an operator replaces rules without renumbering handles.

## Overall Assessment

The change replaces a broad, simple stateful ruleset with a more granular ICMP-type-aware and conntrack-directive-aware policy. The ICMP controls are tightened (ICMP redirect blocked, specific types permitted). The SSH rule is modernised to use `ct direction` rather than `ct state`. However, the removal of `ct state established,related accept` combined with the removal of the `forward` chain's DROP default are two significant changes that require careful verification:

1. **Established session coverage:** Any inbound established session not on SSH port 22 and not marked with ct mark 0x1 will be silently dropped. If this host serves other inbound services (HTTP, HTTPS, etc.), those established sessions now have no return path at the input hook.
2. **Forward chain removed:** Forwarded packets now pass through this table without restriction, potentially re-enabling routing/forwarding that the DROP default was previously blocking.

## Recommended Actions

- **Verify established session coverage:** If this host accepts inbound connections on ports other than 22, add a `ct state established,related accept` rule or equivalent `ct direction reply` rules for each service, or re-add the broad stateful rule as the first rule.
- **Re-evaluate forward chain removal:** If this host should not route packets between interfaces, re-add the `forward` base chain with a drop default. Its removal silently re-enables forwarding for this table.
- **Review ct zone 1 scope:** The new ct zone 1 drop rule affects all traffic in conntrack zone 1. Confirm this zone is correctly assigned to the intended network segment and will not inadvertently drop legitimate traffic.
- **Confirm ct mark 0x1 provisioning:** The ct mark accept rule only works if something upstream sets `ct mark 1` on approved flows. Verify the marking mechanism is in place before relying on this rule as a passthrough.
