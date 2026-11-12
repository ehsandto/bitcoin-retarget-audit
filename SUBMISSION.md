# BitcoinRetargetAudit

**Contribution type** Builder → Intelligent Contracts

**Description**

BitcoinRetargetAudit verifies historical Bitcoin mainnet difficulty boundaries. Each GenLayer validator independently fetches three headers from both mempool.space and Blockstream. It reconstructs the 80-byte headers, checks their hashes and proof of work, then requires agreement on the complete report.

The contract computes the compact target from the previous interval’s timestamps using the mainnet clamp and proof-of-work limit. It records the raw headers and exact calculation. A reusable read checks a candidate’s parent, required target and work.

StudioNet verified boundaries 840672 and 842688 plus six successor checks. Valid headers passed. Altered nonces and wrong parents failed. The audit relies on the two explorers for main-chain selection and verifies sampled headers.

**Evidence**

- [GitHub repository](https://github.com/ehsandto/bitcoin-retarget-audit)
- [Exact deployed source](https://github.com/ehsandto/bitcoin-retarget-audit/blob/5342141f1b73bb760c78cc98e306c9514565f86f/contracts/BitcoinRetargetAudit.py)
- [StudioNet deployment](https://explorer-studio.genlayer.com/address/0xb18A7d381B10c5982DFF5538aCe6B8c5E1b56bD4)
- [Live proof matrix](https://github.com/ehsandto/bitcoin-retarget-audit/blob/main/LIVE_PROOFS.md)
- [Deploy contract](https://explorer-studio.genlayer.com/tx/0x1a3d586b14219372e366a6f79d9992f8cfaa423f082f1fb0f17593863241b037)
- [Capture boundary 840672](https://explorer-studio.genlayer.com/tx/0xb1d201ffec9d9a2291cf77c1afea63ac4fbbe3cd8ab4435a4da8801626294257)
- [Capture boundary 842688](https://explorer-studio.genlayer.com/tx/0xa33d716dd6a4b3a8d93c1e9bc61042dd2fe1e54892f8a634f79d8da58f5fdbaf)
