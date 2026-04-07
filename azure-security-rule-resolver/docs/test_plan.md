# Test Plan: azure-security-rule-resolver Skill

## Test Fixtures

All fixtures are in `fixtures/`. Each fixture is a JSON file in the `az network nic list-effective-nsg` format and tests one specific behaviour.

| Fixture | Description | Primary Behaviour Under Test |
|---|---|---|
| `fx-01-inbound-both-allow.json` | Two NSGs, both allow TCP 443 inbound | Happy path — verdict ALLOW, both gates pass |
| `fx-02-subnet-deny-overrides-nic-allow.json` | Subnet NSG denies port 5432, NIC NSG allows it | Subnet gate fires first; NIC never evaluated |
| `fx-03-nic-deny-clean-subnet.json` | Subnet NSG allows port 8080, NIC NSG denies it | Both gates evaluated inbound; NIC denies last |
| `fx-04-shadowed-allow-rule.json` | Wildcard DENY at priority 100, ALLOW at 200 | Shadow detection — allow-https-inbound unreachable |
| `fx-05-outbound-nic-first.json` | Outbound: NIC denies, subnet allows | Outbound gate order — NIC evaluated before subnet |
| `fx-06-no-nic-nsg.json` | Subnet NSG only, no NIC NSG | Single gate — gate_count=1, correct evaluation |
| `fx-07-service-tag-rule.json` | Rules using AzureCloud, Storage, AzureMonitor | Service tag pass-through and flagging |
| `fx-08-port-range.json` | Port ranges 8080-8090, 3000-3010 | Port range matching |
| `fx-09-default-rule-wins.json` | No custom rules — default rules only | Default rule evaluation; audit notes no custom rules |
| `fx-10-complex-production.json` | Multi-rule production NSGs, shadow, service tags | Combined behaviour — shadow + service tags + tiered rules |

---

## Test Scenarios

### T1 — Happy path inbound verdict (fx-01)

```
/azure-security-rule-resolver fixtures/fx-01-inbound-both-allow.json \
  --src 10.0.0.5 \
  --dst 10.0.1.10:443 \
  --proto tcp \
  --direction inbound
```

**Expected:**
- Preprocessor: `gate_count: 2`, both gates identified (subnet-nsg, nic-nsg)
- Verdict: ALLOWED
- Subnet gate: matches `allow-https-inbound` (priority 200, protocol Tcp, src=`*`, port 443) → Allow. Source 10.0.0.5 matches `*`.
- NIC gate: matches `allow-https-nic` (priority 300, protocol Tcp, src=`10.0.0.0/16`, port 443) → Allow. 10.0.0.5 is in 10.0.0.0/16.
- No shadowed rules, no parse warnings

---

### T2 — Subnet deny overrides NIC allow (fx-02)

```
/azure-security-rule-resolver fixtures/fx-02-subnet-deny-overrides-nic-allow.json \
  --src 10.0.1.5 \
  --dst 10.0.2.10:5432 \
  --proto tcp \
  --direction inbound
```

**Expected:**
- Verdict: DENIED
- Blocking gate: subnet-nsg (ghost-demo-subnet-nsg)
- Blocking rule: `ghost-demo-subnet-block-5432` (priority 100, Tcp, src=`*`, dst=`*`, port=5432)
- NIC NSG: marked as not evaluated — subnet gate terminated evaluation on DENY
- Root cause clearly states the subnet DENY fires before the NIC ALLOW is reached
- Actionable step: modify or remove `ghost-demo-subnet-block-5432` on the subnet NSG

---

### T3 — NIC deny, subnet allows (fx-03)

```
/azure-security-rule-resolver fixtures/fx-03-nic-deny-clean-subnet.json \
  --src 1.2.3.4 \
  --dst 10.0.1.20:8080 \
  --proto tcp \
  --direction inbound
```

**Expected:**
- Verdict: DENIED
- Subnet gate: matches `allow-web-traffic` (priority 100, Tcp, src=`*`, port=8080) → Allow
- NIC gate: matches `deny-port-8080-nic` (priority 200, Tcp, src=`*`, dst=`*`, port=8080) → Deny
- Output shows both gates were evaluated: subnet passed, NIC denied
- No short-circuit after subnet ALLOW — inbound evaluation always proceeds to NIC gate

---

### T4 — Shadow detection (fx-04)

```
/azure-security-rule-resolver fixtures/fx-04-shadowed-allow-rule.json
```

**Expected (audit mode):**
- `allow-https-inbound` (priority 200) flagged as SHADOWED by `deny-all-custom` (priority 100)
  - deny-all-custom is protocol=All, ports=0-65535, src=`*`, dst=`*` — complete wildcard → definitive shadow
- `allow-ssh-inbound` (priority 300) also flagged as SHADOWED by `deny-all-custom`
- Default rules `AllowVnetInBound` (65000) and `AllowAzureLoadBalancerInBound` (65001) also shadowed by `deny-all-custom` — correctly flagged
- NIC NSG (default rules only) — no shadows reported there (deny-all-custom only applies to subnet-nsg)
- Shadow callout names the specific blocking rule and explains it can never be reached

Verdict mode cross-check:
```
/azure-security-rule-resolver fixtures/fx-04-shadowed-allow-rule.json \
  --src 1.2.3.4 \
  --dst 10.0.1.5:443 \
  --proto tcp \
  --direction inbound
```
**Expected:** DENIED — `deny-all-custom` (priority 100, protocol=All) matches first. `allow-https-inbound` is shadowed and must NOT appear as the matching rule.

---

### T5 — Outbound gate order (fx-05)

```
/azure-security-rule-resolver fixtures/fx-05-outbound-nic-first.json \
  --src 10.0.1.10 \
  --dst 10.0.3.5:22 \
  --proto tcp \
  --direction outbound
```

**Expected:**
- Verdict: DENIED
- Direction: Outbound — NIC NSG is evaluated **first**
- NIC gate (first): `deny-lateral-movement` (priority 100, Tcp, dst=10.0.3.0/24, port=22) → Deny. 10.0.3.5 is in 10.0.3.0/24. Evaluation stops.
- Subnet NSG: not evaluated — NIC gate terminated outbound evaluation on DENY
- The subnet NSG has `allow-ssh-to-backend` (priority 200) which would allow this traffic, but it is never evaluated
- Output explicitly states NIC-first outbound gate order

---

### T6 — Single gate, no NIC NSG (fx-06)

```
/azure-security-rule-resolver fixtures/fx-06-no-nic-nsg.json \
  --src 10.0.1.10 \
  --dst 10.0.1.5:80 \
  --proto tcp \
  --direction inbound
```

**Expected:**
- Preprocessor: `gate_count: 1`
- Only one gate (subnet-nsg: db-subnet-nsg) evaluated; no NIC NSG present
- `allow-http-from-web-tier` (priority 100, Tcp, src=10.0.1.0/24, port=80): src 10.0.1.10 is in 10.0.1.0/24 ✓ → Allow
- Verdict: ALLOWED (single gate)
- Skill notes no NIC-level NSG is attached to this NIC

Audit mode cross-check:
```
/azure-security-rule-resolver fixtures/fx-06-no-nic-nsg.json
```
**Expected:** Notable finding that only one NSG gate is present; no NIC-level NSG attached.

---

### T7 — Service tag rules (fx-07)

```
/azure-security-rule-resolver fixtures/fx-07-service-tag-rule.json
```

**Expected (audit mode):**
- Rules with `AzureMonitor`, `Storage`, `AzureCloud` as source or destination are listed correctly in the rule tables
- `AzureMonitor`, `Storage`, `AzureCloud` flagged in Notable Findings as unresolvable without Azure IP range data
- `Internet` and `VirtualNetwork` recognised as known built-ins — NOT flagged
- `AzureLoadBalancer` recognised as known built-in (168.63.129.16) — NOT flagged

Verdict mode cross-check — inbound, source from an unknown service tag:
```
/azure-security-rule-resolver fixtures/fx-07-service-tag-rule.json \
  --src 10.0.1.5 \
  --dst 52.96.0.0:443 \
  --proto tcp \
  --direction outbound
```
**Expected:**
- `allow-azure-monitor` (priority 100, dst=AzureMonitor): cannot resolve whether 52.96.0.0 is in AzureMonitor range → flagged as uncertain
- `allow-storage-outbound` (priority 110, dst=Storage): same → flagged as uncertain
- Conservative interpretation provided; user directed to Azure IP Ranges JSON for resolution

---

### T8 — Port range matching (fx-08)

**T8a — port inside range, source in allowed CIDR:**
```
/azure-security-rule-resolver fixtures/fx-08-port-range.json \
  --src 10.0.0.5 \
  --dst 10.0.1.5:8085 \
  --proto tcp \
  --direction inbound
```

**Expected:**
- `deny-port-8085-override` (priority 50, src=192.168.0.0/16): source 10.0.0.5 is NOT in 192.168.0.0/16 → no match
- `allow-api-port-range` (priority 100, src=10.0.0.0/8, port=8080-8090): src 10.0.0.5 in 10.0.0.0/8 ✓, port 8085 inside range [8080-8090] ✓ → Allow
- Verdict: ALLOWED

**T8b — same port, source matches the deny-override:**
```
/azure-security-rule-resolver fixtures/fx-08-port-range.json \
  --src 192.168.1.5 \
  --dst 10.0.1.5:8085 \
  --proto tcp \
  --direction inbound
```

**Expected:**
- `deny-port-8085-override` (priority 50, src=192.168.0.0/16, port=8085): src 192.168.1.5 in 192.168.0.0/16 ✓, port 8085 ✓ → Deny
- Verdict: DENIED at priority 50, before `allow-api-port-range` (priority 100) is reached

---

### T9 — Default rules only (fx-09)

**T9a — inbound from VNet source:**
```
/azure-security-rule-resolver fixtures/fx-09-default-rule-wins.json \
  --src 10.0.5.10 \
  --dst 10.0.1.5:443 \
  --proto tcp \
  --direction inbound
```

**Expected:**
- Both gates: `AllowVnetInBound` (priority 65000, VirtualNetwork → VirtualNetwork) matches if both IPs are in the same VNet. Skill notes this depends on VNet topology.
- Rule cited as default rule (is_default=true, priority ≥ 65000)
- Verdict: ALLOWED (via default rule)
- Audit should note no custom rules are configured

**T9b — inbound from Internet source:**
```
/azure-security-rule-resolver fixtures/fx-09-default-rule-wins.json \
  --src 203.0.113.50 \
  --dst 10.0.1.5:443 \
  --proto tcp \
  --direction inbound
```

**Expected:**
- `AllowVnetInBound` (65000): src=203.0.113.50 is not VirtualNetwork → no match
- `AllowAzureLoadBalancerInBound` (65001): src is not AzureLoadBalancer (168.63.129.16) → no match
- `DenyAllInBound` (65500): src=`*`, dst=`*`, all ports → matches → Deny
- Verdict: DENIED via default rule `DenyAllInBound` (priority 65500) at both gates

Audit mode:
```
/azure-security-rule-resolver fixtures/fx-09-default-rule-wins.json
```
**Expected:** Notable finding that no custom rules are configured; entire posture relies on Azure default rules.

---

### T10 — Complex production (fx-10)

**Audit mode:**
```
/azure-security-rule-resolver fixtures/fx-10-complex-production.json
```

**Expected:**
- 2 gates: `prod-app-subnet-nsg` (subnet) and `prod-app-vm-nic-nsg` (NIC)
- Shadows in subnet-nsg inbound: `allow-monitoring-probe` (600), `AllowVnetInBound` (65000), `AllowAzureLoadBalancerInBound` (65001) — all shadowed by `deny-all-other-inbound` (500, wildcard All, `*` src/dst, 0-65535 ports)
- Service tag: `Storage` in `allow-storage-outbound` flagged as unresolvable
- Notable: `deny-internet-outbound` (subnet NSG, priority 400) overrides `AllowInternetOutBound` default (65001) for Internet-bound traffic

**Verdict A — inbound, source not in any ALLOW range:**
```
/azure-security-rule-resolver fixtures/fx-10-complex-production.json \
  --src 10.0.5.10 \
  --dst 10.0.2.15:443 \
  --proto tcp \
  --direction inbound
```
**Expected:**
- Subnet gate: 10.0.5.10 is not AzureLoadBalancer (rule 100), not in 10.0.1.0/24 (rule 110), not in 10.0.10.0/27 (rule 200), port 443 ≠ 22 → falls to `deny-all-other-inbound` (500) → DENY
- NIC NSG: not evaluated (subnet terminated on DENY)
- Verdict: DENIED at subnet gate

**Verdict B — inbound, source in the frontend CIDR:**
```
/azure-security-rule-resolver fixtures/fx-10-complex-production.json \
  --src 10.0.1.5 \
  --dst 10.0.2.15:443 \
  --proto tcp \
  --direction inbound
```
**Expected:**
- Subnet gate: `allow-https-from-frontend` (priority 110, src=10.0.1.0/24, dst=10.0.2.0/24, port=443). 10.0.1.5 in 10.0.1.0/24 ✓, 10.0.2.15 in 10.0.2.0/24 ✓, port 443 ✓ → Allow
- NIC gate: `deny-high-ports` (100, port=9000-9999): port 443 not in [9000-9999] → no match. `allow-https-nic` (200, src=10.0.0.0/16, port=443): 10.0.1.5 in /16 ✓ → Allow
- Verdict: ALLOWED

**Verdict C — inbound, high port blocked at NIC:**
```
/azure-security-rule-resolver fixtures/fx-10-complex-production.json \
  --src 10.0.5.10 \
  --dst 10.0.2.15:9500 \
  --proto tcp \
  --direction inbound
```
**Expected:**
- Subnet gate: port 9500 doesn't match 443 (rules 100, 110) or 22 (rule 200) → `deny-all-other-inbound` (500) → DENY
- NIC: not evaluated
- Verdict: DENIED at subnet gate (not NIC — subnet catches it first)

---

## Accuracy Checklist

Before considering the skill validated, verify each of the following:

- [ ] T1: `allow-https-nic` matches because 10.0.0.5 is in 10.0.0.0/16 — CIDR evaluation correct
- [ ] T2: Subnet deny cited as blocking gate; NIC NSG correctly marked as not evaluated
- [ ] T3: Both inbound gates evaluated — subnet ALLOW does not short-circuit to final ALLOW
- [ ] T4: Shadowed rules in audit mode; matching rule in verdict mode is deny-all-custom not allow-https-inbound
- [ ] T5: `--direction outbound` causes NIC to be evaluated first; subnet ALLOW not overriding NIC DENY
- [ ] T6: Single gate reported correctly; verdict ALLOW via `allow-http-from-web-tier`
- [ ] T7: AzureMonitor/Storage/AzureCloud flagged; Internet/VirtualNetwork/AzureLoadBalancer not flagged
- [ ] T8: Port 8085 matched inside range [8080-8090]; deny-override fires first for 192.168.x.x source
- [ ] T9: Default rules cited explicitly as default (is_default=true); Internet src falls to DenyAllInBound
- [ ] T10: Three shadows detected in subnet-nsg; T10-C verdict DENIED at subnet not NIC

---

## Real Fixture Capture (Optional)

To supplement the synthetic fixtures with real Azure output:

```bash
# On an Azure VM or from a machine with Azure CLI access
az network nic list \
  --resource-group <rg-name> \
  --query "[].{name:name, rg:resourceGroup}" \
  -o table

az network nic list-effective-nsg \
  --name <nic-name> \
  --resource-group <rg-name> \
  -o json > fixtures/fx-real-<vm-name>.json
```

Store real fixtures in `fixtures/` with the `fx-real-` prefix to distinguish them from synthetic ones.
