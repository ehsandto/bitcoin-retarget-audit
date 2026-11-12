import fs from 'node:fs';
import {spawn} from 'node:child_process';
import assert from 'node:assert/strict';
import {rpc, receipt, source, read, digest, sha} from './check.mjs';

const code = 'contracts/BitcoinRetargetAudit.py';
const publisher = {name: 'studio-proof-deployer', address: '0x7a413BB4AB62E31d62d4cD9efC8C8a8Dae37FB42'};
const journal = 'PROOFS.json';
const commit = process.argv[2];
const verifyOnly = process.argv.includes('--verify-only');
assert(/^[a-f0-9]{40}$/.test(commit ?? ''));
const proof = fs.existsSync(journal)
  ? JSON.parse(fs.readFileSync(journal, 'utf8'))
  : {network: 'StudioNet', source_commit: commit, transactions: []};
assert.equal(proof.source_commit, commit);
const save = () => fs.writeFileSync(journal, JSON.stringify(proof, null, 2) + '\n');

function send(args, signer, entry) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ['scripts/run-cli.cjs', ...args], {
      windowsHide: true,
      env: {...process.env, BRA_TEST_ACCOUNT: signer.name},
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let pending = '';
    child.stderr.resume();
    child.stdout.on('data', chunk => {
      const lines = (pending + chunk.toString()).split(/\r?\n/);
      pending = lines.pop();
      for (const line of lines) {
        const matched = /^BROADCAST_HASH (0x[0-9a-f]{64})$/i.exec(line);
        if (matched) {
          entry.hash = matched[1];
          save();
          console.log(entry.step, entry.hash);
        }
      }
    });
    child.on('error', reject);
    child.on('close', resolve);
  });
}

async function transaction(step, args, signer) {
  let entry = proof.transactions.find(item => item.step === step);
  if (!entry) {
    assert(!verifyOnly, 'Verification requires an original broadcast journal');
    const nonce = await rpc('eth_getTransactionCount', [signer.address, 'latest']);
    assert.equal(await rpc('eth_getTransactionCount', [signer.address, 'pending']), nonce);
    entry = {step, args, signer: signer.address, nonce};
    proof.transactions.push(entry);
    save();
    await send(args, signer, entry);
  }
  assert.deepEqual(entry.args, args);
  assert.equal(entry.signer, signer.address);
  assert(entry.hash, 'Broadcast status unknown. Inspect account history before any retry.');
  entry.receipt = await receipt(entry.hash);
  save();
  assert(entry.receipt.committed, 'Transaction did not commit');
  const native = await rpc('eth_getTransactionByHash', [entry.hash]);
  assert.equal(native.from_address.toLowerCase(), signer.address.toLowerCase());
  assert.equal(BigInt(native.nonce), BigInt(entry.nonce));
  assert.equal(BigInt(native.value), 0n);
  console.log(step, entry.receipt.status, entry.receipt.execution);
  return entry.receipt.address;
}





const reference = JSON.parse(fs.readFileSync('REFERENCE.json', 'utf8'));
const timespan = 1209600;
const limit = (1n << 224n) - 1n;

function target(bits) {
  const mantissa = BigInt(bits & 0x7fffff);
  const shift = BigInt(8 * ((bits >>> 24) - 3));
  return shift < 0n ? mantissa >> -shift : mantissa << shift;
}

function newBits(oldBits, seconds) {
  const scaled = target(oldBits) * BigInt(seconds) / BigInt(timespan);
  let hex = (scaled > limit ? limit : scaled).toString(16);
  if (hex.length % 2) hex = '0' + hex;
  if (parseInt(hex.slice(0, 2), 16) >= 128) hex = '00' + hex;
  return (hex.length / 2) * 0x1000000 + parseInt(hex.slice(0, 6).padEnd(6, '0'), 16);
}

function blockHash(raw) {
  const once = sha(Buffer.from(raw, 'hex'));
  const twice = sha(Buffer.from(once, 'hex'));
  return Buffer.from(twice, 'hex').reverse().toString('hex');
}

function reconstructEvidence(height, fixture) {
  const headers = fixture.rows.map((row, i) => {
    const raw = fixture.raw[i];
    const hash = blockHash(raw);
    assert.equal(hash, row.id);
    assert(BigInt('0x' + hash) <= target(row.bits));
    return {raw, hash, parent: row.previousblockhash, timestamp: row.timestamp, bits: row.bits, pow_valid: true};
  });
  assert.equal(headers[0].bits, headers[1].bits);
  assert.equal(headers[2].parent, headers[1].hash);
  const elapsed = headers[1].timestamp - headers[0].timestamp;
  const bounded = Math.min(4 * timespan, Math.max(timespan / 4, elapsed));
  const expected = newBits(headers[1].bits, bounded);
  assert.equal(expected, headers[2].bits);
  const required = target(expected);
  return {boundary: height, sources: ['https://mempool.space/api', 'https://blockstream.info/api'],
    heights: [height - 2016, height - 1, height], headers, elapsed_seconds: elapsed, used_seconds: bounded,
    previous_bits: headers[1].bits, expected_bits: expected, expected_target_hex: required.toString(16).padStart(64, '0'),
    work_per_block: ((1n << 256n) / (required + 1n)).toString()};
}

assert.equal(await rpc('eth_chainId', []), '0xf22f');
proof.address = await transaction('deploy', ['deploy', '--contract', code], publisher);
proof.source = await source(proof.address);
proof.audits ??= {};
save();

for (const [key, fixture] of Object.entries(reference)) {
  const height = Number(key);
  assert.equal(await transaction('capture-' + key, ['write', proof.address, 'capture', '--args', key], publisher), proof.address);
  const evidence = reconstructEvidence(height, fixture);
  const audit = await read(proof.address, 'get_audit', [height]);
  const record = {audit, cases: {}};
  proof.audits[key] = record;
  save();
  assert.deepEqual(audit, {...evidence, id: digest(evidence)});
  const original = fixture.raw[2];
  const altered = original.slice(0, -2) + (original.endsWith('00') ? '01' : '00');
  const cases = [
    ['observed', original, {parent: true, retarget: true, work: true}],
    ['altered_nonce', altered, {parent: true, retarget: true, work: false}],
    ['wrong_parent', fixture.raw[1], {parent: false, retarget: audit.previous_bits === audit.expected_bits, work: true}],
  ];
  for (const [name, raw, checks] of cases) {
    const result = await read(proof.address, 'check_successor', [height, audit.id, raw]);
    record.cases[name] = result;
    save();
    assert.deepEqual(result, {height, audit_id: audit.id, header_hash: blockHash(raw), checks,
      passes: Object.values(checks).every(Boolean)});
  }
  console.log('Boundary', height, 'verified with nBits', audit.expected_bits.toString(16).padStart(8, '0'));
}
const history = await rpc('sim_getTransactionsForAddress', [proof.address]);
assert.deepEqual(history.map(t => t.hash).sort(), proof.transactions.map(t => t.hash).sort());
proof.verified = true;
save();
console.log('Verified two historical retargets and six successor checks.');
