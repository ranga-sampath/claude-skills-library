# How to Use: azure-security-rule-resolver Skill

## Installation

### 1. Clone the skills library

```bash
git clone https://github.com/ranga-sampath/claude-skills-library
cd claude-skills-library/azure-security-rule-resolver
```

### 2. Install the skill globally in Claude Code

Claude Code discovers skills from `~/.claude/skills/` — your global skills directory. Copying the files there registers the skill for every Claude Code session on this machine, regardless of which project directory you are working in.

```bash
mkdir -p ~/.claude/skills/azure-security-rule-resolver
cp .claude/skills/azure-security-rule-resolver/skill.md ~/.claude/skills/azure-security-rule-resolver/
cp .claude/skills/azure-security-rule-resolver/nsg_preprocessor.py ~/.claude/skills/azure-security-rule-resolver/
```

### 3. Verify the skill is available

Open Claude Code and type `/` — `azure-security-rule-resolver` should appear in the autocomplete list.

---

## Capturing the Input

```bash
# Capture effective NSG state for a specific NIC
az network nic list-effective-nsg \
  --name <nic-name> \
  --resource-group <resource-group-name> \
  -o json > effective-nsg.json
```

You need the NIC name, not the VM name. To find the NIC name for a VM:

```bash
az vm show \
  --name <vm-name> \
  --resource-group <resource-group-name> \
  --query "networkProfile.networkInterfaces[].id" \
  -o tsv | awk -F'/' '{print $NF}'
```

The output is a JSON object with a `value` array containing one entry per NSG attached to the NIC (typically one for the subnet NSG, one for the NIC NSG).

---

## Usage

```
/azure-security-rule-resolver <nsg.json> [--src IP] [--dst IP:PORT] [--proto tcp|udp|icmp|*] [--direction inbound|outbound]
```

### Verdict mode

Provide all four arguments to get a definitive Allow/Deny verdict:

```bash
# Is TCP from 10.0.1.5 to 10.0.2.10:5432 allowed? (client cannot reach DB — inbound to DB VM)
/azure-security-rule-resolver effective-nsg.json \
  --src 10.0.1.5 \
  --dst 10.0.2.10:5432 \
  --proto tcp \
  --direction inbound
```

```bash
# Can this VM reach 10.0.3.5:22? (VM cannot SSH out — outbound from this VM)
/azure-security-rule-resolver effective-nsg.json \
  --src 10.0.1.10 \
  --dst 10.0.3.5:22 \
  --proto tcp \
  --direction outbound
```

### Audit mode

Omit one or more tuple arguments to get a full security audit:

```bash
# Full audit — rule tables, shadow detection, notable findings
/azure-security-rule-resolver effective-nsg.json

# Audit focused on inbound (no dst port specified)
/azure-security-rule-resolver effective-nsg.json --src 10.0.1.5 --proto tcp
```

---

## Understanding the Output

### Verdict mode output

The output is a markdown report in the Claude Code conversation:

```markdown
## 🔍 Security Rule Resolution

**Traffic:** TCP from 10.0.1.5 to 10.0.2.10:5432 (Inbound)

### Gate Evaluation

| Gate | NSG Name | Winning Rule | Priority | Action |
|:-----|:---------|:------------|:---------|:-------|
| Subnet NSG | ghost-demo-subnet-nsg | `ghost-demo-subnet-block-5432` | 100 | **DENY** |
| NIC NSG | ghost-demo-nic-nsg | Not evaluated | — | — |

### 🔴 Final Verdict: DENIED

**Root cause:** `ghost-demo-subnet-block-5432` (priority 100) on the subnet NSG matches
all TCP traffic to port 5432. The subnet gate fires first for inbound traffic — the NIC
NSG is never reached.

**Actionable next step:** Remove `ghost-demo-subnet-block-5432` from ghost-demo-subnet-nsg,
or add a higher-priority ALLOW rule for the specific source IP and port.
```

### Audit mode output

```markdown
## 🛡️ Effective NSG Audit

**Gates:** 2 NSGs — prod-app-subnet-nsg (Subnet NSG), prod-app-vm-nic-nsg (NIC NSG)

### Inbound Rules

#### prod-app-subnet-nsg (Subnet NSG)

| Priority | Rule Name | Protocol | Source | Dest Port | Action | Notes |
|:---------|:----------|:---------|:-------|:----------|:-------|:------|
| 100 | `allow-https-from-lb` | Tcp | AzureLoadBalancer | 443 | ALLOW | |
| 500 | `deny-all-other-inbound` | All | * | * | **DENY** | |
| 600 | `allow-monitoring-probe` | Tcp | 10.0.20.0/24 | 8443 | ALLOW | ⚠️ Shadowed by `deny-all-other-inbound` |

### 🔎 Notable Findings

- **Shadowed rules:** `allow-monitoring-probe` (priority 600) is unreachable — ...
- **Service tags:** `Storage` in allow-storage-outbound cannot be resolved without Azure IP range data.
```

Audit mode always shows **all rules across all gates** — it is not filtered to a particular direction or source even if partial tuple arguments were provided.

---

## Common Workflows

### Investigating a connectivity complaint

```bash
# 1. Find the NIC
az vm show -n <vm-name> -g <rg> --query "networkProfile.networkInterfaces[].id" -o tsv

# 2. Capture effective NSG state
az network nic list-effective-nsg --name <nic-name> -g <rg> -o json > incident-nsg.json

# 3. Run verdict mode — use inbound if traffic is arriving AT this VM,
#    outbound if this VM is the source of the failing traffic
/azure-security-rule-resolver incident-nsg.json \
  --src <reported-src-ip> \
  --dst <reported-dst-ip>:<reported-dst-port> \
  --proto tcp \
  --direction inbound
```

### Pre-change NSG audit

```bash
# Before applying a change, audit the full current state
/azure-security-rule-resolver pre-change-nsg.json
```

### Post-change verification

```bash
# After rollback, capture new state and verify
az network nic list-effective-nsg --name <nic-name> -g <rg> -o json > post-rollback-nsg.json
/azure-security-rule-resolver post-rollback-nsg.json \
  --src <src-ip> \
  --dst <dst-ip>:<port> \
  --proto tcp \
  --direction inbound
```

---

## Troubleshooting

### "File not found" or "Cannot read JSON"

Verify the file exists and contains valid JSON:

```bash
python3 -c "import json; json.load(open('effective-nsg.json'))" && echo "Valid JSON"
```

If the file is empty, the `az` command may have returned an error. Re-run with `--debug` to inspect.

### "parse_warnings: gate identification fell back to positional"

The preprocessor could not find `association.subnet` or `association.networkInterface` in one or more entries. This happens with some older API versions or non-standard JSON extractions. The gates are still identified positionally (first entry = subnet NSG, second = NIC NSG) but verify manually that the ordering is correct.

### "Only one gate found"

If only a subnet NSG or only a NIC NSG is attached, the preprocessor reports `gate_count: 1`. This is valid — some VMs have no NIC-level NSG. The skill will evaluate the single gate and note that the second gate is absent.

### Service tag rules in verdict mode

If a rule uses a service tag (e.g., `AzureCloud`, `Storage`) and you are running in verdict mode, the skill cannot determine whether your source or destination IP falls within the tag's CIDR ranges. It will flag this in the output and provide a conservative interpretation. To resolve definitively, download the Azure IP Ranges JSON from the Microsoft Download Center (search "Azure IP Ranges and Service Tags" on microsoft.com/download) and cross-reference manually.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| Application Security Groups | ASG membership is not included in effective-nsg output. Rules referencing ASGs are flagged but cannot be resolved. |
| Service tags | Tag-to-CIDR mapping requires Azure's IP Ranges JSON. Tags are passed through with a flag rather than expanded. |
| OS firewall | iptables/nftables/Windows Firewall run inside the VM. NSG evaluation is external. Use iptables-explain for OS-level analysis. |
| NVA/firewall appliances | If traffic is routed through an NVA, the NVA's own ACLs are not visible to this skill. |
| Routing | A DENY verdict does not distinguish between NSG drop and routing black-hole. Use azure-effective-route-summarizer to rule out routing issues first. |
