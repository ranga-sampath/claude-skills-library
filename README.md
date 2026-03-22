# Claude Skills & Agent Toolkit 🤖

A curated collection of production-grade skills, MCP servers, and agentic workflows designed for the Anthropic Claude ecosystem.

## 🏗️ Structure Philosophy
All skills in this repository follow a standardized structure:
* **Standardized Documentation:** Every skill includes an Overview, How-To, and Technical Specification.
* **Examples:** Sample inputs and reference output reports are included so you can verify behaviour before deploying.

---

## 🛠️ Available Skills

| Skill Name | Description | Type | Status |
| :--- | :--- | :--- | :--- |
| **Image & Audio Extraction** | Multimodal extraction suite for processing media assets within Claude. | Code-Gen | ![Verified](https://img.shields.io/badge/Status-Verified-success?style=flat-square) |
| **PCAP Forensic Analysis** | Operational skill: agentic network forensics on `.pcap` captures via tshark + Claude. Detects ARP spoofing, PMTUD black holes, TCP retransmission storms, DNS malware beaconing, and more. | Operational | ![Verified](https://img.shields.io/badge/Status-Verified-success?style=flat-square) |
| **iptables-explain** | Plain-English security analysis of an `iptables-save` snapshot — policies, rules, custom chains (fail2ban, Docker), and overall posture. | Operational | ![Verified](https://img.shields.io/badge/Status-Verified-success?style=flat-square) |
| **iptables-diff-explain** | Compares two `iptables-save` snapshots and explains what changed, whether it tightens or loosens posture, and what to verify. | Operational | ![Verified](https://img.shields.io/badge/Status-Verified-success?style=flat-square) |
| **nftables-explain** | Plain-English security analysis of an `nft --json list ruleset` snapshot — address families, policies, rules, named sets, and overall posture. | Operational | ![Verified](https://img.shields.io/badge/Status-Verified-success?style=flat-square) |
| **nftables-diff-explain** | Compares two nftables JSON snapshots and explains what changed, whether it tightens or loosens posture, and what to verify. | Operational | ![Verified](https://img.shields.io/badge/Status-Verified-success?style=flat-square) |

---

## 📂 Repository Structure
```text
.
├── /extract-data-from-image-or-audio   # Code-gen skill: multimodal extraction
│   ├── .claude/skills/                 # Skill definition
│   ├── /templates                      # Generated code templates
│   ├── /tests                          # Test suite & report
│   └── /docs                           # Skill-specific documentation
│
├── /pcap-forensics                      # Operational skill: PCAP forensics
│   ├── .claude/skills/pcap-forensics/  # Skill definition + extractor script
│   ├── /examples                       # Sample forensic report
│   ├── /tests                          # Test report
│   └── /docs                           # Overview, how-to, test plan
│
├── /iptables-explain                    # Operational skill: iptables ruleset analysis
│   ├── .claude/skills/iptables-explain/ # skill.md + iptables_parser.py
│   ├── /examples                       # Sample fixture and explain report
│   └── /docs                           # Overview, how-to, test plan
│
├── /iptables-diff-explain               # Operational skill: iptables change analysis
│   ├── .claude/skills/iptables-diff-explain/ # skill.md + parser + differ
│   ├── /examples                       # Sample fixtures and diff report
│   └── /docs                           # Overview, how-to, test plan
│
├── /nftables-explain                    # Operational skill: nftables ruleset analysis
│   ├── .claude/skills/nftables-explain/ # skill.md + nftables_parser.py
│   ├── /examples                       # Sample fixture and explain report
│   └── /docs                           # Overview, how-to, test plan
│
├── /nftables-diff-explain               # Operational skill: nftables change analysis
│   ├── .claude/skills/nftables-diff-explain/ # skill.md + parser + differ
│   ├── /examples                       # Sample fixtures and diff report
│   └── /docs                           # Overview, how-to, test plan
|
└── README.md                           # Project Index (You are here)
