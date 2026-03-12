# Test Plan: PCAP Forensic Engine Skill

## Test Environment

- Claude Code installed and running
- tshark installed (`tshark --version` returns successfully)
- Skill installed: `~/.claude/skills/pcap-forensics/skill.md` and `pcap_extractor.py` present
- Sample pcap files from `nw-forensics/agentic-pcap-forensic-engine/tests/sample_pcaps/`

---

## T01 — Installation Verification

**Objective**: Confirm skill is discoverable in Claude Code.

**Steps**:
1. Open Claude Code in any directory
2. Type `/` and observe the autocomplete list

**Pass**: `pcap-forensics` appears in the list with its description.
**Fail**: Skill does not appear — check that `~/.claude/skills/pcap-forensics/skill.md` exists.

---

## T02 — Pre-flight: Missing File

**Objective**: Confirm graceful failure when file doesn't exist.

**Invocation**: `/pcap-forensics /tmp/nonexistent.pcap`

**Pass**: Clear error message "File not found: /tmp/nonexistent.pcap". No traceback.
**Fail**: Python traceback, or skill hangs.

---

## T03 — Pre-flight: tshark Missing

**Objective**: Confirm skill provides actionable install instructions when tshark is absent.

**Setup**: Temporarily rename tshark (`sudo mv /usr/local/bin/tshark /usr/local/bin/tshark.bak`)

**Invocation**: `/pcap-forensics /any/file.pcap`

**Pass**: Error message with OS-specific install instructions. Restore tshark after test.
**Fail**: Cryptic error or Python traceback.

---

## T04 — Single Capture: ARP Spoofing

**Objective**: Confirm CRITICAL ARP spoofing detection.

**Input**: `nw-forensics/agentic-pcap-forensic-engine/tests/sample_pcaps/arp_spoofing.pcap`

**Invocation**: `/pcap-forensics <path>/arp_spoofing.pcap`

**Pass criteria**:
- Report contains CRITICAL severity ARP finding
- IP-MAC conflict detected with specific MAC addresses named
- Frame references provided
- Remediation includes `ip arp inspection vlan` command
- `arp_spoofing_semantic.json` written to same directory as input

**Fail**: ARP conflict not detected, or no CRITICAL severity assigned.

---

## T05 — Single Capture: TCP Retransmissions

**Objective**: Confirm TCP retransmission detection and classification.

**Input**: `tests/sample_pcaps/tcp_retransmissions.pcap`

**Pass criteria**:
- Retransmission count matches tshark's own count (verify with `tshark -r file.pcap -q -z io,stat,0,"tcp.analysis.retransmission"`)
- Stream(s) with issues listed with src/dst IPs and ports
- Severity appropriate (MEDIUM or HIGH depending on rate)
- Remediation includes `ethtool`, `netstat -s`, `tc` commands

---

## T06 — Single Capture: DNS NXDOMAIN / DGA

**Objective**: Confirm DNS DGA malware beaconing detection.

**Input**: `tests/sample_pcaps/dns_nxdomain.pcap`

**Pass criteria**:
- NXDOMAIN domains listed
- If domain names appear random/DGA-pattern, CRITICAL severity assigned
- DNS server IP identified
- Remediation includes isolation and DNS block commands

---

## T07 — Single Capture: Healthy Traffic

**Objective**: Confirm skill correctly identifies healthy captures with no false positives.

**Input**: `tests/sample_pcaps/healthy_large.pcap`

**Pass criteria**:
- Executive Summary states capture appears healthy
- Anomaly Table shows only INFO rows or "No anomalies detected"
- No CRITICAL/HIGH/MEDIUM severity findings
- Report does not fabricate problems

---

## T08 — Single Capture: Kitchen Sink (Multi-protocol)

**Objective**: Confirm cross-protocol correlation works on a complex capture with multiple simultaneous anomalies.

**Input**: `tests/sample_pcaps/kitchen_sink.pcap`

**Pass criteria**:
- Multiple severity levels present in Anomaly Table
- Cross-protocol findings identified (e.g., ARP unanswered + ICMP Host Unreachable correlated)
- Root Cause Analysis section present for HIGH/CRITICAL findings
- No fabricated frame numbers (verify at least 2 frame numbers against tshark output)

**Verification**: `tshark -r kitchen_sink.pcap -Y "arp" -T fields -e frame.number | head -5`

---

## T09 — Temporal Compare

**Objective**: Confirm compare mode identifies what changed between two captures.

**Input**:
- A: `tests/sample_pcaps/compare/healthy_stable_a.pcap`
- B: `tests/sample_pcaps/compare/tcp_degradation_b.pcap`

**Invocation**: `/pcap-forensics <path_a> --compare <path_b>`

**Pass criteria**:
- Report shows Change Summary Table with both captures' metrics
- TCP degradation identified as REGRESSION in Capture B
- Two semantic JSON files written to disk
- Report does not conflate A and B (check that metrics are assigned to the right capture)

---

## T10 — Endpoint Correlation Mode

**Objective**: Confirm endpoint correlation mode correctly attributes findings to source vs. destination direction.

**Input**:
- Source: `tests/sample_pcaps/compare/arp_spoofing_start_a.pcap`
- Dest: `tests/sample_pcaps/compare/arp_spoofing_start_b.pcap`

**Invocation**: `/pcap-forensics <source> --compare <dest> --mode endpoint-correlation`

**Pass criteria**:
- Report includes Path Health Table
- Report includes Verdict section with confidence level
- Source and destination are not swapped in the analysis

---

## T11 — Semantic JSON Artifact

**Objective**: Confirm the semantic JSON is valid, well-formed, and machine-readable.

**Steps**:
1. Run any single-capture invocation
2. Find the `*_semantic.json` file
3. Validate: `python3 -c "import json; json.load(open('file_semantic.json'))"`
4. Check structure contains `capture_summary` key with `total_packets`, `duration_seconds`

**Pass**: JSON is valid and structurally correct.
**Fail**: Invalid JSON, missing keys, or file not written.

---

## Pass/Fail Summary Table

| Test | Scenario | Expected Severity | Status |
|---|---|---|---|
| T01 | Installation | — | Pending |
| T02 | Missing file | Error message | Pending |
| T03 | tshark missing | Install instructions | Pending |
| T04 | ARP spoofing | CRITICAL | Pending |
| T05 | TCP retransmissions | MEDIUM/HIGH | Pending |
| T06 | DNS NXDOMAIN / DGA | CRITICAL | Pending |
| T07 | Healthy traffic | INFO only | Pending |
| T08 | Kitchen sink | Multiple | Pending |
| T09 | Temporal compare | REGRESSION | Pending |
| T10 | Endpoint correlation | Verdict present | Pending |
| T11 | Semantic JSON | Valid JSON | Pending |
