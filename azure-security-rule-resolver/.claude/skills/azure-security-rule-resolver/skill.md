# azure-security-rule-resolver — Claude Code Skill

## Description

Resolves the Azure dual-gate NSG evaluation model against a specific traffic tuple and returns a deterministic ALLOW/DENY verdict — or audits all rules for shadowed entries and posture findings. Input is the JSON output of `az network nic list-effective-nsg`.

## When to Use

Invoke when the user:
- Provides `az network nic list-effective-nsg` JSON and asks whether specific traffic is allowed or denied
- Asks "why is port X blocked?" or "which rule is dropping this traffic?"
- Wants to audit effective NSG rules for shadowed rules or security posture issues
- Uses `/azure-security-rule-resolver` explicitly

## Invocation

```
# Verdict mode — evaluate a specific traffic tuple
/azure-security-rule-resolver <nsg.json> --src <IP> --dst <IP:PORT> --proto <tcp|udp|icmp|*> --direction inbound|outbound

# Audit mode — full rule analysis, no specific tuple
/azure-security-rule-resolver <nsg.json>
```

**Arguments:**
- `FILE` — required. Path to the JSON output of `az network nic list-effective-nsg`.
- `--src <IP>` — source IP address of the traffic being evaluated.
- `--dst <IP:PORT>` — destination IP and port (e.g. `10.0.2.10:443`). Port can be `*` for audit.
- `--proto <tcp|udp|icmp|*>` — protocol. Case-insensitive.
- `--direction inbound|outbound` — traffic direction relative to the VM whose NIC was captured. **Required in verdict mode.** Inbound = traffic arriving at the VM; outbound = traffic leaving the VM.

If `--src`, `--dst`, `--proto`, and `--direction` are all provided: run **Verdict mode**.
If any of `--src`, `--dst`, `--proto`, `--direction` are omitted: run **Audit mode**.

**Choosing the direction:**
- Use `--direction inbound` when investigating why traffic cannot reach this VM (e.g. a client cannot connect to a service running here).
- Use `--direction outbound` when investigating why this VM cannot reach another host (e.g. the VM cannot connect to a database or external endpoint).
- The NIC captured with `az network nic list-effective-nsg` must be the NIC of the VM whose traffic you are analyzing. If you captured the wrong NIC, the direction will be wrong.

---

## Execution Steps

### Step 1 — Parse Arguments

Extract from the invocation:
- `FILE` — required path to the effective NSG JSON
- `--src`, `--dst`, `--proto`, `--direction` — optional; all four required for verdict mode

If no `FILE` is provided, respond with usage and stop:
```
Usage:
  /azure-security-rule-resolver <nsg.json> \
    [--src <IP>] [--dst <IP:PORT>] [--proto <tcp|udp|icmp|*>] [--direction inbound|outbound]

To capture the input:
  az network nic list-effective-nsg --resource-group <RG> --name <NIC_NAME> -o json > nsg.json
```

If `--direction` is provided but is not `inbound` or `outbound` (case-insensitive):
```
Error: --direction must be 'inbound' or 'outbound'.
```
Stop.

If `--src`, `--dst`, `--proto` are all provided but `--direction` is missing:
```
Error: --direction inbound|outbound is required in verdict mode.
  Use --direction inbound if this VM is the destination (traffic arriving at the VM).
  Use --direction outbound if this VM is the source (traffic leaving the VM).
```
Stop.

If `--dst` is provided, parse the destination into IP and port:
- `10.0.2.10:443` → dst_ip = `10.0.2.10`, dst_port = `443`
- `10.0.2.10` (no port) → dst_ip = `10.0.2.10`, dst_port = `*`

---

### Step 2 — Pre-flight Checks

Run these checks using Bash. Fail fast with a clear message.

**Check 1: File exists**
```bash
test -f "<FILE>" && echo "OK" || echo "NOT_FOUND"
```
If NOT_FOUND: `Error: File not found: <FILE>`  Stop.

**Check 2: preprocessor is installed**
```bash
ls ~/.claude/skills/azure-security-rule-resolver/nsg_preprocessor.py 2>/dev/null && echo "FOUND" || echo "NOT_FOUND"
```
If NOT_FOUND:
```
Error: nsg_preprocessor.py not found at ~/.claude/skills/azure-security-rule-resolver/
Install it by copying it from the skill repo:
  cp <repo>/azure-security-rule-resolver/.claude/skills/azure-security-rule-resolver/nsg_preprocessor.py \
     ~/.claude/skills/azure-security-rule-resolver/
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
python3 ~/.claude/skills/azure-security-rule-resolver/nsg_preprocessor.py "<FILE>"
```

Capture the JSON output. If the preprocessor exits non-zero or returns an `"error"` key:
```
Error: Failed to parse <FILE>.
Ensure the file is the output of: az network nic list-effective-nsg -o json
Detail: <error message from preprocessor>
```
Stop.

If `parse_warnings` is non-empty, display each warning before proceeding.

---

### Step 4 — Analyse

Apply the analysis framework below based on the mode.

---

## Analysis Framework

### Azure NSG Evaluation Model

Azure evaluates NSG rules using a strict, non-negotiable sequence. You must apply these rules exactly based on the `--direction` argument.

**Inbound traffic** (`--direction inbound`):
```
[1] Subnet NSG — evaluate inbound_rules in priority order (lowest number first)
       First matching rule → verdict for this gate (ALLOW or DENY)
       If DENY → traffic is dropped. Stop. NIC NSG is never reached.
[2] NIC NSG — evaluate inbound_rules in priority order (lowest number first)
       First matching rule → verdict for this gate
Final result: ALLOWED only if BOTH gates return ALLOW.
```

**Outbound traffic** (`--direction outbound`):
```
[1] NIC NSG — evaluate outbound_rules in priority order (lowest number first)
       First matching rule → verdict for this gate
       If DENY → traffic is dropped. Stop. Subnet NSG is never reached.
[2] Subnet NSG — evaluate outbound_rules in priority order (lowest number first)
       First matching rule → verdict for this gate
Final result: ALLOWED only if BOTH gates return ALLOW.
```

**Critical:** Only evaluate the rules in the direction matching `--direction`. Inbound rules are only evaluated for inbound traffic; outbound rules only for outbound traffic. Never cross-evaluate.

**If only one NSG is present** (no subnet NSG or no NIC NSG): only that single gate applies.

### Rule Matching

A rule matches the traffic tuple when ALL of the following are true:

| Field | Match condition |
|---|---|
| Direction | Rule direction == traffic direction (Inbound/Outbound) |
| Protocol | Rule protocol == `*` OR rule protocol == traffic protocol (case-insensitive) |
| Source address | Rule source == `*` OR traffic source IP falls within the rule's CIDR/prefix |
| Destination address | Rule destination == `*` OR traffic dest IP falls within the rule's CIDR/prefix |
| Destination port | Rule port == `*` OR traffic dest port == rule port OR traffic dest port is within rule's port range |

**Service tags:** If a rule uses a service tag (e.g., `AzureCloud`, `Internet`, `VirtualNetwork`):
- `VirtualNetwork` matches IPs within this VNet's address space, directly peered VNets, and on-premises ranges connected via VPN or ExpressRoute. It does **not** mean all RFC 1918 — it is scoped to the topology known to this specific VNet.
- `Internet` matches any IP not recognised as belonging to this VNet or its connected spaces — the inverse of VirtualNetwork for public addressing.
- `AzureLoadBalancer` matches the Azure load balancer health probe source (168.63.129.16).
- For all other service tags, state that the match cannot be determined without the tag membership and note it in the findings.

**Priority:** Lower priority number = higher precedence = evaluated first.

**First match:** Evaluation stops at the first matching rule per gate. Lower-priority rules are never evaluated if a higher-priority rule matches.

---

## Verdict Mode Output

```markdown
## 🔍 Security Rule Resolution

**Traffic:** <proto> from <src> to <dst_ip>:<dst_port> — Direction: Inbound / Outbound

### Gate Evaluation

| Gate | NSG Name | Winning Rule | Priority | Action |
|:-----|:---------|:------------|:---------|:-------|
| Subnet NSG | <nsg_name> | `<rule_name>` | <priority> | **ALLOW** / **DENY** |
| NIC NSG | <nsg_name> | `<rule_name>` | <priority> | **ALLOW** / **DENY** |

### 🔴 Final Verdict: DENIED  /  🟢 Final Verdict: ALLOWED

**Root cause:** <which gate, which rule name, which priority, and why it fires>

**Actionable next step:** <specific remediation — which NSG, what rule to add/remove/reprioritise>
```

**Notes:**
- If only one gate is present, show only that gate row and note the other is absent.
- If the winning rule is a default rule (priority ≥ 65000), note it explicitly.
- If the NIC NSG is never evaluated because the subnet NSG denied the traffic, mark the NIC NSG row as `Not evaluated`.
- If a shadowed rule was relevant (an ALLOW rule that would have permitted the traffic but is blocked by a higher-priority DENY), call it out after the table.

---

## Audit Mode Output

```markdown
## 🛡️ Effective NSG Audit

**Gates:** <N> NSG(s) found — <list of NSG names and their gate type>

### Inbound Rules

#### <subnet-nsg-name> (Subnet NSG)

| Priority | Rule Name | Protocol | Source | Dest Port | Action | Notes |
|:---------|:----------|:---------|:-------|:----------|:-------|:------|
| 100 | `deny-all-inbound` | * | * | * | **DENY** | |
| 1000 | `allow-https` | TCP | * | 443 | ALLOW | ⚠️ Shadowed by `deny-all-inbound` |
| 65000 | `AllowVnetInBound` | * | VirtualNetwork | * | ALLOW | Default rule |

#### <nic-nsg-name> (NIC NSG)
...

### Outbound Rules
...

### 🔎 Notable Findings

- **Shadowed rules:** <list any rules whose `shadowed_by` field is non-null — name the shadowing rule and explain the traffic impact>
- **Security posture:** <default-deny or default-allow for inbound; same for outbound>
- **Overly permissive rules:** <any ALLOW rule with source=* and dest=* and port=*>
- **Default rules as sole gatekeepers:** <any direction where only default rules exist, meaning no custom rules have been configured>
```

**Notes on audit mode defaults:**
- Show all rules including defaults.
- Highlight shadowed rules with ⚠️.
- In the Notable Findings section, omit sub-headings that have nothing to report.

---

## Known Limitations

State these clearly in the report when relevant:

| Limitation | When to flag |
|---|---|
| **ASGs** | A rule uses an Application Security Group as source or destination. Claude cannot resolve ASG membership. State the rule name, note that ASG membership is required to determine if the traffic matches, and ask the user to provide the ASG definition if needed. |
| **Service tags** | A rule uses a service tag other than `VirtualNetwork`, `Internet`, or `AzureLoadBalancer`. State that the match cannot be determined and list the tag name. |
| **OS firewall / NVA** | This skill evaluates Azure NSGs only. If traffic passes both NSG gates but still fails, the cause may be an OS-level firewall (iptables/nftables) or a Network Virtual Appliance. |
| **Routing** | NSGs are evaluated only when the packet reaches the NIC. If traffic is blackholed by a routing decision before reaching the NIC, the NSG evaluation is irrelevant. |
