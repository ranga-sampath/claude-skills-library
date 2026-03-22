# Test Plan: iptables-explain Skill

## Test Fixtures

All fixtures are in `examples/` and `tests/` (parser unit tests use fixtures from the netfilter-inspector source project).

| Fixture | Description | Key Features to Verify |
|---|---|---|
| `examples/ubuntu2404-docker-fail2ban.txt` | Ubuntu 24.04, Docker 27+, fail2ban active | iptables-nft framework, Docker chain topology, active ban listed |

Additional fixtures available in the `netfilter-inspector` source project:

| Fixture | Key Features |
|---|---|
| `ubuntu2404-cis-hardened.txt` | INPUT DROP, FORWARD DROP, minimal 4-rule set |
| `ubuntu2404-docker.txt` | Docker 27+ chains only, no fail2ban |
| `ubuntu2404-docker-fail2ban-wireguard.txt` | Docker + fail2ban + WireGuard (17 chains) |
| `ubuntu2404-log-mark-snat.txt` | Logging rules, MARK target, SNAT |
| `ubuntu2404-clean.txt` | Baseline — security table only, no filter table |
| `ubuntu2404-clean-ip6.txt` | IPv6 ruleset |
| `ubuntu2404-docker-counters.txt` | Counters on chains and rules |

---

## Test Scenarios

### T1 — Basic parse and report (sample fixture)

```
/iptables-explain examples/ubuntu2404-docker-fail2ban.txt
```

**Expected:**
- Framework: `iptables-nft`
- Default policy: INPUT ACCEPT, FORWARD DROP
- fail2ban: `f2b-sshd` chain identified, `1.2.3.4/32` active ban listed
- Docker: DOCKER-FORWARD / DOCKER-CT / DOCKER-BRIDGE topology explained
- Notable findings: INPUT ACCEPT default, port 8080 publicly exposed, DOCKER-USER empty

### T2 — CIS-hardened minimal ruleset

```
/iptables-explain <path-to>/ubuntu2404-cis-hardened.txt
```

**Expected:**
- INPUT DROP and FORWARD DROP called out prominently
- 4 INPUT rules explained: loopback, established, ICMP type 8, SSH
- No custom chains, no nat table
- Security posture: default-deny inbound

### T3 — IPv6 ruleset

```
/iptables-explain <path-to>/ubuntu2404-clean-ip6.txt
```

**Expected:**
- family: ipv6 noted
- ip6tables-save format noted

### T4 — Error: missing file

```
/iptables-explain /tmp/does-not-exist.txt
```

**Expected:** `Error: File not found: /tmp/does-not-exist.txt`

### T5 — Error: missing parser

Remove `~/.claude/skills/iptables-explain/iptables_parser.py` temporarily and invoke.

**Expected:** Error message with install instructions.

### T6 — No-op (all-ACCEPT, no rules)

Use `ubuntu2404-clean.txt` (security table only, no filter table).

**Expected:** Explanation notes only the security table is present; no filter/nat rules.

---

## Parser Unit Tests

The `iptables_parser.py` has a full unit test suite in the `netfilter-inspector` source project:

```bash
cd <netfilter-inspector>/iptables-parser
python3 -m pytest tests/ -q
# Expected: 108 passed
```

Tests cover: all table types, policy parsing, rule parsing (all match extensions), counter parsing, IPv6, custom chains, diagnostics, parse warnings.

---

## Ground Truth Verification

Parser output is verified against pre-computed reference snapshots:

```bash
python3 iptables_parser.py ubuntu2404-docker-fail2ban.txt > computed.json
diff <(python3 -c "import json,sys; d=json.load(open('computed.json')); print(json.dumps({k:v for k,v in d.items() if k!='parsed_at'}, sort_keys=True))") \
     <(python3 -c "import json,sys; d=json.load(open('ubuntu2404-docker-fail2ban_snapshot.json')); print(json.dumps({k:v for k,v in d.items() if k!='parsed_at'}, sort_keys=True))")
# Expected: no diff
```

Reference snapshots: `*_snapshot.json` files alongside each fixture in the netfilter-inspector source project.
