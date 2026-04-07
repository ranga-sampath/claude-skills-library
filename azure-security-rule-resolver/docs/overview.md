# Overview: azure-security-rule-resolver — Claude Code Skill

## What This Skill Is

An **operational Claude Code skill** — invoked via `/azure-security-rule-resolver` — that reads the JSON output of `az network nic list-effective-nsg` and applies the Azure NSG dual-gate evaluation model to produce a definitive Allow/Deny verdict or a full security audit. Analysis runs natively inside Claude Code; no external API key is required.

## The Problem It Solves

Azure Network Security Groups are evaluated at two independent layers: the subnet NSG and the NIC NSG. Traffic must pass both. When a connectivity problem occurs, the instinctive response is to check one NSG — usually the NIC-level one — find an ALLOW rule, and conclude the configuration is correct. The subnet NSG goes unchecked. If it has a DENY at a lower priority number, it fires first and the ALLOW on the NIC NSG is never reached.

The Azure portal shows each NSG's rules in isolation. `az network nsg rule list` returns one NSG at a time. Neither surfaces the combined effective state across both gates. `az network nic list-effective-nsg` is the correct command — it returns both NSGs for a given NIC — but its JSON output is several hundred lines and the evaluation logic is not immediately obvious.

This skill parses that JSON, identifies the two gates, applies the correct Azure evaluation order, and returns a definitive verdict with the specific rule name and priority that caused the result.

## Architecture: Three Stages

```
az network nic list-effective-nsg output (JSON file)
    │
    ▼
[Stage 1] Validate
    │  Check file exists, preprocessor installed, python3 available
    ▼
[Stage 2] Preprocess  (nsg_preprocessor.py)
    │  Parse JSON → structured gate model
    │  Identify subnet NSG and NIC NSG from association field
    │  Extract NSG names from resource IDs
    │  Normalise rules: sort by priority, expand port ranges, flag defaults
    │  Detect shadowed rules
    ▼
[Stage 3] AI Analysis  (Claude Code — native)
       Reads structured gate model
       Applies Azure dual-gate evaluation model
       Verdict mode: traces traffic tuple through both gates → Allow/Deny
       Audit mode: rule tables, shadow callouts, notable findings
```

**Stages 1–2** run in `nsg_preprocessor.py` (Python stdlib only — no pip installs).

**Stage 3** runs natively inside Claude Code — Claude IS the analyst.

## Azure Dual-Gate Evaluation Model

Azure NSG evaluation follows a strict, fixed sequence depending on traffic direction:

**Inbound traffic:**
1. Subnet NSG evaluated first
2. NIC NSG evaluated second
3. Both must allow — if either denies, traffic is dropped

**Outbound traffic:**
1. NIC NSG evaluated first
2. Subnet NSG evaluated second
3. Both must allow — if either denies, traffic is dropped

Within each NSG, the rule with the lowest priority number wins. Evaluation stops at the first matching rule — lower numbers are evaluated before higher numbers.

Default rules (priority ≥ 65000) are the backstop: `AllowVnetInBound` (65000), `AllowAzureLoadBalancerInBound` (65001), `DenyAllInBound` (65500) — and their outbound equivalents.

## What the Preprocessor Produces

`nsg_preprocessor.py` converts the raw `az network nic list-effective-nsg` JSON into a structured gate model:

```json
{
  "gate_count": 2,
  "gates": [
    {
      "gate": "subnet-nsg",
      "nsg_name": "app-subnet-nsg",
      "nsg_id": "/subscriptions/.../networkSecurityGroups/app-subnet-nsg",
      "association_type": "subnet",
      "association_id": "/subscriptions/.../subnets/app-subnet",
      "inbound_rules": [
        {
          "name": "ghost-demo-subnet-block-5432",
          "priority": 100,
          "direction": "Inbound",
          "access": "Deny",
          "protocol": "Tcp",
          "source_address": "*",
          "destination_address": "*",
          "destination_ports": ["5432"],
          "is_default": false,
          "shadowed_by": null
        }
      ],
      "outbound_rules": [...]
    },
    {
      "gate": "nic-nsg",
      "nsg_name": "app-vm-nic-nsg",
      ...
    }
  ],
  "parse_warnings": []
}
```

Key fields:

| Field | Source | Purpose |
|---|---|---|
| `gate` | `association.subnet` or `association.networkInterface` | Identifies which layer this NSG is attached to |
| `nsg_name` | Last path segment of resource ID | Human-readable NSG name |
| `is_default` | `priority >= 65000` | Distinguish custom vs Azure default rules |
| `shadowed_by` | Shadow detection algorithm | Name of the higher-priority rule that makes this rule unreachable |
| `destination_ports` | Normalised from `destinationPortRange` | Handles ranges ("8080-8090") and single ports |

## Gate Identification

The preprocessor reads the `association` field in each entry of the `value[]` array:

- `association.subnet` present → this is the subnet NSG
- `association.networkInterface` present → this is the NIC NSG
- Neither present → `unknown`, gate labelled positionally with a parse warning

This is more reliable than positional ordering because the Azure API does not guarantee a fixed order for the two entries.

## Shadow Detection

A rule is flagged as shadowed when a higher-priority rule in the same NSG and direction meets all of:

1. **Opposing access**: the blocking rule's access is `Deny` and the shadowed rule's is `Allow` (or vice versa)
2. **Wildcard source**: the blocking rule's source address is `*`
3. **Wildcard destination**: the blocking rule's destination address is `*`

These conditions identify the conservative case — a wildcard DENY that makes any subsequent ALLOW completely unreachable. Partial overlaps (e.g., a DENY on a specific CIDR partially overlapping the ALLOW's CIDR) are not flagged to avoid false positives.

Port range overlap is detected via range arithmetic: "8080-8090" is parsed into `(8080, 8090)` and compared numerically with the overlapping rule's port range.

## Supported Input Formats

The preprocessor handles four envelope variants returned by different Azure CLI versions and contexts:

| Format | Description |
|---|---|
| `{"value": [...]}` | Standard `az network nic list-effective-nsg -o json` output |
| `{"networkSecurityGroups": [...]}` | Alternative field name seen in some API versions |
| Raw list `[...]` | Direct array (e.g., from a scripted extraction) |
| Single object `{...}` | Single NSG wrapped in braces |

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Parsing | Python stdlib | No pip installs; portable |
| Gate identification | `association` field | More reliable than positional ordering |
| NSG name extraction | Last resource ID path segment | Avoids assuming consistent field names across API versions |
| Shadow detection scope | Wildcard src+dst only | Avoids false positives from partial overlaps |
| AI analysis | Claude Code native | No separate API key; Claude IS the LLM |

## What This Skill Intentionally Omits

| Omitted | Why |
|---|---|
| Application Security Groups (ASGs) | Membership list not included in effective-nsg output — flagged as a limitation |
| OS-level firewall | iptables/Windows Firewall runs inside the VM; NSG evaluation is external |
| NVA/firewall appliances | Routing-dependent; NSG analysis is topology-blind |
| Routing | UDR and BGP affect reachability before NSG; use azure-effective-route-summarizer for routing |
| Live Azure CLI execution | Takes a JSON file — does not call Azure APIs directly |
