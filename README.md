# BitcoinRetargetAudit

Audit a historical Bitcoin mainnet difficulty boundary from public block headers. A validator independently retrieves three blocks from both the mempool.space and Blockstream Esplora APIs. The contract reconstructs each full 80-byte wire header, checks its double SHA-256 hash and proof of work, and requires identical bytes from both explorers. [Esplora block API](https://github.com/Blockstream/esplora/blob/master/API.md#blocks)

`capture(height)` accepts a multiple of 2016. It fetches the first and last headers of the previous interval and the successor at the boundary. The successor must name the last block as its parent. The elapsed time comes from the first and last header timestamps. The mainnet rule clamps this time to one-quarter through four times 14 days, multiplies the old target by the resulting ratio using integer arithmetic, caps it at the mainnet proof-of-work limit, and encodes the compact target. The successor's observed bits must match the computed bits exactly. [Bitcoin Core proof-of-work code](https://github.com/bitcoin/bitcoin/blob/master/src/pow.cpp)

Every GenLayer validator repeats the fetch and arithmetic and compares the complete normalized report. `get_audit(height)` returns the raw headers, interval, target, work per block and report ID. `check_successor(height, audit_id, header_hex)` checks the candidate's parent, target and work separately against that report. [GenLayer nondeterminism](https://docs.genlayer.com/developers/intelligent-contracts/features/non-determinism)

The audit uses the two explorers for main-chain selection and verifies the three sampled headers. Its checks cover the retarget boundary. Full Bitcoin validation also requires intermediate headers, timestamp context, and block transactions.

```sh
python -m pip install -r requirements-dev.txt
genvm-lint check contracts/BitcoinRetargetAudit.py
python -m pytest tests -q
```

[StudioNet contract](https://explorer-studio.genlayer.com/address/0xb18A7d381B10c5982DFF5538aCe6B8c5E1b56bD4) · [Live proofs](LIVE_PROOFS.md) · [Submission text](SUBMISSION.md)
