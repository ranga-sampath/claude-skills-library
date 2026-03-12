# PCAP Forensic Engine — Operational Skill

## Description

Performs agentic network forensic analysis on `.pcap`, `.pcapng`, or `.cap` packet capture files. Extracts protocol metadata via tshark, builds a compact Semantic JSON, then applies expert-level root cause analysis natively using Claude.

Supports three modes:
- **Single capture** — forensic analysis of one capture file
- **Temporal compare** — baseline vs. current capture (what changed?)
- **Endpoint correlation** — source vs. destination capture (where are packets dropped?)

## When to Use

Invoke when the user:
- Provides a `.pcap`, `.pcapng`, or `.cap` file path and asks for analysis
- Uses `/pcap-forensics` explicitly
- Asks for root cause analysis, network forensics, or packet-level troubleshooting
- Wants to compare two captures or correlate source/destination captures

## Invocation

```
/pcap-forensics <path/to/capture.pcap>
/pcap-forensics <capture_a.pcap> --compare <capture_b.pcap>
/pcap-forensics <source.pcap> --compare <dest.pcap> --mode endpoint-correlation
```

---

## Execution Steps

### Step 1 — Parse Arguments

Extract from the invocation arguments:
- `PCAP_A`: required — the primary `.pcap` file path
- `PCAP_B`: optional — `--compare <path>` second capture
- `MODE`: optional — `--mode temporal` (default) or `--mode endpoint-correlation`

If no file path is provided, respond with:
```
Usage: /pcap-forensics <capture.pcap> [--compare <capture2.pcap>] [--mode temporal|endpoint-correlation]

Example: /pcap-forensics ~/captures/incident.pcap
```

---

### Step 2 — Pre-flight Checks

Run these checks using Bash before proceeding. Fail fast with a clear message.

**Check 1: File exists**
```bash
test -f "<PCAP_A>" && echo "OK" || echo "NOT_FOUND"
```
If NOT_FOUND: `Error: File not found: <PCAP_A>`

**Check 2: tshark is installed**
```bash
which tshark && tshark --version | head -1
```
If missing, print:
```
Error: tshark is not installed or not on PATH.

Install Wireshark/tshark:
  macOS:   brew install wireshark
  Ubuntu:  sudo apt install tshark
  Windows: https://www.wireshark.org/download.html
```

**Check 3: Extractor script exists**

Look for `pcap_extractor.py` in this order:
```bash
ls ~/.claude/skills/pcap-forensics/pcap_extractor.py 2>/dev/null && echo "FOUND" || echo "NOT_FOUND"
```
If NOT_FOUND:
```
Error: pcap_extractor.py not found at ~/.claude/skills/pcap-forensics/

Re-install the skill:
  cp <repo>/pcap-analysis/.claude/skills/pcap-forensics/pcap_extractor.py ~/.claude/skills/pcap-forensics/
```

---

### Step 3 — Run Extraction

**Single capture:**
```bash
python3 ~/.claude/skills/pcap-forensics/pcap_extractor.py "<PCAP_A>"
```

**Compare mode:**
```bash
python3 ~/.claude/skills/pcap-forensics/pcap_extractor.py "<PCAP_A>" --compare "<PCAP_B>" --mode <MODE>
```

Parse stdout to extract the semantic JSON path(s):
- Single: line containing `SEMANTIC_JSON=<path>`
- Compare: lines containing `SEMANTIC_JSON_A=<path>` and `SEMANTIC_JSON_B=<path>`, and `COMPARE_MODE=<mode>`

If the script exits non-zero, display stderr to the user and stop.

---

### Step 4 — Read Semantic JSON

Read the semantic JSON file(s) written by the extractor. These are compact aggregations of packet metadata — not raw packet data.

For compare mode, read both JSON files.

---

### Step 5 — Forensic Analysis

Apply the analysis framework below to the semantic JSON. You ARE the forensic analyst. Every claim must be grounded in data present in the JSON — do not fabricate frame numbers, IPs, or statistics.

---

## Analysis Framework

### ARP Analysis

- **IP-MAC conflicts** (`duplicate_ip_alerts`): Multiple MACs claiming one IP = ARP spoofing/cache poisoning, or legitimate VRRP/HSRP failover. Check if one MAC is a known virtual MAC prefix (00:00:5e:00 for VRRP, 00:07:b4:00 for HSRP). If not, treat as CRITICAL spoofing alert.
- **Unanswered ARP requests**: Target host is down, wrong VLAN, or firewall blocking ARP at L2. If >5 unanswered for a specific IP, that host is unreachable at the data-link layer.
- **Gratuitous ARP flood**: >10 gratuitous ARPs suggests VRRP/HSRP flapping, NIC teaming failover, or an ARP announcement storm.

### ICMP Analysis

Destination Unreachable codes are critical diagnostic signals:
- **Code 0** (Network Unreachable): No route to destination network. Sending router's routing table is incomplete.
- **Code 1** (Host Unreachable): Router has a route to the network but the specific host doesn't respond to ARP — host is down or has wrong subnet mask.
- **Code 3** (Port Unreachable): UDP port is closed. Application is not listening. Common with DNS (53), SNMP (161), syslog (514) misconfig.
- **Code 4** (Fragmentation Needed, DF Set): Path MTU constraint. If these are being suppressed (PMTUD black hole), large transfers stall silently while pings continue working.
- **Code 9/10** (Admin Prohibited): Firewall actively rejecting with ICMP (not silently dropping). Identifies the filtering device's IP.
- **Code 13** (Communication Admin Prohibited): Packet filter rule match.

Field semantics in `unreachable_details`:
- `src`: router/device that sent the ICMP error
- `dst`: original sender that receives the error notification
- `unreachable_dst`: the actual host that could not be reached (from embedded inner IP header)
- Do NOT confuse `dst` (notification recipient) with the unreachable target.

TTL Exceeded (`ttl_exceeded_sources`):
- `src`: router that dropped the packet; `dst`: original sender; `original_dst`: destination packet was trying to reach
- Multiple different `src` routers for same `original_dst` = multi-hop routing loop
- Single `src` sending repeated TTL exceeded for same `original_dst` = bouncing at that hop
- All different `original_dst` values = normal traceroute probing, not a loop

ICMP Redirect (`redirect_details`):
- `src`: router sending redirect; `dst`: host being redirected; `gateway`: new gateway to use; `redirect_for`: destination the redirect applies to
- Correlate whether `gateway` is a known router or unexpected host (redirect-based MITM indicator)

Unmatched echo requests:
- >50% unmatched = serious reachability problem
- <10% unmatched = transient loss

### TCP Analysis

- **Connection success rate < 90%**: Server overload, firewall blocking, or service down. Check if RSTs come from server IP (port closed/app crash) or a different IP (forged RSTs from firewall/IPS/ISP).
- **Retransmission patterns**:
  - Scattered across many streams = network-wide packet loss (congested link, bad cable/optic, duplex mismatch, CRC errors)
  - Concentrated in 1-2 streams = endpoint-specific issue (slow application, kernel buffer exhaustion, CPU saturation)
  - Exponential backoff deltas (200ms→400ms→800ms) = RTO-based retransmission, severe sustained loss
- **Duplicate ACKs**: 3+ duplicate ACKs trigger Fast Retransmit (RFC 5681). High dup ACK count relative to retransmissions = fast retransmit working but loss sustained. Low dup ACK with high retransmissions = loss so severe ACKs don't get through.
- **Zero-window events**: Receiver's TCP buffer full — application not reading data fast enough. This is an APPLICATION bottleneck, not a network issue. Receiving application needs profiling (slow DB queries, GC pauses, thread pool exhaustion).
- **Out-of-order packets**: Correlated with specific path = ECMP/LAG load balancing reordering. Random across streams = network congestion.
- **RST origin**: RSTs from server endpoint IP = port closed or app crashed. RSTs from IP that is NEITHER client NOR server = inline device (firewall, IDS/IPS, ISP middlebox) forging RSTs.
- **ACK RTT distribution**: If p95/median ratio > 10, suspect bufferbloat in intermediate device.

### DNS Analysis

- **NXDOMAIN patterns**:
  - Random-looking names (e.g., `xk3f9a2.example.com`) = DGA malware trying to reach C2 servers. **CRITICAL security finding.**
  - Misspelled real domains = typo or misconfigured service discovery
  - Sequential subdomains = zone enumeration/reconnaissance
- **SERVFAIL domains**: DNS server cannot resolve — authoritative server down, DNSSEC validation failed, or zone misconfigured. Critical if it affects production hostnames.
- **Query type distribution**:
  - TXT queries >20% of total = potential DNS tunneling for data exfiltration. **CRITICAL security finding.**
  - High PTR ratio = reverse DNS lookups from scanner or IDS
  - ANY queries = DNS amplification attack preparation
- **Unanswered queries >5%**: DNS server overloaded, unreachable, or rate-limiting.
- **Latency outliers >200ms**: Query traversing multiple forwarders or authoritative server distant/overloaded.
- **Truncated responses**: Response too large for UDP. Client should retry over TCP. High truncation count = check EDNS0 buffer size.
- **Unexpected DNS servers**: IPs not in org's designated resolvers = DNS hijacking, DHCP-injected rogue DNS, or misconfigured `/etc/resolv.conf`.

### Cross-Protocol Correlation

Apply these multi-protocol patterns when evidence from multiple sections points to the same root cause:

- **ARP unanswered for IP X + ICMP Host Unreachable (Code 1) for IP X** = host X confirmed down or disconnected from L2 segment.
- **ICMP Fragmentation Needed (Code 4) + TCP retransmissions on streams with large tcp.len** = PMTUD black hole. Path has smaller MTU than endpoints expect; DF bit prevents fragmentation so large segments silently drop.
- **DNS NXDOMAIN for domain Y + TCP SYN to IP with RST** = application using stale DNS cache after domain removed.
- **High DNS latency to server IP Z + TCP retransmissions to same IP Z** = DNS server itself has connectivity or performance issues.
- **ICMP TTL Exceeded from same router + high TCP retransmissions** = routing loop causing packet loss as packets exhaust TTL bouncing between routers.

---

## Output Format — Single Capture

Produce a forensic report in Markdown with exactly these sections:

### Executive Summary
2-4 sentences stating the most critical finding and its likely root cause. Be specific — name the IPs, ports, and protocols. Prioritize: security issues > connectivity failures > performance degradation > informational. If no issues: state the capture appears healthy with specific evidence.

### Anomaly Table
Markdown table: `Severity | Protocol | Issue | Detail | Frame(s)`

Severity levels:
- **CRITICAL**: Active security threat (ARP spoofing, DGA malware, DNS tunneling)
- **HIGH**: Service-impacting (host unreachable, connection failures, zero-window stalls)
- **MEDIUM**: Performance degradation (retransmissions, elevated latency)
- **LOW**: Worth monitoring (occasional retransmissions, minor latency spikes)
- **INFO**: Notable but benign

Use specific frame numbers, IPs, and port numbers from the data.
If no anomalies: `INFO | — | No anomalies detected | All protocols operating within normal parameters | —`

### Root Cause Analysis
For each HIGH or CRITICAL finding: 2-3 sentence technical explanation covering what protocol behavior indicates the problem, what the expected behavior is (cite the RFC if relevant), and how it correlates with other findings. Skip entirely if no HIGH/CRITICAL findings.

### Remediation
Specific remediation for each finding with exact CLI commands. Specify which host/device each command runs on.

**Sequencing rule:** When remediation steps have dependencies or must be applied in a specific order to avoid an outage or to be effective, present them as a numbered sequence with each step labelled. Do not list related steps as independent bullets — a reader must be able to apply them top-to-bottom without needing to infer the order. If a step must complete before the next begins (e.g. enable DHCP snooping before DAI, flush a stale entry before adding a static one), make that dependency explicit in the step label or a one-line note.

Example structure for sequenced remediation:
```
**Step 1 — <action> (on <device>):** <why first>
<commands>

**Step 2 — <action> (on <device>):** <depends on step 1 / run after>
<commands>

**Step 3 — Verify:**
<commands>
```

Expected specificity:
- ARP spoofing: flush poisoned entry before pinning static binding; trust uplink ports before enabling DAI; add ARP ACLs for static-IP hosts before enabling DAI; verify with `show ip arp inspection statistics vlan <id>`
- PMTUD black hole: `ping -M do -s 1400 <dst>` to find MTU; `ip link set dev eth0 mtu <value>` or `iptables -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu`
- TCP retransmissions: `ethtool eth0 | grep -i duplex`; `netstat -s | grep retrans`; `tc -s qdisc show dev eth0`
- Zero-window: `ss -tnp dst <ip>` to identify process; check application logs for slow queries or GC pauses
- DNS SERVFAIL: `dig +trace example.com @<server>`; `named-checkzone example.com /etc/bind/zones/example.com.zone`; `systemctl restart named`

If no issues: "No action required — capture indicates healthy network operation."

---

## Output Format — Temporal Compare (`--mode temporal`)

### Executive Summary
2-4 sentences stating overall trajectory (improved/degraded/stable) with the most significant change.

### Change Summary Table
`Protocol | Metric | Capture A | Capture B | Delta | Assessment`
Assessment: REGRESSION, IMPROVEMENT, STABLE, NEW ISSUE, RESOLVED

### New Issues (Capture B only)
Issues in B not in A. Same severity table format as single capture.

### Resolved Issues (Capture A only)
Issues in A absent in B.

### Regressions
For each metric that worsened significantly: 2-3 sentence technical explanation. Skip if no regressions.

### Remediation
CLI commands for each new issue or regression.

**Rules**: Compare RATES and RATIOS, not raw counts. Use `avg_packets_per_second` and `duration_seconds` to normalize. Change <10% = STABLE. 10-50% = noteworthy. >50% = significant. >200% = critical.

---

## Output Format — Endpoint Correlation (`--mode endpoint-correlation`)

Capture A = SOURCE endpoint (sender). Capture B = DESTINATION endpoint (receiver).

### Executive Summary
2-4 sentences: are packets delivered, dropped, or delayed? Name specific IPs, drop rates, RTT figures.

### Path Health Table
`Protocol | Metric | Source (A) | Dest (B) | Assessment`
Assessment: DELIVERED, PARTIAL DROP, FULL DROP, DELAYED, ASYMMETRIC, CLEAN

### Flows Dropped in Transit
Flows visible at source but absent/incomplete at destination.
`Protocol | Source IP | Dest IP | Port | Source Packets | Dest Packets | Est. Drop Rate`

### Delivery Confirmed
Flows visible at both with consistent packet counts.

### One-Way vs Round-Trip Analysis
RTT at source (full round-trip) vs latency at destination (one-way A→B). Identify which direction introduces delay.

### Verdict
One of: CLEAN PATH | PARTIAL DROP | FULL DROP | DEGRADED (DELAYED) | ASYMMETRIC ROUTING
Followed by 2-3 sentence root cause explanation citing specific metrics. Include confidence level: HIGH / MEDIUM / LOW.

### Recommended Actions
CLI commands to investigate further. If path is CLEAN: "No action required."

**Rules**: A flow absent from B is significant only if it appears in A with ≥3 packets. Single-packet flows may be timing artifacts.

---

## General Rules (All Modes)

- Every claim must be supported by data in the JSON. Do not fabricate frame numbers, IPs, or statistics.
- Do not speculate beyond what the data supports. When data is insufficient, state what additional capture would be needed.
- Correlate across protocols — the most valuable insights come from connecting symptoms across layers.

## Step 6 — Save Report to Disk

After generating the forensic report, write it to a `.md` file alongside the input pcap.

**Naming convention:**
- Single capture: `<pcap_directory>/<capture_stem>_forensic_report.md`
- Compare (temporal or endpoint correlation): `<pcap_a_directory>/<capture_a_stem>_vs_<capture_b_stem>_report.md`

Where `<capture_stem>` is the filename without extension (e.g. `arp_spoofing.pcap` → `arp_spoofing_forensic_report.md`).

Use the Write tool to save the full report markdown to that path.

After saving, tell the user:
- The report path
- The semantic JSON path(s) (from the extractor stdout)
