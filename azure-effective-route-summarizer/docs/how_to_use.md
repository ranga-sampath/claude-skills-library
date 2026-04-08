# How to Use: azure-effective-route-summarizer

## Prerequisites

| Requirement | Notes |
|:------------|:------|
| Python 3.10+ | Usually pre-installed on macOS and modern Linux |
| Claude Code | [Install guide](https://docs.anthropic.com/en/docs/claude-code) |
| Azure CLI | Only needed to capture input; not required at analysis time |

No external Python packages required.

---

## Installation

```bash
# 1. Clone the skills library
git clone https://github.com/ranga-sampath/claude-skills-library
cd claude-skills-library/azure-effective-route-summarizer

# 2. Copy to ~/.claude/skills/ — Claude Code discovers skills from this global directory,
#    making the skill available in every session regardless of working directory.
mkdir -p ~/.claude/skills/azure-effective-route-summarizer
cp .claude/skills/azure-effective-route-summarizer/skill.md \
   ~/.claude/skills/azure-effective-route-summarizer/
cp .claude/skills/azure-effective-route-summarizer/route_preprocessor.py \
   ~/.claude/skills/azure-effective-route-summarizer/
```

---

## Capturing the Input

```bash
# Find the NIC name attached to your VM
az vm show \
  --resource-group <rg-name> \
  --name <vm-name> \
  --query "networkProfile.networkInterfaces[].id" \
  -o tsv | xargs -I{} basename {}

# Capture the effective route table for that NIC
az network nic show-effective-route-table \
  --name <nic-name> \
  --resource-group <rg-name> \
  -o json > effective-routes.json
```

> **Important:** Capture the routes from the **NIC of the VM whose traffic you are investigating**, not from the source VM. If you are debugging why `vm-a` cannot reach `vm-b`, capture `vm-b`'s NIC to check inbound routing, or capture `vm-a`'s NIC to check outbound routing.

---

## Usage

### Single-Target Mode

Use this when investigating a specific connectivity failure. Provide the destination IP to find out exactly which route Azure selected.

```bash
/azure-effective-route-summarizer effective-routes.json --dst 10.50.1.10
```

> **`--dst` format:** IPv4 dotted-decimal notation only (e.g., `10.50.1.10`). CIDR notation (e.g., `10.50.1.0/24`) and IPv6 addresses are not accepted.

Output: a single "Winning Route" table with the selected route, all eliminated competitors, and the reason for selection.

### Audit Mode

Use this for a proactive review of the full route table without a specific destination.

```bash
/azure-effective-route-summarizer effective-routes.json
```

Output: the full normalised route table, NVA routes flagged, invalid routes highlighted, and a findings summary.

---

## Workflows

### Workflow 1 — Debugging a Firewall Bypass

Traffic to `10.50.1.10` is bypassing the NVA at `10.0.0.4`. The UDR sends `10.50.0.0/16` through it, but traffic is taking a different path.

```bash
# Step 1: capture the source VM's effective routes
az network nic show-effective-route-table \
  --name app-vm-nic \
  --resource-group prod-rg \
  -o json > routes.json

# Step 2: find the winning route for the target IP
/azure-effective-route-summarizer routes.json --dst 10.50.1.10
```

Expected finding: a more specific system route (`VnetLocal` or `VnetPeering`) with a longer prefix is shadowing the UDR — LPM beats source precedence.

**Fix:** Add a more specific UDR (matching the exact subnet prefix) pointing to the NVA.

---

### Workflow 2 — Blackholed Traffic

Traffic to an on-premises IP is disappearing silently.

```bash
/azure-effective-route-summarizer routes.json --dst 192.168.10.50
```

Expected finding: a route with `next_hop_type = "None"` is the winning route — either a disconnected peering or an explicitly configured blackhole. Azure drops traffic matching a `None` hop silently.

**Fix:** Restore the peering or VPN connection, or remove the `None` hop route if it was unintentional.

---

### Workflow 3 — Confirming ExpressRoute is Active

Verify that on-premises routes learned via ExpressRoute are actually winning over system defaults.

```bash
# Audit mode — review all BGP-learned routes
/azure-effective-route-summarizer routes.json
```

Look for entries with `source = VirtualNetworkGateway`. If any are `state = Invalid`, the ExpressRoute circuit has lost those prefixes.

---

### Workflow 4 — NVA IP Forwarding Verification

After routing traffic to an NVA, verify the NVA NIC has IP Forwarding enabled.

```bash
az network nic show \
  --name nva-nic \
  --resource-group nva-rg \
  --query "enableIpForwarding"
```

If `false`, Azure's fabric will not forward the packet to the NVA's NIC — the packet is dropped before it reaches the VM. This is an Azure platform control, not a VM OS setting.

---

## Troubleshooting

### "Error: File not found"

The path provided does not exist or the shell glob did not resolve. Check:

```bash
ls -la effective-routes.json
```

### "Error: route_preprocessor.py not found"

The preprocessor was not copied to `~/.claude/skills/azure-effective-route-summarizer/`. Re-run the installation step.

### "Error: Not a valid effective route table"

The file is not the output of `az network nic show-effective-route-table`. Common causes:
- Wrong command used (`az network route-table route list` gives a different format)
- File was piped through `jq` and restructured
- Azure portal export format (not directly compatible)

### "BGP tie-break cannot be determined"

Two BGP routes with identical prefixes exist. The skill cannot determine which one Azure is using without AS Path data. Check the VPN/ExpressRoute gateway BGP peer status:

```bash
az network vnet-gateway list-bgp-peer-status \
  --name <gateway-name> \
  --resource-group <rg-name>
```

### "Route has state: Invalid"

The route is present in the table but Azure is not using it. Common causes:
- VNet peering disconnected (peer VNet deleted, or peering in "Initiated" state only)
- VPN Gateway removed or reprovisioning
- ExpressRoute circuit in "Not Provisioned" state

Fix the underlying resource and re-capture the effective routes to confirm the route returns to Active.

---

## Related Skills

- [`azure-security-rule-resolver`](../azure-security-rule-resolver/) — evaluate Azure NSG rules for a specific traffic tuple; use this when routing is confirmed correct but traffic is still blocked
- [`iptables-explain`](../iptables-explain/) — Linux firewall equivalent for traffic blocked inside the VM OS
- [`pcap-forensics`](../pcap-forensics/) — packet-level evidence when neither routing nor NSG explain the drop
