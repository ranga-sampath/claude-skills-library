# How to Use: nftables-explain Skill

## Installation

### 1. Clone the skills library

```bash
git clone https://github.com/ranga-sampath/claude-skills-library
cd claude-skills-library/nftables-explain
```

### 2. Install the skill globally in Claude Code

Claude Code discovers skills from `~/.claude/skills/` — your global skills directory. Copying the files there registers the skill for every Claude Code session on this machine, regardless of which project directory you are working in.

```bash
mkdir -p ~/.claude/skills/nftables-explain
cp .claude/skills/nftables-explain/skill.md ~/.claude/skills/nftables-explain/
cp .claude/skills/nftables-explain/nftables_parser.py ~/.claude/skills/nftables-explain/
```

### 3. Verify the skill is available

Open Claude Code and type `/` — `nftables-explain` should appear in the autocomplete list.

---

## Capturing the Snapshot

```bash
# Capture the full ruleset in JSON format
nft --json list ruleset > current.json

# Capture and pretty-print (larger file, same content)
nft --json list ruleset | python3 -m json.tool > current-pretty.json
```

The file must be the output of `nft --json list ruleset`. Plain-text `nft list ruleset` output is not supported.

---

## Usage

```
/nftables-explain <snapshot.json>
```

### Examples

```
# Analyse the current host's nftables ruleset
/nftables-explain /tmp/current.json

# Analyse a snapshot captured from a remote host
/nftables-explain ~/snapshots/prod-db-01-20260315.json

# Analyse a specific fixture from the examples directory
/nftables-explain examples/fx-03-inet-drop-policy.json
```

Claude will:
1. Check the file exists and the parser script is installed
2. Run `nftables_parser.py` to produce structured JSON
3. Analyse the JSON and return the full explanation inline

---

## What the Report Covers

| Section | Content |
|---|---|
| **Address Families Covered** | Which families (ip, ip6, inet, etc.) are present |
| **Default Policies** | Hook chain → policy table; drop policies highlighted |
| **Rules** | Chain-by-chain plain-English explanation |
| **Sets** | Named sets and maps, their contents, how they are used |
| **Security Posture Summary** | 2-4 sentence verdict |
| **Notable Findings** | Anything that warrants attention |

---

## Understanding the Output

### Address Families

| Family | What it governs |
|---|---|
| `ip` | IPv4 traffic only |
| `ip6` | IPv6 traffic only |
| `inet` | Both IPv4 and IPv6 in a single table |
| `arp` | ARP packets |
| `bridge` | Bridged traffic (Docker default network, VMs) |
| `netdev` | Per-device ingress/egress hooks |

An `inet` table with a drop input policy governs **both** IPv4 and IPv6 inbound traffic. A separate `ip` table alongside an `inet` table means IPv4 traffic passes through both.

### Named Sets

Sets (`@setname`) are referenced in rules by name. The report explains what each set contains (IP addresses, CIDR prefixes, ports, etc.) and which rules reference it. An unresolved set reference (`@setname` appears in a rule but has no definition in the ruleset) is flagged as a notable finding.

### Conntrack Directives

| Directive | Meaning |
|---|---|
| `ct state new,established,related` | Connection tracking state |
| `ct direction original` | Packet travelling in the initiator's direction |
| `ct direction reply` | Packet travelling in the responder's direction |
| `ct mark <value>` | Connection marked by a previous rule or policy map |
| `ct zone <id>` | Connection in a specific isolation zone |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `Error: File not found` | Check the path; use an absolute path |
| `Error: nftables_parser.py not found` | Re-run the install step |
| `Error: python3 not on PATH` | Install Python 3.10+: `sudo apt install python3` |
| `Failed to parse as nft JSON` | Ensure the file is from `nft --json list ruleset`, not `nft list ruleset` |
| `/nftables-explain` not in autocomplete | Confirm `~/.claude/skills/nftables-explain/skill.md` exists; restart Claude Code |
| Empty ruleset | `nft --json list ruleset` returns `{"nftables":[{"metainfo":{...}}]}` for an empty system — the report will confirm no tables or rules are present |

---

## Using the Parser Standalone

`nftables_parser.py` can also be used independently of the Claude skill:

```bash
# Parse to JSON (stdout)
python3 nftables_parser.py snapshot.json

# Pretty-print with 4-space indentation
python3 nftables_parser.py snapshot.json --indent 4

# Pipe into jq
python3 nftables_parser.py snapshot.json | jq '.diagnostics.drop_policy_chains'
python3 nftables_parser.py snapshot.json | jq '[.tables | to_entries[] | {table: .key, sets: (.value.sets | keys)}]'
```

The JSON output schema is documented in `docs/overview.md`.
