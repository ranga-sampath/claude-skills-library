# iptables Ruleset Explanation
*AI-generated analysis — verify against raw snapshot before acting on findings.*
*Scope: iptables rules only. Azure NSG, cloud firewall, and routing table not included.*

> **Sample input:** `ubuntu2404-docker-fail2ban.txt`
> **Command:** `/iptables-explain ubuntu2404-docker-fail2ban.txt`

---

## Framework

**iptables-nft** — iptables CLI using the nftables kernel backend (detected from header: `iptables-save v1.8.10 (nf_tables)`). Common on Ubuntu 20.04+. Rule syntax is identical to iptables-legacy; the distinction matters if native nft rules also exist on the system, as both share the same kernel data path.

## Default Policies

| Chain | Table | Policy |
|---|---|---|
| INPUT | filter | ACCEPT |
| **FORWARD** | **filter** | **DROP** |
| OUTPUT | filter | ACCEPT |
| PREROUTING | raw | ACCEPT |
| PREROUTING / INPUT / OUTPUT / POSTROUTING | nat | ACCEPT |

The **FORWARD chain has a DROP default policy** — all inter-host packet forwarding is blocked unless Docker's chains explicitly permit it.

The **INPUT chain has an ACCEPT default policy** — this host is **not default-deny inbound**. All inbound traffic is accepted unless fail2ban bans it.

## Rules

### filter table

#### INPUT chain

- **Rule 1:** All TCP traffic to port 22 (matched via `-m multiport --dports 22`) → `f2b-sshd` chain for fail2ban evaluation. Any SSH session not matching a ban falls through to the ACCEPT default.

#### FORWARD chain

- **Rule 1:** All forwarded traffic → `DOCKER-USER` (empty — operator hook for custom overrides, currently unused).
- **Rule 2:** All forwarded traffic → `DOCKER-FORWARD` (Docker's main forwarding decision chain).

The FORWARD DROP default ensures only traffic explicitly processed by Docker's chains can be forwarded.

#### DOCKER chain (user-defined)

Container-level access control:
- **Rule 1:** TCP from any external interface (not `docker0`) destined to `172.17.0.2:80` → **ACCEPT** (permits forwarded web traffic after DNAT).
- **Rule 2:** Any traffic from external interfaces destined to `docker0` (not matched above) → **DROP** (blocks direct access to other container ports).

#### DOCKER-BRIDGE (user-defined)

Routes all traffic destined to `docker0` into the `DOCKER` chain for per-container evaluation.

#### DOCKER-CT (user-defined)

`RELATED,ESTABLISHED` traffic destined to `docker0` → **ACCEPT**. Permits response packets on existing container sessions without re-evaluating each packet.

#### DOCKER-FORWARD (user-defined)

Docker's main forwarding pipeline (Docker 27+ topology):
1. → `DOCKER-CT` — pass return/established traffic
2. → `DOCKER-INTERNAL` — placeholder for internal-only container traffic (empty)
3. → `DOCKER-BRIDGE` — per-container access rules via `DOCKER` chain
4. Traffic originating from `docker0` (container-initiated outbound) → **ACCEPT**

#### DOCKER-INTERNAL, DOCKER-USER (user-defined)

Both empty. `DOCKER-USER` is Docker's hook for operator-added custom forwarding rules.

#### f2b-sshd (user-defined — fail2ban)

Evaluated for all TCP port 22 traffic:
- **Rule 1:** Source `1.2.3.4/32` → **REJECT** (icmp-port-unreachable). **1 active ban.**
- **Rule 2:** All other sources → **RETURN** (passes through to INPUT ACCEPT default, allowing SSH).

### raw table

#### PREROUTING chain

- **Rule 1:** Packets destined to `172.17.0.2/32` arriving on any interface **other than `docker0`** → **DROP**. Prevents external hosts from directly addressing the container's private IP, bypassing DNAT. Packets via DNAT (host:8080 → 172.17.0.2:80) are unaffected because DNAT rewrites the destination in the nat table which runs after raw.

### nat table

#### PREROUTING chain
- Packets destined to any LOCAL address → `DOCKER` nat chain (enables DNAT port mapping evaluation for inbound traffic).

#### OUTPUT chain
- Locally generated packets destined to a LOCAL address (excluding 127.x) → `DOCKER` nat chain (enables DNAT for container traffic initiated on the host itself).

#### POSTROUTING chain
- Traffic from `172.17.0.0/16` (Docker bridge subnet) egressing on any interface except `docker0` → **MASQUERADE** (source NAT for container outbound internet access).

#### DOCKER chain (nat, user-defined)
- TCP from any external interface (not `docker0`), port **8080** → **DNAT to `172.17.0.2:80`**. External port 8080 is forwarded into the container's web server on port 80.

## Security Posture Summary

The host is **not default-deny inbound** — the filter INPUT chain has an ACCEPT policy. The only inbound protection is fail2ban on SSH (port 22), with one active ban (`1.2.3.4`). Any port not protected by an explicit rule is openly reachable. Container isolation is correctly configured: Docker's forwarding chains allow only port 8080→container:80 from external sources, and the raw table blocks direct addressing of the container IP.

## Notable Findings

- **INPUT ACCEPT default:** No explicit inbound drop rule for the host itself. Any service listening on any port (e.g. database, metrics endpoint) is reachable on all interfaces unless the application binds to loopback. Consider adding a default-deny INPUT policy with explicit ACCEPT rules for known ports.
- **Port 8080 publicly exposed:** External TCP port 8080 is DNATted to `172.17.0.2:80` with no source IP restriction. Any host on the internet can reach the container's web service.
- **1 active fail2ban ban:** `1.2.3.4/32` is currently banned from SSH. Verify this is an expected ban.
- **DOCKER-USER is empty:** No operator-added forwarding restrictions. To restrict which external IPs can reach port 8080, add rules to DOCKER-USER.
- **Docker 27+ chain topology:** Uses the modern DOCKER-FORWARD/DOCKER-CT/DOCKER-BRIDGE structure, not the older DOCKER-ISOLATION-STAGE-1/2 pattern.
