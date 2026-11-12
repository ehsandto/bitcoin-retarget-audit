import fs from 'node:fs';
import assert from 'node:assert/strict';

const proof = JSON.parse(fs.readFileSync('PROOFS.json', 'utf8'));
const {address, source_commit: commit, source, transactions, audits} = proof;
assert(proof.verified && source.source_match);
assert.equal(transactions.length, 3);
assert(transactions.every(t => t.receipt.committed && t.receipt.status === 'FINALIZED'));
assert.deepEqual(Object.keys(audits), ['840672', '842688']);

const repo = 'https://github.com/ehsandto/bitcoin-retarget-audit';
const explorer = 'https://explorer-studio.genlayer.com';
const deployed = '[StudioNet deployment](' + explorer + '/address/' + address + ')';
const code = '[Exact deployed source](' + repo + '/blob/' + commit + '/contracts/BitcoinRetargetAudit.py)';
const tx = t => '[' + (t.step === 'deploy' ? 'Deploy contract' : 'Capture boundary ' + t.step.slice(8)) +
  '](' + explorer + '/tx/' + t.hash + ')';
const hex = value => '0x' + value.toString(16).padStart(8, '0');

const rows = Object.values(audits).map(({audit, cases}) => {
  assert(cases.observed.passes);
  assert(!cases.altered_nonce.passes && !cases.altered_nonce.checks.work);
  assert(!cases.wrong_parent.passes && !cases.wrong_parent.checks.parent);
  return '| ' + audit.boundary + ' | ' + audit.elapsed_seconds + ' | ' + hex(audit.previous_bits) +
    ' | ' + hex(audit.expected_bits) + ' | Accepted | Rejected | Rejected |';
});

fs.writeFileSync('LIVE_PROOFS.md', [
  '# StudioNet evidence', '',
  '- ' + deployed, '- ' + code,
  '- [Finalized receipts and full audit reports](PROOFS.json)',
  '- [Independent explorer reference headers](REFERENCE.json)',
  '- Deployed source SHA-256 ' + source.sha256,
  '', '| Finalized transaction | Execution | Agree votes |', '|---|---|---:|',
  ...transactions.map(t => '| ' + tx(t) + ' | ' + t.receipt.execution + ' | ' + t.receipt.agree_votes + ' |'),
  '', '| Boundary height | Elapsed seconds | Previous bits | Computed and observed bits | Observed header | Altered nonce | Wrong parent |',
  '|---:|---:|---|---|---|---|---|',
  ...rows, '',
  'Both explorers returned matching wire headers. The reference verifier independently recalculated each block hash, verified proof of work, and replayed the retarget arithmetic with BigInt. The contract verified the sampled boundary using explorer-selected mainnet history.',
  '',
  'Twelve local tests also cover the Bitcoin Core historical vector, both clamp edges, malformed compact targets, modified source evidence and validator refetching.',
  '',
].join('\n'));

const description = [
  'BitcoinRetargetAudit verifies historical Bitcoin mainnet difficulty boundaries. Each GenLayer validator independently fetches three headers from both mempool.space and Blockstream. It reconstructs the 80-byte headers, checks their hashes and proof of work, then requires agreement on the complete report.',
  'The contract computes the compact target from the previous interval’s timestamps using the mainnet clamp and proof-of-work limit. It records the raw headers and exact calculation. A reusable read checks a candidate’s parent, required target and work.',
  'StudioNet verified boundaries 840672 and 842688 plus six successor checks. Valid headers passed. Altered nonces and wrong parents failed. The audit relies on the two explorers for main-chain selection and verifies sampled headers.',
].join('\n\n');
assert(description.length <= 1000);
fs.writeFileSync('SUBMISSION.md', [
  '# BitcoinRetargetAudit', '', '**Contribution type** Builder → Intelligent Contracts', '',
  '**Description**', '', description, '',
  '**Evidence**', '', '- [GitHub repository](' + repo + ')', '- ' + code, '- ' + deployed,
  '- [Live proof matrix](' + repo + '/blob/main/LIVE_PROOFS.md)',
  ...transactions.map(t => '- ' + tx(t)), '',
].join('\n'));
