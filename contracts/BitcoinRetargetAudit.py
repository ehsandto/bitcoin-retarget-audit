# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import hashlib
import json
import re


SOURCES = ("https://mempool.space/api", "https://blockstream.info/api")
INTERVAL = 2016
TIMESPAN = 14 * 24 * 60 * 60
POW_LIMIT = (1 << 224) - 1


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fail(message):
    raise gl.vm.UserError("[EXPECTED] " + message)


def boundary(height):
    return type(height) is int and INTERVAL <= height < 2**31 and height % INTERVAL == 0


def compact(target):
    if target == 0:
        return 0
    size = (target.bit_length() + 7) // 8
    word = target << (8 * (3 - size)) if size <= 3 else target >> (8 * (size - 3))
    if word & 0x00800000:
        word >>= 8
        size += 1
    return (size << 24) | word


def target_from_bits(bits):
    size = bits >> 24
    word = bits & 0x007fffff
    if bits & 0x00800000 or not 1 <= size <= 32 or word == 0:
        raise ValueError("Invalid compact target")
    target = word >> (8 * (3 - size)) if size <= 3 else word << (8 * (size - 3))
    if not 1 <= target <= POW_LIMIT or compact(target) != bits:
        raise ValueError("Invalid mainnet target")
    return target


def retarget(old_bits, elapsed):
    bounded = max(TIMESPAN // 4, min(elapsed, TIMESPAN * 4))
    target = min(POW_LIMIT, target_from_bits(old_bits) * bounded // TIMESPAN)
    return bounded, compact(target)


def uint32(value, signed=False):
    minimum = -(2**31) if signed else 0
    if type(value) is not int or not minimum <= value < 2**32:
        raise ValueError("Invalid 32-bit header field")
    return (value % 2**32).to_bytes(4, "little")


def wire_hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Invalid header hash field")
    return bytes.fromhex(value)[::-1]


def parse_header(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9a-f]{160}", raw):
        raise ValueError("Expected 80-byte block header")
    payload = bytes.fromhex(raw)
    block_hash = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[::-1].hex()
    bits = int.from_bytes(payload[72:76], "little")
    target = target_from_bits(bits)
    return {"raw": raw, "hash": block_hash, "parent": payload[4:36][::-1].hex(),
            "timestamp": int.from_bytes(payload[68:72], "little"),
            "bits": bits, "pow_valid": int(block_hash, 16) <= target}


def normalize_header(row, height):
    if not isinstance(row, dict) or type(row.get("height")) is not int or row["height"] != height:
        raise ValueError("Wrong block height")
    parent = row.get("previousblockhash", "0" * 64) if height == 0 else row.get("previousblockhash")
    payload = (uint32(row.get("version"), signed=True) + wire_hash(parent) + wire_hash(row.get("merkle_root"))
               + uint32(row.get("timestamp")) + uint32(row.get("bits")) + uint32(row.get("nonce")))
    header = parse_header(payload.hex())
    if row.get("id") != header["hash"] or not header["pow_valid"]:
        raise ValueError("Explorer header hash or work mismatch")
    return header["raw"]


def audit_report(height, raw_headers):
    if not isinstance(raw_headers, list) or len(raw_headers) != 3:
        raise ValueError("Expected three boundary headers")
    first, last, successor = map(parse_header, raw_headers)
    if not all(header["pow_valid"] for header in (first, last, successor)):
        raise ValueError("Insufficient header work")
    if first["bits"] != last["bits"] or successor["parent"] != last["hash"]:
        raise ValueError("Header boundary mismatch")
    elapsed = last["timestamp"] - first["timestamp"]
    bounded, expected = retarget(last["bits"], elapsed)
    if successor["bits"] != expected:
        raise ValueError("Unexpected successor difficulty")
    target = target_from_bits(expected)
    report = {
        "boundary": height, "sources": list(SOURCES),
        "heights": [height - INTERVAL, height - 1, height],
        "headers": [first, last, successor],
        "elapsed_seconds": elapsed, "used_seconds": bounded,
        "previous_bits": last["bits"], "expected_bits": expected,
        "expected_target_hex": f"{target:064x}",
        "work_per_block": str((1 << 256) // (target + 1)),
    }
    report["id"] = hashlib.sha256(canonical(report).encode("utf-8")).hexdigest()
    return report


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def source_headers(base, top, heights):
    response = gl.nondet.web.get(f"{base}/blocks/{top}")
    if response.status != 200 or not 1 <= len(response.body) <= 32768:
        raise ValueError("Explorer response unavailable")
    rows = json.loads(response.body.decode("utf-8"), object_pairs_hook=unique_keys)
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10:
        raise ValueError("Unexpected explorer window")
    headers = []
    for height in heights:
        candidates = [row for row in rows if isinstance(row, dict) and row.get("height") == height]
        if len(candidates) != 1:
            raise ValueError("Missing or duplicate boundary block")
        headers.append(normalize_header(candidates[0], height))
    return headers


def acquire(height):
    def evaluate():
        try:
            evidence = []
            for base in SOURCES:
                first = source_headers(base, height - INTERVAL, (height - INTERVAL,))
                nearby = source_headers(base, height, (height - 1, height))
                evidence.append(first + nearby)
            if evidence[0] != evidence[1]:
                raise ValueError("Explorer header disagreement")
            return audit_report(height, evidence[0])
        except Exception:
            raise gl.vm.UserError("[SOURCE_ERROR] Bitcoin boundary evidence unavailable or invalid")

    def validator(result):
        if not isinstance(result, gl.vm.Return):
            return False
        try:
            return canonical(evaluate()) == canonical(result.calldata)
        except Exception:
            return False

    result = gl.vm.run_nondet_unsafe(evaluate, validator)
    try:
        raw = [header["raw"] for header in result["headers"]]
        if canonical(result) != canonical(audit_report(height, raw)):
            raise ValueError("Substituted retarget evidence")
    except Exception:
        raise gl.vm.UserError("[SOURCE_ERROR] Invalid agreed Bitcoin boundary report")
    return result


class BitcoinRetargetAudit(gl.Contract):
    audits: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def capture(self, height: int) -> str:
        if not boundary(height):
            fail("Expected a mainnet difficulty boundary height")
        key = str(height)
        if key in self.audits:
            return json.loads(self.audits[key])["id"]
        report = acquire(height)
        self.audits[key] = canonical(report)
        return report["id"]

    @gl.public.view
    def get_audit(self, height: int) -> dict:
        if str(height) not in self.audits:
            fail("Unknown difficulty boundary")
        return json.loads(self.audits[str(height)])

    @gl.public.view
    def check_successor(self, height: int, audit_id: str, header_hex: str) -> dict:
        report = self.get_audit(height)
        if report["id"] != audit_id:
            fail("Audit ID mismatch")
        try:
            header = parse_header(header_hex)
        except ValueError:
            fail("Malformed successor header")
        checks = {"parent": header["parent"] == report["headers"][1]["hash"],
                  "retarget": header["bits"] == report["expected_bits"], "work": header["pow_valid"]}
        return {"height": height, "audit_id": audit_id, "header_hash": header["hash"],
                "checks": checks, "passes": all(checks.values())}
