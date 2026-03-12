# Claude Skills & Agent Toolkit 🤖

A curated collection of production-grade skills, MCP servers, and agentic workflows designed for the Anthropic Claude ecosystem. Each skill in this library is built with a "Test-First" philosophy, ensuring reliability in real-world deployments.

## 🏗️ Architecture Philosophy
All skills in this repository follow a standardized structure to ensure interoperability and ease of integration:
* **Standardized Documentation:** Every skill includes an Overview, How-To, and Technical Specification.
* **Rigorous Testing:** Full test suites and verifiable Test Reports are included for every module.

---

## 🛠️ Available Skills

| Skill Name | Description | Type | Status | Latest Report |
| :--- | :--- | :--- | :--- | :--- |
| **Image & Audio Extraction** | Multimodal extraction suite for processing media assets within Claude. | Code-Gen | ![Verified](https://img.shields.io/badge/Status-Verified-success?style=flat-square) | [View Report](./extract-data-from-image-or-audio/tests/TEST_REPORT.md) |
| **PCAP Forensic Analysis** | Operational skill: agentic network forensics on `.pcap` captures via tshark + Claude. Detects ARP spoofing, PMTUD black holes, TCP retransmission storms, DNS malware beaconing, and more. | Operational | ![In Development](https://img.shields.io/badge/Status-In%20Development-yellow?style=flat-square) | [View Report](./pcap-forensics/tests/TEST_REPORT.md) |

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
|
└── README.md                           # Project Index (You are here)
