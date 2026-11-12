# StudioNet evidence

- [StudioNet deployment](https://explorer-studio.genlayer.com/address/0xb18A7d381B10c5982DFF5538aCe6B8c5E1b56bD4)
- [Exact deployed source](https://github.com/ehsandto/bitcoin-retarget-audit/blob/5342141f1b73bb760c78cc98e306c9514565f86f/contracts/BitcoinRetargetAudit.py)
- [Finalized receipts and full audit reports](PROOFS.json)
- [Independent explorer reference headers](REFERENCE.json)
- Deployed source SHA-256 7578a2c0c53430714015ebc3de375d98bda4b2775e24c47f08c8531a689f6bab

| Finalized transaction | Execution | Agree votes |
|---|---|---:|
| [Deploy contract](https://explorer-studio.genlayer.com/tx/0x1a3d586b14219372e366a6f79d9992f8cfaa423f082f1fb0f17593863241b037) | SUCCESS | 3 |
| [Capture boundary 840672](https://explorer-studio.genlayer.com/tx/0xb1d201ffec9d9a2291cf77c1afea63ac4fbbe3cd8ab4435a4da8801626294257) | SUCCESS | 3 |
| [Capture boundary 842688](https://explorer-studio.genlayer.com/tx/0xa33d716dd6a4b3a8d93c1e9bc61042dd2fe1e54892f8a634f79d8da58f5fdbaf) | SUCCESS | 3 |

| Boundary height | Elapsed seconds | Previous bits | Computed and observed bits | Observed header | Altered nonce | Wrong parent |
|---:|---:|---|---|---|---|---|
| 840672 | 1186047 | 0x17034219 | 0x170331db | Accepted | Rejected | Rejected |
| 842688 | 1281700 | 0x170331db | 0x1703629a | Accepted | Rejected | Rejected |

Both explorers returned matching wire headers. The reference verifier independently recalculated each block hash, verified proof of work, and replayed the retarget arithmetic with BigInt. The contract verified the sampled boundary using explorer-selected mainnet history.

Twelve local tests also cover the Bitcoin Core historical vector, both clamp edges, malformed compact targets, modified source evidence and validator refetching.
