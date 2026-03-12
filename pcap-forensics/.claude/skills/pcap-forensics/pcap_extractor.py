#!/usr/bin/env python3
"""PCAP Extractor — Stages 1-3 of the PCAP Forensic Engine.

Extracts network metadata via tshark and builds a compact Semantic JSON.
AI-powered forensic analysis is performed by the Claude Code skill (SKILL.md)
natively — no external API call required.

Usage:
    python3 pcap_extractor.py <capture.pcap>
    python3 pcap_extractor.py <capture_a.pcap> --compare <capture_b.pcap>
    python3 pcap_extractor.py <source.pcap> --compare <dest.pcap> --mode endpoint-correlation
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# TCP flag bitmasks
SYN = 0x0002
ACK = 0x0010
RST = 0x0004
FIN = 0x0001

# DNS RCODE names
RCODE_NAMES = {
    0: "NOERROR",
    1: "FORMERR",
    2: "SERVFAIL",
    3: "NXDOMAIN",
    4: "NOTIMP",
    5: "REFUSED",
}

# ICMP type names for type_distribution
ICMP_TYPE_NAMES = {
    0: "echo_reply", 3: "dest_unreachable", 5: "redirect",
    8: "echo_request", 11: "time_exceeded",
}

# ICMP Destination Unreachable code meanings
ICMP_UNREACH_CODES = {
    0: "Network Unreachable", 1: "Host Unreachable",
    3: "Port Unreachable", 4: "Fragmentation Needed/DF Set",
    9: "Net Admin Prohibited", 10: "Host Admin Prohibited",
    13: "Communication Admin Prohibited",
}

# DNS query type names
DNS_QTYPE_NAMES = {
    1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR",
    15: "MX", 16: "TXT", 28: "AAAA", 33: "SRV", 255: "ANY",
}


# ---------------------------------------------------------------------------
# Helpers — parsing tshark's tab-separated output
# ---------------------------------------------------------------------------

def _parse_optional_int(value: str) -> int | None:
    """Parse a tshark field to int, returning None for empty/missing fields.
    Takes the first value if the field is comma-separated (multi-value)."""
    value = value.strip()
    if not value:
        return None
    return int(value.split(",")[0], 0)


def _parse_optional_float(value: str) -> float | None:
    """Parse a tshark field to float, returning None for empty/missing fields."""
    value = value.strip()
    if not value:
        return None
    return float(value.split(",")[0])


def _parse_str(value: str) -> str:
    """Parse a tshark string field. Takes first value if comma-separated."""
    return value.split(",")[0].strip() if value else ""


def _parse_bool_present(value: str) -> bool:
    """Parse a tshark 'present when true' field to bool."""
    return bool(value.strip())


def _parse_bool_flag(value: str) -> bool:
    """Parse a tshark boolean flag field (True/False or 1/0) to bool."""
    v = value.strip().split(",")[0]
    return v in ("1", "True")


# ---------------------------------------------------------------------------
# Stage 1 — Input Validation
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PCAP Extractor — extracts semantic metadata from packet captures")
    parser.add_argument("pcap", help="Path to .pcap/.pcapng/.cap file")
    parser.add_argument("--semantic-dir",
        help="Output directory for semantic JSON (default: same as input)")
    parser.add_argument("--compare", metavar="PCAP2",
        help="Second pcap for comparative analysis")
    parser.add_argument("--mode",
        choices=["temporal", "endpoint-correlation"],
        default="temporal",
        help=(
            "Comparison mode (only used with --compare). "
            "'temporal': baseline-vs-current analysis at different times. "
            "'endpoint-correlation': source-vs-destination path analysis."
        ))
    return parser.parse_args()


def validate_input(pcap_arg: str) -> Path:
    pcap_path = Path(pcap_arg)

    if not pcap_path.exists():
        print(f"Error: File not found: {pcap_path}", file=sys.stderr)
        sys.exit(1)

    if not pcap_path.is_file() or not os.access(pcap_path, os.R_OK):
        print(f"Error: File is not readable: {pcap_path}", file=sys.stderr)
        sys.exit(1)

    if pcap_path.suffix.lower() not in (".pcap", ".pcapng", ".cap"):
        print(
            f"Error: Unsupported file extension '{pcap_path.suffix}'. "
            "Expected .pcap, .pcapng, or .cap",
            file=sys.stderr,
        )
        sys.exit(1)

    if not shutil.which("tshark"):
        print("Error: tshark is not installed or not on PATH.", file=sys.stderr)
        print("  Install Wireshark/tshark:", file=sys.stderr)
        print("    macOS:   brew install wireshark", file=sys.stderr)
        print("    Ubuntu:  sudo apt install tshark", file=sys.stderr)
        print("    Windows: https://www.wireshark.org/download.html", file=sys.stderr)
        sys.exit(1)

    return pcap_path


# ---------------------------------------------------------------------------
# Stage 2 — Protocol Extraction (tshark)
# ---------------------------------------------------------------------------

def run_tshark(pcap_path: Path, fields: list[str],
               display_filter: str = "",
               extra_opts: list[str] | None = None) -> list[list[str]]:
    """Run a tshark command and return rows of tab-separated field values.
    Uses list args — never shell=True — to prevent command injection."""
    cmd = ["tshark", "-r", str(pcap_path), "-T", "fields"]
    if display_filter:
        cmd.extend(["-Y", display_filter])
    for field in fields:
        cmd.extend(["-e", field])
    cmd.extend(["-E", "separator=\t", "-E", "header=n"])
    if extra_opts:
        cmd.extend(extra_opts)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"tshark failed: {result.stderr.strip()}")

    rows = []
    for line in result.stdout.rstrip("\n").split("\n"):
        if line:
            rows.append(line.split("\t"))
    return rows


def extract_capture_summary(pcap_path: Path) -> dict:
    """Stream every packet's frame number and timestamp from tshark line by
    line. Only three values are kept in memory regardless of pcap size."""
    cmd = [
        "tshark", "-r", str(pcap_path), "-T", "fields",
        "-e", "frame.number", "-e", "frame.time_epoch",
        "-E", "separator=\t", "-E", "header=n",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)

    count = 0
    first_ts = 0.0
    last_ts = 0.0

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            ts = float(parts[1])
            if count == 0:
                first_ts = ts
            last_ts = ts
            count += 1

    proc.wait()
    if proc.returncode != 0:
        stderr_text = proc.stderr.read()
        raise RuntimeError(f"tshark failed: {stderr_text.strip()}")

    duration = last_ts - first_ts if count > 1 else 0.0
    return {
        "file": pcap_path.name,
        "total_packets": count,
        "duration_seconds": round(duration, 3),
    }


def extract_arp(pcap_path: Path) -> list[dict]:
    fields = [
        "frame.number", "frame.time_epoch", "arp.opcode",
        "arp.src.hw_mac", "arp.src.proto_ipv4", "arp.dst.proto_ipv4",
    ]
    packets = []
    for row in run_tshark(pcap_path, fields, "arp"):
        if len(row) < 6:
            continue
        packets.append({
            "frame": int(row[0]),
            "timestamp": float(row[1]),
            "opcode": _parse_optional_int(row[2]),
            "src_mac": _parse_str(row[3]),
            "src_ip": _parse_str(row[4]),
            "dst_ip": _parse_str(row[5]),
        })
    return packets


def extract_icmp(pcap_path: Path) -> list[dict]:
    fields = [
        "frame.number", "frame.time_epoch", "icmp.type", "icmp.code",
        "icmp.seq", "icmp.resp_in", "frame.time_delta",
        "ip.src", "ip.dst",
        "icmp.redir_gw",
    ]
    packets = []
    for row in run_tshark(pcap_path, fields, "icmp"):
        if len(row) < 10:
            continue
        packets.append({
            "frame": int(row[0]),
            "timestamp": float(row[1]),
            "type": _parse_optional_int(row[2]),
            "code": _parse_optional_int(row[3]),
            "seq": _parse_optional_int(row[4]),
            "resp_in": _parse_optional_int(row[5]),
            "time_delta": _parse_optional_float(row[6]),
            "src_ip": _parse_str(row[7]),
            "dst_ip": _parse_str(row[8]),
            "redir_gw": _parse_str(row[9]),
        })

    # Second pass: extract inner IP dst for ICMP error types (3, 5, 11)
    inner_dst_by_frame: dict[int, str] = {}
    for row in run_tshark(
        pcap_path,
        ["frame.number", "ip.dst"],
        "icmp.type == 3 || icmp.type == 5 || icmp.type == 11",
        extra_opts=["-E", "occurrence=l"],
    ):
        if len(row) >= 2:
            inner_dst = _parse_str(row[1])
            if inner_dst:
                inner_dst_by_frame[int(row[0])] = inner_dst

    for pkt in packets:
        if pkt.get("type") in (3, 5, 11):
            inner_dst = inner_dst_by_frame.get(pkt["frame"])
            if inner_dst and inner_dst != pkt.get("dst_ip", ""):
                pkt["inner_dst_ip"] = inner_dst

    return packets


def extract_tcp(pcap_path: Path) -> list[dict]:
    fields = [
        "frame.number", "frame.time_epoch", "tcp.stream",
        "ip.src", "tcp.srcport", "ip.dst", "tcp.dstport",
        "tcp.flags", "tcp.analysis.retransmission",
        "tcp.analysis.duplicate_ack", "tcp.analysis.out_of_order",
        "tcp.analysis.zero_window", "tcp.analysis.ack_rtt",
        "tcp.len", "tcp.window_size_value", "tcp.time_delta",
    ]
    packets = []
    for row in run_tshark(pcap_path, fields, "tcp"):
        if len(row) < 16:
            continue
        flags_str = _parse_str(row[7])
        packets.append({
            "frame": int(row[0]),
            "timestamp": float(row[1]),
            "stream": _parse_optional_int(row[2]),
            "src_ip": _parse_str(row[3]),
            "src_port": _parse_optional_int(row[4]),
            "dst_ip": _parse_str(row[5]),
            "dst_port": _parse_optional_int(row[6]),
            "flags": int(flags_str, 16) if flags_str else 0,
            "is_retransmission": _parse_bool_present(row[8]),
            "is_duplicate_ack": _parse_bool_present(row[9]),
            "is_out_of_order": _parse_bool_present(row[10]),
            "is_zero_window": _parse_bool_present(row[11]),
            "ack_rtt": _parse_optional_float(row[12]),
            "tcp_len": _parse_optional_int(row[13]),
            "window_size": _parse_optional_int(row[14]),
            "time_delta": _parse_optional_float(row[15]),
        })
    return packets


def extract_dns(pcap_path: Path) -> list[dict]:
    fields = [
        "frame.number", "frame.time_epoch", "dns.id",
        "dns.flags.response", "dns.qry.name", "dns.qry.type",
        "dns.flags.rcode", "dns.time",
        "dns.count.answers", "dns.flags.truncated", "ip.dst",
    ]
    packets = []
    for row in run_tshark(pcap_path, fields, "dns"):
        if len(row) < 11:
            continue
        resp_raw = row[3].strip().split(",")[0]
        is_response = 1 if resp_raw in ("1", "True") else 0
        packets.append({
            "frame": int(row[0]),
            "timestamp": float(row[1]),
            "dns_id": _parse_optional_int(row[2]),
            "is_response": is_response,
            "qry_name": _parse_str(row[4]),
            "qry_type": _parse_optional_int(row[5]),
            "rcode": _parse_optional_int(row[6]),
            "dns_time": _parse_optional_float(row[7]),
            "answer_count": _parse_optional_int(row[8]),
            "is_truncated": _parse_bool_flag(row[9]),
            "dst_ip": _parse_str(row[10]),
        })
    return packets


def extract_all(pcap_path: Path) -> dict:
    summary = extract_capture_summary(pcap_path)

    arp = extract_arp(pcap_path)
    print(f"      ARP:  {len(arp):,} packets", file=sys.stderr)

    icmp = extract_icmp(pcap_path)
    print(f"      ICMP: {len(icmp):,} packets", file=sys.stderr)

    tcp = extract_tcp(pcap_path)
    print(f"      TCP:  {len(tcp):,} packets", file=sys.stderr)

    dns = extract_dns(pcap_path)
    print(f"      DNS:  {len(dns):,} packets", file=sys.stderr)

    return {
        "summary": summary,
        "arp": arp,
        "icmp": icmp,
        "tcp": tcp,
        "dns": dns,
    }


# ---------------------------------------------------------------------------
# Stage 3 — Semantic Reduction
# ---------------------------------------------------------------------------

def compute_stats(values: list[float]) -> dict:
    if not values:
        return {"min": 0, "median": 0, "p95": 0, "max": 0}
    s = sorted(values)
    n = len(s)
    return {
        "min": round(s[0], 2),
        "median": round(statistics.median(s), 2),
        "p95": round(s[int(n * 0.95)], 2),
        "max": round(s[-1], 2),
    }


def reduce_arp(raw: list[dict]) -> dict:
    total_requests = 0
    total_replies = 0
    gratuitous_count = 0
    replied_ips = set()
    request_targets = defaultdict(int)
    ip_to_macs: dict[str, dict[str, int]] = defaultdict(dict)

    for pkt in raw:
        opcode = pkt.get("opcode")
        src_ip = pkt.get("src_ip", "")
        dst_ip = pkt.get("dst_ip", "")
        src_mac = pkt.get("src_mac", "")

        if src_ip and src_mac:
            if src_mac not in ip_to_macs[src_ip]:
                ip_to_macs[src_ip][src_mac] = pkt["frame"]

        if opcode == 1:
            total_requests += 1
            if src_ip and dst_ip and src_ip == dst_ip:
                gratuitous_count += 1
            else:
                request_targets[dst_ip] += 1
        elif opcode == 2:
            total_replies += 1
            replied_ips.add(src_ip)

    unanswered = [
        {"ip": ip, "count": count}
        for ip, count in sorted(request_targets.items())
        if ip not in replied_ips
    ]

    duplicate_ip_alerts = []
    for ip, mac_frames in sorted(ip_to_macs.items()):
        if len(mac_frames) > 1:
            duplicate_ip_alerts.append({
                "ip": ip,
                "macs": sorted(mac_frames.keys()),
                "sample_frames": [mac_frames[m] for m in sorted(mac_frames.keys())],
            })

    result = {
        "total_requests": total_requests,
        "total_replies": total_replies,
        "unanswered_requests": unanswered,
        "gratuitous_arp_count": gratuitous_count,
    }
    if duplicate_ip_alerts:
        result["duplicate_ip_alerts"] = duplicate_ip_alerts
    return result


def reduce_icmp(raw: list[dict]) -> dict:
    ts_map = {pkt["frame"]: pkt["timestamp"] for pkt in raw}
    reply_by_seq: dict[int, int] = {}
    for pkt in raw:
        if pkt.get("type") == 0 and pkt.get("seq") is not None:
            reply_by_seq.setdefault(pkt["seq"], pkt["frame"])

    matched = 0
    unmatched = 0
    rtt_entries = []

    for pkt in raw:
        if pkt.get("type") != 8:
            continue
        resp_frame = pkt.get("resp_in")
        if resp_frame is None:
            resp_frame = reply_by_seq.get(pkt.get("seq"))
        if resp_frame is not None and resp_frame in ts_map:
            rtt_ms = round((ts_map[resp_frame] - pkt["timestamp"]) * 1000, 2)
            rtt_entries.append((rtt_ms, pkt.get("seq"), pkt["frame"]))
            matched += 1
        else:
            unmatched += 1

    rtts = [e[0] for e in rtt_entries]
    rtt_stats = compute_stats(rtts)

    anomalies = []
    if rtt_stats["median"] > 0:
        threshold = rtt_stats["median"] * 2
        for rtt_ms, seq, frame in rtt_entries:
            if rtt_ms > threshold:
                anomalies.append({"seq": seq, "rtt_ms": rtt_ms, "frame": frame})

    result = {
        "echo_pairs_matched": matched,
        "echo_unmatched": unmatched,
        "rtt_ms": rtt_stats,
        "anomalies": anomalies,
    }

    type_counts: dict[str, int] = defaultdict(int)
    for pkt in raw:
        t = pkt.get("type")
        if t is not None:
            name = ICMP_TYPE_NAMES.get(t, f"type_{t}")
            type_counts[name] += 1
    if type_counts:
        result["type_distribution"] = dict(type_counts)

    # Destination Unreachable details (Type 3)
    unreach_groups: dict[tuple, dict] = {}
    for pkt in raw:
        if pkt.get("type") != 3:
            continue
        src = pkt.get("src_ip", "")
        dst = pkt.get("dst_ip", "")
        code = pkt.get("code", 0)
        inner_dst = pkt.get("inner_dst_ip", "")
        key = (src, dst, code, inner_dst)
        if key not in unreach_groups:
            unreach_entry: dict = {
                "src": src, "dst": dst, "code": code,
                "code_meaning": ICMP_UNREACH_CODES.get(code, f"Code {code}"),
                "count": 0, "sample_frame": pkt["frame"],
            }
            if inner_dst:
                unreach_entry["unreachable_dst"] = inner_dst
            unreach_groups[key] = unreach_entry
        unreach_groups[key]["count"] += 1
    if unreach_groups:
        result["unreachable_details"] = list(unreach_groups.values())

    # Redirect details (Type 5)
    redirect_groups: dict[tuple, dict] = {}
    for pkt in raw:
        if pkt.get("type") != 5:
            continue
        src = pkt.get("src_ip", "")
        dst = pkt.get("dst_ip", "")
        gateway = pkt.get("redir_gw", "")
        redirect_for = pkt.get("inner_dst_ip", "")
        key = (src, dst, gateway, redirect_for)
        if key not in redirect_groups:
            redir_entry: dict = {
                "src": src, "dst": dst,
                "count": 0, "sample_frame": pkt["frame"],
            }
            if gateway:
                redir_entry["gateway"] = gateway
            if redirect_for:
                redir_entry["redirect_for"] = redirect_for
            redirect_groups[key] = redir_entry
        redirect_groups[key]["count"] += 1
    if redirect_groups:
        result["redirect_details"] = list(redirect_groups.values())

    # TTL Exceeded sources (Type 11)
    ttl_groups: dict[tuple, dict] = {}
    for pkt in raw:
        if pkt.get("type") != 11:
            continue
        src = pkt.get("src_ip", "")
        dst = pkt.get("dst_ip", "")
        original_dst = pkt.get("inner_dst_ip", "")
        key = (src, original_dst)
        if key not in ttl_groups:
            ttl_entry: dict = {
                "src": src, "dst": dst,
                "count": 0, "sample_frame": pkt["frame"],
            }
            if original_dst:
                ttl_entry["original_dst"] = original_dst
            ttl_groups[key] = ttl_entry
        ttl_groups[key]["count"] += 1
    if ttl_groups:
        result["ttl_exceeded_sources"] = list(ttl_groups.values())

    return result


def reduce_tcp(raw: list[dict]) -> dict:
    streams = defaultdict(list)
    for pkt in raw:
        stream_id = pkt.get("stream")
        if stream_id is not None:
            streams[stream_id].append(pkt)

    retransmissions_total = 0
    rst_count_total = 0
    duplicate_ack_total = 0
    out_of_order_total = 0
    zero_window_total = 0
    all_deltas = []
    per_stream = {}

    syn_sent = 0
    syn_ack_received = 0
    rst_teardown_streams = set()
    fin_teardown_streams = set()

    for stream_id, pkts in streams.items():
        retrans = 0
        rst_count = 0
        dup_ack = 0
        ooo = 0
        zero_win = 0
        notable_frames_set = set()
        deltas = []
        ack_rtts = []
        has_syn = False
        has_syn_ack = False
        has_post_handshake_ack = False

        for pkt in pkts:
            flags = pkt.get("flags", 0)

            if (flags & SYN) and not (flags & ACK):
                has_syn = True
                syn_sent += 1
            if (flags & SYN) and (flags & ACK):
                has_syn_ack = True
                syn_ack_received += 1
            if (flags & ACK) and not (flags & SYN) and has_syn_ack:
                has_post_handshake_ack = True

            if flags & RST:
                rst_count += 1
                rst_teardown_streams.add(stream_id)
                notable_frames_set.add(pkt["frame"])
            if flags & FIN:
                fin_teardown_streams.add(stream_id)

            if pkt.get("is_retransmission"):
                retrans += 1
                notable_frames_set.add(pkt["frame"])
            if pkt.get("is_duplicate_ack"):
                dup_ack += 1
                notable_frames_set.add(pkt["frame"])
            if pkt.get("is_out_of_order"):
                ooo += 1
                notable_frames_set.add(pkt["frame"])
            if pkt.get("is_zero_window"):
                zero_win += 1
                notable_frames_set.add(pkt["frame"])

            delta = pkt.get("time_delta")
            if delta is not None:
                delta_ms = round(delta * 1000, 2)
                deltas.append(delta_ms)
                all_deltas.append(delta_ms)

            art = pkt.get("ack_rtt")
            if art is not None:
                ack_rtts.append(round(art * 1000, 2))

        retransmissions_total += retrans
        rst_count_total += rst_count
        duplicate_ack_total += dup_ack
        out_of_order_total += ooo
        zero_window_total += zero_win

        handshake_complete = has_syn and has_syn_ack and has_post_handshake_ack

        per_stream[stream_id] = {
            "first": pkts[0],
            "retrans": retrans,
            "dup_ack": dup_ack,
            "ooo": ooo,
            "zero_win": zero_win,
            "rst_present": rst_count > 0,
            "notable_frames": sorted(notable_frames_set)[:5],
            "delta_stats": compute_stats(deltas),
            "ack_rtt_stats": compute_stats(ack_rtts),
            "handshake_complete": handshake_complete,
        }

    overall_median = statistics.median(all_deltas) if all_deltas else 0

    handshakes_completed = sum(
        1 for d in per_stream.values() if d["handshake_complete"]
    )
    handshake_success_pct = round(
        handshakes_completed / syn_sent * 100, 1
    ) if syn_sent > 0 else 0.0

    streams_with_issues = []
    for stream_id, data in per_stream.items():
        has_retrans = data["retrans"] > 0
        has_dup_ack = data["dup_ack"] > 0
        has_ooo = data["ooo"] > 0
        has_zero_win = data["zero_win"] > 0
        has_rst = data["rst_present"]
        has_high_delta = (
            data["delta_stats"]["p95"] > overall_median * 2
            if overall_median > 0 else False
        )
        if not (has_retrans or has_dup_ack or has_ooo or has_zero_win
                or has_rst or has_high_delta):
            continue

        first = data["first"]
        streams_with_issues.append({
            "stream_id": stream_id,
            "src": f"{first.get('src_ip', '')}:{first.get('src_port', '')}",
            "dst": f"{first.get('dst_ip', '')}:{first.get('dst_port', '')}",
            "retransmissions": data["retrans"],
            "duplicate_acks": data["dup_ack"],
            "out_of_order": data["ooo"],
            "zero_window_events": data["zero_win"],
            "rst": data["rst_present"],
            "ack_rtt_ms": data["ack_rtt_stats"],
            "delta_ms": data["delta_stats"],
            "sample_frames": data["notable_frames"],
        })

    return {
        "streams_total": len(streams),
        "retransmissions_total": retransmissions_total,
        "rst_count": rst_count_total,
        "duplicate_ack_total": duplicate_ack_total,
        "out_of_order_total": out_of_order_total,
        "zero_window_total": zero_window_total,
        "connection_stats": {
            "syn_sent": syn_sent,
            "syn_ack_received": syn_ack_received,
            "handshakes_completed": handshakes_completed,
            "handshake_success_rate_pct": handshake_success_pct,
            "rst_teardowns": len(rst_teardown_streams),
            "fin_teardowns": len(fin_teardown_streams),
        },
        "streams_with_issues": streams_with_issues,
    }


def reduce_dns(raw: list[dict]) -> dict:
    queries = []
    responses = []
    for pkt in raw:
        if pkt.get("is_response") == 1:
            responses.append(pkt)
        else:
            queries.append(pkt)

    response_ids = {
        pkt["dns_id"] for pkt in responses if pkt.get("dns_id") is not None
    }
    unanswered = sum(
        1 for q in queries
        if q.get("dns_id") is not None and q["dns_id"] not in response_ids
    )

    rcode_dist = defaultdict(int)
    for pkt in responses:
        rcode = pkt.get("rcode")
        if rcode is not None:
            rcode_dist[RCODE_NAMES.get(rcode, f"RCODE_{rcode}")] += 1

    latency_entries = []
    for pkt in responses:
        dns_time = pkt.get("dns_time")
        if dns_time is not None:
            latency_ms = round(dns_time * 1000, 2)
            latency_entries.append({
                "latency_ms": latency_ms,
                "name": pkt.get("qry_name", ""),
                "frame": pkt["frame"],
            })

    latencies = [e["latency_ms"] for e in latency_entries]
    latency_stats = compute_stats(latencies)

    slow_queries = []
    if latency_stats["median"] > 0:
        threshold = latency_stats["median"] * 2
        for entry in latency_entries:
            if entry["latency_ms"] > threshold:
                slow_queries.append(entry)

    result = {
        "queries_total": len(queries),
        "responses_total": len(responses),
        "unanswered_queries": unanswered,
        "rcode_distribution": dict(rcode_dist),
        "latency_ms": latency_stats,
        "slow_queries": slow_queries,
    }

    qtype_counts: dict[str, int] = defaultdict(int)
    for pkt in queries:
        qt = pkt.get("qry_type")
        if qt is not None:
            name = DNS_QTYPE_NAMES.get(qt, f"TYPE_{qt}")
            qtype_counts[name] += 1
    if qtype_counts:
        result["query_type_distribution"] = dict(qtype_counts)

    nxdomain_groups: dict[str, dict] = {}
    for pkt in responses:
        if pkt.get("rcode") != 3:
            continue
        name = pkt.get("qry_name", "")
        if name not in nxdomain_groups:
            nxdomain_groups[name] = {
                "name": name, "count": 0, "sample_frame": pkt["frame"],
            }
        nxdomain_groups[name]["count"] += 1
    if nxdomain_groups:
        result["nxdomain_domains"] = sorted(
            nxdomain_groups.values(), key=lambda x: x["count"], reverse=True
        )[:10]

    servfail_groups: dict[str, dict] = {}
    for pkt in responses:
        if pkt.get("rcode") != 2:
            continue
        name = pkt.get("qry_name", "")
        if name not in servfail_groups:
            servfail_groups[name] = {
                "name": name, "count": 0, "sample_frame": pkt["frame"],
            }
        servfail_groups[name]["count"] += 1
    if servfail_groups:
        result["servfail_domains"] = sorted(
            servfail_groups.values(), key=lambda x: x["count"], reverse=True
        )[:10]

    domain_counts: dict[str, int] = defaultdict(int)
    for pkt in queries:
        name = pkt.get("qry_name", "")
        if name:
            domain_counts[name] += 1
    if domain_counts:
        result["top_queried_domains"] = [
            {"name": name, "count": count}
            for name, count in sorted(
                domain_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]
        ]

    dns_servers = set()
    for pkt in queries:
        dst = pkt.get("dst_ip", "")
        if dst:
            dns_servers.add(dst)
    if dns_servers:
        result["dns_servers_queried"] = sorted(dns_servers)

    truncated = sum(1 for pkt in responses if pkt.get("is_truncated"))
    result["truncated_responses"] = truncated

    return result


def reduce_to_semantic(raw_data: dict) -> dict:
    summary = raw_data["summary"]
    protocols_present = []

    duration = summary["duration_seconds"]
    total = summary["total_packets"]
    avg_pps = round(total / duration, 1) if duration > 0 else 0.0

    semantic = {
        "capture_summary": {
            "file": summary["file"],
            "total_packets": total,
            "duration_seconds": duration,
            "avg_packets_per_second": avg_pps,
        }
    }

    if raw_data["arp"]:
        protocols_present.append("ARP")
        semantic["arp"] = reduce_arp(raw_data["arp"])

    if raw_data["icmp"]:
        protocols_present.append("ICMP")
        semantic["icmp"] = reduce_icmp(raw_data["icmp"])

    if raw_data["tcp"]:
        protocols_present.append("TCP")
        semantic["tcp"] = reduce_tcp(raw_data["tcp"])

    if raw_data["dns"]:
        protocols_present.append("DNS")
        semantic["dns"] = reduce_dns(raw_data["dns"])

    semantic["capture_summary"]["protocols_present"] = protocols_present
    return semantic


def save_semantic_json(semantic: dict, pcap_path: Path,
                       output_dir: Path | None = None) -> Path:
    base_dir = output_dir if output_dir else pcap_path.parent
    base_dir.mkdir(parents=True, exist_ok=True)
    out_path = base_dir / f"{pcap_path.stem}_semantic.json"
    out_path.write_text(json.dumps(semantic, indent=2) + "\n", encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        args = parse_args()
        semantic_dir = Path(args.semantic_dir) if args.semantic_dir else None

        if args.compare:
            print("[1/4] Validating inputs...", file=sys.stderr)
            pcap_a = validate_input(args.pcap)
            pcap_b = validate_input(args.compare)

            print(f"[2/4] Extracting from Capture A ({pcap_a.name})...", file=sys.stderr)
            raw_a = extract_all(pcap_a)

            print(f"[3/4] Extracting from Capture B ({pcap_b.name})...", file=sys.stderr)
            raw_b = extract_all(pcap_b)

            print("[4/4] Building semantic summaries...", file=sys.stderr)
            semantic_a = reduce_to_semantic(raw_a)
            semantic_b = reduce_to_semantic(raw_b)
            json_a = save_semantic_json(semantic_a, pcap_a, semantic_dir)
            json_b = save_semantic_json(semantic_b, pcap_b, semantic_dir)
            print(f"      Saved: {json_a}", file=sys.stderr)
            print(f"      Saved: {json_b}", file=sys.stderr)

            # Emit machine-readable output for the skill to parse
            print(f"SEMANTIC_JSON_A={json_a}")
            print(f"SEMANTIC_JSON_B={json_b}")
            print(f"COMPARE_MODE={args.mode}")

        else:
            print("[1/3] Validating input...", file=sys.stderr)
            pcap_path = validate_input(args.pcap)

            print("[2/3] Extracting protocol data via tshark...", file=sys.stderr)
            raw_data = extract_all(pcap_path)

            print("[3/3] Building semantic summary...", file=sys.stderr)
            semantic = reduce_to_semantic(raw_data)
            json_path = save_semantic_json(semantic, pcap_path, semantic_dir)
            print(f"      Saved: {json_path}", file=sys.stderr)

            # Emit machine-readable output for the skill to parse
            print(f"SEMANTIC_JSON={json_path}")

    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
