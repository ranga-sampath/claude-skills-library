# How to Use: PCAP Forensic Engine Skill

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/ranga-sampath/claude-skills-library
cd claude-skills-library/pcap-forensics
```

### 2. Install the skill globally in Claude Code

```bash
mkdir -p ~/.claude/skills/pcap-forensics
cp .claude/skills/pcap-forensics/skill.md ~/.claude/skills/pcap-forensics/
cp .claude/skills/pcap-forensics/pcap_extractor.py ~/.claude/skills/pcap-forensics/
```

### 3. Verify tshark is installed

```bash
tshark --version
# Expected: TShark (Wireshark) 4.x.x ...
```

If missing:
- **macOS**: `brew install wireshark`
- **Ubuntu/Debian**: `sudo apt install tshark`
- **RHEL/CentOS**: `sudo yum install wireshark-cli`

### 4. Verify the skill is available in Claude Code

Open Claude Code and type `/` — `pcap-forensics` should appear in the autocomplete list.

---

## Usage

### Single Capture — Forensic Analysis

```
/pcap-forensics ~/captures/incident.pcap
```

Claude will:
1. Run tshark extraction against the file
2. Build a Semantic JSON summary
3. Perform forensic analysis and return a full report inline

**Outputs written to disk** (same directory as the input file):
- `incident_semantic.json` — structured protocol metadata
- The forensic report is displayed in the conversation (not written to disk)

---

### Temporal Compare — What Changed?

Use when you have two captures from the same network segment taken at different times — e.g., before and after a configuration change, or baseline vs. incident.

```
/pcap-forensics ~/captures/baseline.pcap --compare ~/captures/after-change.pcap
```

**Outputs**:
- `baseline_semantic.json`
- `after-change_semantic.json`
- Comparison report inline (regressions, improvements, new issues, resolved issues)

**Normalization**: The report compares rates and ratios, not raw packet counts — so captures of different durations are fairly compared.

---

### Endpoint Correlation — Where Are Packets Dropped?

Use when you have two simultaneous captures from both ends of a network path — e.g., both the client and server ran tcpdump at the same time during a connectivity failure.

```
/pcap-forensics ~/captures/client-side.pcap --compare ~/captures/server-side.pcap --mode endpoint-correlation
```

The first file is always treated as the **source (sender)**, the second as the **destination (receiver)**.

**The report identifies**:
- Flows visible at source but absent at destination (dropped in transit)
- SYN packets sent but not received (firewall/NSG block)
- RTT asymmetry (which direction is slow)
- Overall verdict: CLEAN PATH / PARTIAL DROP / FULL DROP / DEGRADED / ASYMMETRIC ROUTING

---

## Capture Tips

### Capture commands

```bash
# Linux — capture on specific interface, 60 seconds
sudo tcpdump -i eth0 -w /tmp/incident.pcap -G 60 -W 1

# macOS
sudo tcpdump -i en0 -w /tmp/incident.pcap

# Capture only specific protocols (reduces file size)
sudo tcpdump -i eth0 'arp or icmp or tcp or udp port 53' -w /tmp/filtered.pcap

# Remote capture via SSH (no wireshark on remote host required)
ssh user@host "sudo tcpdump -i eth0 -w - 'not port 22'" > /tmp/remote.pcap
```

### What capture duration to use

| Scenario | Recommended duration |
|---|---|
| Intermittent packet loss | 30-120 seconds during the problem period |
| Connectivity failure | 10-30 seconds — capture the failure, not the recovery |
| DNS issues | 60 seconds — needs enough queries to see patterns |
| ARP spoofing investigation | 30 seconds — gratuitous ARPs repeat quickly |
| Baseline for comparison | Match the incident capture duration |

---

## Understanding the Report

### Severity Levels

| Level | Meaning | Example |
|---|---|---|
| CRITICAL | Active security threat | ARP spoofing, DGA malware beaconing |
| HIGH | Service-impacting | Host unreachable, TCP handshake failures |
| MEDIUM | Performance degradation | Retransmissions, elevated DNS latency |
| LOW | Worth monitoring | Occasional retransmissions, minor latency spikes |
| INFO | Benign observation | Healthy capture, normal traffic patterns |

### Frame References

Every finding in the Anomaly Table includes frame numbers. Use these in Wireshark:
- Open the capture in Wireshark
- Press `Ctrl+G` (Go to Frame)
- Enter the frame number to jump directly to the evidence

### The Semantic JSON

The `*_semantic.json` file saved to disk is useful for:
- Feeding into scripts or dashboards
- Comparing captures without re-running tshark
- Archiving a structured record of the incident alongside the raw pcap

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `tshark: command not found` | Install Wireshark: `brew install wireshark` |
| `Error: File not found` | Check the path; use absolute paths if relative paths fail |
| `tshark failed` error | File may be corrupt — try `tshark -r file.pcap -c 1` to test |
| Extractor script not found | Re-run the install step: copy `pcap_extractor.py` to `~/.claude/skills/pcap-forensics/` |
| Empty report sections | Protocol not present in capture — check with `tshark -r file.pcap -q -z io,phs` |
| `/pcap-forensics` not in autocomplete | Confirm `~/.claude/skills/pcap-forensics/skill.md` exists; restart Claude Code |
