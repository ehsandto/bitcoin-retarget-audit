import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "contracts/BitcoinRetargetAudit.py"
HEIGHT = 840672


@pytest.fixture
def core():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if not isinstance(node, ast.ClassDef)
                 and not (isinstance(node, ast.ImportFrom) and node.module == "genlayer")]
    ns = {}
    exec(compile(tree, str(SOURCE), "exec"), ns)
    return ns


@pytest.fixture
def reference():
    return json.loads((ROOT / "REFERENCE.json").read_text(encoding="utf-8"))


def test_mainnet_arithmetic_matches_core_vector(core):
    # Historical input and expected bits from Bitcoin Core's pow_tests.cpp.
    assert core["retarget"](0x1D00FFFF, 1262152739 - 1261130161) == (1022578, 0x1D00D86A)


def test_exact_clamps_and_limit(core):
    timespan = core["TIMESPAN"]
    previous = 0x1C03FFFC
    assert core["retarget"](previous, 1) == (timespan // 4, 0x1C00FFFF)
    assert core["retarget"](previous, 12 * timespan) == (timespan * 4, 0x1C0FFFF0)
    assert core["retarget"](0x1D00FFFF, 12 * timespan) == (timespan * 4, 0x1D00FFFF)


@pytest.mark.parametrize("bits", [0, 0x1D80FFFF, 0x23000001, 0x1D010000, 0x02000100, 0x01000001])
def test_invalid_or_noncanonical_compact_bits(core, bits):
    with pytest.raises(ValueError):
        core["target_from_bits"](bits)


@pytest.mark.parametrize("height", [840672, 842688])
def test_reconstructs_public_headers_and_expected_retarget(core, reference, height):
    vector = reference[str(height)]
    rows = vector["rows"]
    raw = [core["normalize_header"](row, row["height"]) for row in rows]
    assert raw == vector["raw"]
    report = core["audit_report"](height, raw)
    assert report["expected_bits"] == rows[2]["bits"]
    assert report["headers"][2]["parent"] == rows[1]["id"]
    bad_nonce = raw[2][:-2] + ("00" if raw[2][-2:] != "00" else "01")
    assert not core["parse_header"](bad_nonce)["pow_valid"]
    with pytest.raises(ValueError, match="Insufficient header work"):
        core["audit_report"](height, raw[:2] + [bad_nonce])


def test_callback_refetches_both_explorers_and_rejects_substituted_result(core, reference):
    first, last, successor = reference[str(HEIGHT)]["rows"]
    urls = []
    tamper = False

    def get(url):
        urls.append(url)
        rows = [first] if url.endswith(f"/{HEIGHT - 2016}") else [successor, last]
        if tamper and "blockstream.info" in url:
            rows = [dict(rows[0], nonce=rows[0]["nonce"] ^ 1), *rows[1:]]
        return SimpleNamespace(status=200, body=json.dumps(rows).encode())

    def run(leader, validator):
        nonlocal tamper
        expected = leader()
        assert validator(SimpleNamespace(calldata=expected))
        forged = {**expected, "expected_bits": expected["expected_bits"] ^ 1}
        assert not validator(SimpleNamespace(calldata=forged))
        tamper = True
        assert not validator(SimpleNamespace(calldata=expected))
        return expected

    core["gl"] = SimpleNamespace(
        nondet=SimpleNamespace(web=SimpleNamespace(get=get)),
        vm=SimpleNamespace(Return=SimpleNamespace, UserError=ValueError, run_nondet_unsafe=run),
    )
    assert core["acquire"](HEIGHT)["boundary"] == HEIGHT
    sequence = [f"{base}/blocks/{height}" for base in core["SOURCES"] for height in (HEIGHT - 2016, HEIGHT)]
    assert urls[:12] == sequence * 3
    assert urls[12:] == sequence[:3]


def test_direct_boundary_report_and_successor_gates(direct_vm, direct_deploy, reference):
    contract = direct_deploy(str(SOURCE))
    first, last, successor = reference[str(HEIGHT)]["rows"]
    for top, rows in ((HEIGHT - 2016, [first]), (HEIGHT, [successor, last])):
        direct_vm.mock_web(r".*/blocks/" + str(top) + "$", {
            "response": {"status": 200, "headers": {}, "body": json.dumps(rows).encode()}, "method": "GET",
        })
    with direct_vm.expect_revert("mainnet difficulty boundary"):
        contract.capture(HEIGHT + 1)
    audit_id = contract.capture(HEIGHT)
    report = contract.get_audit(HEIGHT)
    assert report["id"] == audit_id
    assert contract.capture(HEIGHT) == audit_id
    good = contract.check_successor(HEIGHT, audit_id, report["headers"][2]["raw"])
    assert good["passes"] and all(good["checks"].values())
    old = contract.check_successor(HEIGHT, audit_id, report["headers"][1]["raw"])
    assert not old["passes"] and not old["checks"]["parent"] and old["checks"]["work"]
    with direct_vm.expect_revert("Audit ID mismatch"):
        contract.check_successor(HEIGHT, "wrong", report["headers"][2]["raw"])
