# iptables Ruleset Change Explanation
*AI-generated analysis — verify against raw diff and snapshots before acting on findings.*
*Scope: iptables rules only. Azure NSG, cloud firewall, and routing table not included.*

> **Sample input:** `ubuntu2404-clean.txt` (before) → `ubuntu2404-cis-hardened.txt` (after)
> **Command:** `/iptables-diff-explain ubuntu2404-clean.txt ubuntu2404-cis-hardened.txt`

---

## Change Summary

3 chains added (new `filter` table with DROP default policies), 3 chains removed (entire `security` table including Azure Wire Server output controls). This is a CIS hardening operation that introduced default-deny inbound, but simultaneously removed an Azure-specific outbound restriction layer.

## Security Impact

### Policy Changes

No policy changes in the narrow sense — the `filter` table itself is **new** (the baseline had no `filter` table), so the diff engine reports it as chains added rather than policy changes. The net effect is equivalent to:

**INPUT: ACCEPT → DROP (effective)** — Every inbound packet not matched by the 4 new INPUT rules is now silently dropped. Before hardening, all inbound traffic was accepted (no filter table present).

**FORWARD: ACCEPT → DROP (effective)** — The host no longer forwards packets between interfaces. Any Docker, VPN, or routing function would break.

### Rules Added

New `filter` table with 4 INPUT rules:
- **Loopback ACCEPT** — all traffic on `lo` permitted. Required for local inter-process communication.
- **RELATED,ESTABLISHED ACCEPT** — return traffic for outbound sessions. Allows replies to reach the host.
- **ICMP type 8 ACCEPT** — ping requests permitted. All other ICMP types are dropped by the INPUT DROP default.
- **TCP port 22, state NEW ACCEPT** — new inbound SSH connections permitted from any source IP.

### Rules Removed

The entire **`security` table** was removed. It contained 3 OUTPUT rules governing access to the **Azure Wire Server (`168.63.129.16`)**:

| Position | Rule | Effect |
|---|---|---|
| 1 | TCP/53 to 168.63.129.16 → **ACCEPT** | Allowed TCP DNS queries to the Wire Server |
| 2 | TCP to 168.63.129.16, uid-owner 0 → **ACCEPT** | Allowed root-owned processes (Azure agent) to reach the Wire Server |
| 3 | TCP to 168.63.129.16, state INVALID/NEW → **DROP** | Blocked non-established connections to the Wire Server from non-root, non-DNS processes |

Before hardening: only root-owned processes and TCP DNS queries could initiate connections to the Azure Wire Server. After hardening: **any process running as any user can now reach 168.63.129.16** — the restriction is gone and OUTPUT is fully open (ACCEPT, no rules).

### Chains Added / Removed

**Added:** `filter/INPUT` (4 rules, DROP default), `filter/FORWARD` (0 rules, DROP default), `filter/OUTPUT` (0 rules, ACCEPT default).

**Removed:** `security/INPUT` (empty), `security/FORWARD` (empty), `security/OUTPUT` (3 Wire Server rules above).

## Overall Assessment

The CIS hardening correctly tightens the **inbound** posture from fully open to default-deny, permitting only loopback, established sessions, ICMP ping, and SSH — the right baseline for a standalone server. However, the hardening **removed the `security` table's outbound Wire Server controls** without replacing them. On an Azure VM, `168.63.129.16` handles instance metadata, health probes, and agent communication; unrestricted access from non-root processes is a potential privilege escalation and SSRF surface.

## Recommended Actions

- **Verify SSH is reachable** before closing other sessions — TCP 22 is the only permitted inbound service.
- **Restore Wire Server output controls:** Re-add the three `168.63.129.16` rules (either in the `security` table or as equivalent `filter/OUTPUT` rules) to restrict Wire Server access to root-owned processes and DNS only.
- **Restrict SSH source IP:** TCP/22 is open to `0.0.0.0/0`. Restrict to known admin CIDR ranges or layer fail2ban on top.
- **Consider OUTPUT egress filtering:** `filter/OUTPUT` is fully open (ACCEPT, no rules). Adding egress controls limits blast radius if the host is compromised.
