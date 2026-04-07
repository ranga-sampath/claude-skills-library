# Sample Resolver Report — azure-security-rule-resolver

This document shows reference output for both modes of the skill. Inputs are from the test fixtures in `fixtures/`.

---

## Verdict Mode — Subnet deny overrides NIC allow

**Invocation:**
```
/azure-security-rule-resolver fixtures/fx-02-subnet-deny-overrides-nic-allow.json \
  --src 10.0.1.5 \
  --dst 10.0.2.10:5432 \
  --proto tcp
```

**Input summary:** Two NSGs attached to the NIC. Subnet NSG (`ghost-demo-subnet-nsg`) has a DENY rule for TCP port 5432 at priority 100. NIC NSG (`ghost-demo-nic-nsg`) has an ALLOW rule for TCP port 5432 at priority 1000. Traffic is inbound.

---

### Security Rule Resolution

**Traffic tuple:** TCP  10.0.1.5 → 10.0.2.10:5432  (Inbound)

**Gate Evaluation**

| Gate | NSG | Evaluated | First Matching Rule | Priority | Decision |
|---|---|---|---|---|---|
| subnet-nsg | ghost-demo-subnet-nsg | Yes | ghost-demo-subnet-block-5432 | 100 | **DENY** |
| nic-nsg | ghost-demo-nic-nsg | No — subnet gate terminated evaluation | — | — | — |

**Final Verdict: DENIED**

- **Gate:** subnet-nsg (ghost-demo-subnet-nsg)
- **Rule:** `ghost-demo-subnet-block-5432` (priority 100)
- **Direction:** Inbound — subnet NSG is evaluated before NIC NSG

**Root Cause**

The subnet NSG `ghost-demo-subnet-nsg` has an explicit DENY rule (`ghost-demo-subnet-block-5432`, priority 100) matching all TCP traffic to port 5432. This rule fires before the NIC NSG is reached. The NIC-level ALLOW rule (`allow-postgres`, priority 1000 on `ghost-demo-nic-nsg`) is never evaluated — Azure stops at the first match within each gate, and the subnet gate denied the traffic before evaluation proceeded to the NIC gate.

This is a common misdiagnosis pattern: the engineer checks the NIC NSG, sees an ALLOW for port 5432, and concludes the configuration is correct. The subnet NSG is the gate that was never checked.

**Actionable Next Step**

1. Remove `ghost-demo-subnet-block-5432` from `ghost-demo-subnet-nsg` if the block is no longer required.
2. Or add a higher-priority ALLOW rule (e.g., priority 90) for the specific source IP `10.0.1.5` to port 5432 on the subnet NSG, scoped as narrowly as possible.
3. After making the change, re-capture `az network nic list-effective-nsg` and re-run verdict mode to verify.

---

## Verdict Mode — Happy path, both gates allow

**Invocation:**
```
/azure-security-rule-resolver fixtures/fx-01-inbound-both-allow.json \
  --src 10.0.0.5 \
  --dst 10.0.1.10:443 \
  --proto tcp
```

---

### Security Rule Resolution

**Traffic tuple:** TCP  10.0.0.5 → 10.0.1.10:443  (Inbound)

**Gate Evaluation**

| Gate | NSG | Evaluated | First Matching Rule | Priority | Decision |
|---|---|---|---|---|---|
| subnet-nsg | app-subnet-nsg | Yes | allow-https-inbound | 200 | **ALLOW** |
| nic-nsg | app-vm-nic-nsg | Yes | allow-https-nic | 300 | **ALLOW** |

**Final Verdict: ALLOWED**

Both gates passed. Traffic from `10.0.0.5` to port 443 is permitted by custom rules at both the subnet and NIC level. No default rules were reached.

---

## Audit Mode — Complex production NSGs with shadowed rule

**Invocation:**
```
/azure-security-rule-resolver fixtures/fx-10-complex-production.json
```

---

### NSG Security Audit

**Gate Inventory**

| Gate | NSG | Association |
|---|---|---|
| subnet-nsg | prod-app-subnet-nsg | Subnet: app-tier-subnet |
| nic-nsg | prod-app-vm-nic-nsg | NIC: prod-app-vm-nic |

---

**INBOUND RULES — Gate 1: subnet-nsg (prod-app-subnet-nsg)**
*Evaluated first for inbound traffic.*

| Priority | Name | Protocol | Source | Destination | Port | Access |
|---|---|---|---|---|---|---|
| 100 | allow-https-from-lb | Tcp | AzureLoadBalancer | 10.0.2.0/24 | 443 | Allow |
| 110 | allow-https-from-frontend | Tcp | 10.0.1.0/24 | 10.0.2.0/24 | 443 | Allow |
| 200 | allow-ssh-from-bastion | Tcp | 10.0.10.0/27 | * | 22 | Allow |
| 500 | deny-all-other-inbound | All | * | * | * | **Deny** |
| 600 | allow-monitoring-probe | Tcp | 10.0.20.0/24 | * | 8443 | Allow ⚠ SHADOWED |
| 65000 | AllowVnetInBound *(default)* | All | VirtualNetwork | VirtualNetwork | * | Allow |
| 65001 | AllowAzureLoadBalancerInBound *(default)* | All | AzureLoadBalancer | * | * | Allow |
| 65500 | DenyAllInBound *(default)* | All | * | * | * | Deny |

**OUTBOUND RULES — Gate 1: subnet-nsg (prod-app-subnet-nsg)**

| Priority | Name | Protocol | Source | Destination | Port | Access |
|---|---|---|---|---|---|---|
| 100 | allow-app-to-db | Tcp | 10.0.2.0/24 | 10.0.3.0/24 | 5432 | Allow |
| 110 | allow-storage-outbound | Tcp | * | Storage ⚑ | 443 | Allow |
| 400 | deny-internet-outbound | All | * | Internet | * | **Deny** |
| 65000 | AllowVnetOutBound *(default)* | All | VirtualNetwork | VirtualNetwork | * | Allow |
| 65001 | AllowInternetOutBound *(default)* | All | * | Internet | * | Allow |
| 65500 | DenyAllOutBound *(default)* | All | * | * | * | Deny |

---

**INBOUND RULES — Gate 2: nic-nsg (prod-app-vm-nic-nsg)**
*Evaluated second for inbound traffic.*

| Priority | Name | Protocol | Source | Destination | Port | Access |
|---|---|---|---|---|---|---|
| 100 | deny-high-ports | Tcp | * | * | 9000-9999 | **Deny** |
| 200 | allow-https-nic | Tcp | 10.0.0.0/16 | * | 443 | Allow |
| 300 | allow-ssh-ops | Tcp | 10.0.10.0/27 | * | 22 | Allow |
| 65000 | AllowVnetInBound *(default)* | All | VirtualNetwork | VirtualNetwork | * | Allow |
| 65001 | AllowAzureLoadBalancerInBound *(default)* | All | AzureLoadBalancer | * | * | Allow |
| 65500 | DenyAllInBound *(default)* | All | * | * | * | Deny |

---

### ⚠ Shadowed Rules

**allow-monitoring-probe** (subnet-nsg, priority 600) is shadowed by **deny-all-other-inbound** (priority 500).

`deny-all-other-inbound` matches all traffic (protocol: All, source: `*`, destination: `*`, port: `*`) and fires at priority 500. Any rule at a higher priority number cannot be reached. `allow-monitoring-probe` — intended to allow monitoring traffic from `10.0.20.0/24` to port 8443 — has no effect. It will never match any packet.

**Remediation:** Move `allow-monitoring-probe` to a priority lower than 500 (e.g., priority 400), or remove it if the intent was already captured by another rule. If `deny-all-other-inbound` is intentional as a catch-all, all permit rules must appear before it.

---

### Notable Findings

1. **Service tag — Storage (unresolvable):** `allow-storage-outbound` (subnet-nsg, outbound, priority 110) uses the `Storage` service tag as the destination. The specific CIDR ranges for this tag cannot be determined without Azure's IP Ranges JSON. If you are troubleshooting a specific destination IP, verify manually whether it falls within Azure Storage service tag ranges for your region.

2. **deny-internet-outbound overrides default outbound:** `deny-internet-outbound` (subnet-nsg, priority 400) blocks all traffic to `Internet` destinations. The Azure default rule `AllowInternetOutBound` (priority 65001) is effectively dead for Internet-bound traffic. Any VM in this subnet cannot reach the public Internet unless a custom ALLOW rule is added at a priority higher than 400 for that specific destination.

3. **NIC NSG denies high ports:** `deny-high-ports` (nic-nsg, priority 100) blocks all TCP traffic to ports 9000-9999. This applies to all inbound traffic regardless of source. Verify this is intentional and does not conflict with any legitimate application ports in that range.
