"""Obtain a portable independent reference for the two mainnet boundaries."""
import hashlib
import json
from pathlib import Path
import struct
from urllib.request import urlopen


EXPLORERS = ("https://mempool.space/api", "https://blockstream.info/api")
HEIGHTS = (840672, 842688)
FIELDS = ("height", "id", "version", "previousblockhash", "merkle_root", "timestamp", "bits", "nonce")


def get_window(url):
    with urlopen(url, timeout=20) as response:
        data = response.read(32769)
    assert len(data) <= 32768
    return json.loads(data)


def get_rows(explorer, height):
    first = get_window(f"{explorer}/blocks/{height - 2016}")
    pair = get_window(f"{explorer}/blocks/{height}")
    candidates = [first[0], pair[1], pair[0]]
    assert [block["height"] for block in candidates] == [height - 2016, height - 1, height]
    return [{key: block[key] for key in FIELDS} for block in candidates]


def raw_header(row):
    parent = bytes.fromhex(row["previousblockhash"])[::-1]
    merkle = bytes.fromhex(row["merkle_root"])[::-1]
    raw = struct.pack("<I32s32sIII", row["version"] & 0xffffffff, parent, merkle,
                      row["timestamp"], row["bits"], row["nonce"])
    assert hashlib.sha256(hashlib.sha256(raw).digest()).digest()[::-1].hex() == row["id"]
    return raw.hex()


def capture():
    output = {}
    for height in HEIGHTS:
        first, second = (get_rows(explorer, height) for explorer in EXPLORERS)
        wire = list(map(raw_header, first))
        assert wire == list(map(raw_header, second))
        output[str(height)] = {"rows": first, "raw": wire}
    Path("REFERENCE.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    capture()
