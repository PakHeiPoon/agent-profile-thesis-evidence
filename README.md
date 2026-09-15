# Verifiable Agent Profile: public thesis experiment evidence

This repository contains synthetic public test data and reproducibility evidence
for sponsored profile attestation and auditable directory discovery. It does not
contain the private thesis repository, service credentials, or device private keys.

## Scope

- Device keys authorize profile messages; a separate relayer submits transactions
  and pays testnet fees.
- After correct first binding, authorization and integrity are checked against a
  specified contract. This does not prove the truth of capability claims.
- Directory omission checks require the same snapshot, scope and complete listing.
- Network: Conflux eSpace Testnet (chain ID 71), never mainnet.
- Contract: `0x49Fda55aEFfa835375290217Cd69E9bFFf17039b`.

## Completed run (2026-09-15)

19 real transactions: 14 authorized operations succeeded and 5 adversarial
requests reverted without changing the target records. All 10 device addresses
retained zero balances and nonces. An independent read-only audit replayed 14
events, checked all 9 states against the fixed-block contract, and rechecked all
19 receipts via another RPC endpoint (not an independent operator).

- Snapshot block: `262638930` (22 successor blocks observed at audit start).
- Snapshot hash: `0x879dea9a35d812e18094b53935907b6ab5329cd66540af136a6a8152a18919eb`.
- Directory: 4 verified, 1 unavailable URI, 1 content mismatch, 1 identity mismatch,
  2 revoked. Full view: no omission. Reduced view: B omitted, although all 3
  returned entries individually validate. Both static views were fetched in full.
- Actual fee: 0.11071962 **test** CFX, excluding deployment. Failed transactions
  also incur fees. The charged gas follows Conflux's limited refund rule.
- [Contract and transactions](https://evmtestnet.confluxscan.org/address/0x49Fda55aEFfa835375290217Cd69E9bFFf17039b).
- [Detailed Chinese report](run-20260915-public/README.md).

This is a controlled mechanism experiment, not a proof of security, capability
truth, long-term availability, scalability, or a production-service deployment.
First-binding fairness and cross-contract replay remain outside the guarantee.

## Input publication

`run-20260915-public/cards/` contains nine published JSON files. Identity E has an
intentionally missing path; F contains a content mismatch; H has a mismatching
identity. These are controlled negative inputs, not observations of natural users.
`originals/` preserves the intended pre-mutation cards, including E. L is a
separate lifecycle subject. A-v2 is a legitimate update.

Cards were published before device signing so on-chain URIs point to immutable
commit URLs. The card commit is `34c6ccdfd758e61bbae4bd968ece03ad8932c82d`;
the public static view commit is `c242d992a5016c6fe05a534532b2c994c9654a4c`.
The preparation manifest's `public/` paths correspond to `cards/` in this repository.

## Read-only reproduction

Install Python with `web3==7.16.0` and `eth-account==0.13.7`, then run from the
repository root. These commands do not require a wallet or submit transactions.
Use a new output directory for each recheck; archived evidence is never overwritten.

```bash
python scripts/testnet_audit.py reconstruct run-20260915-public/run-manifest.json deployment/contract-artifact.json run-20260915-public/evidence/run-results.json audit-recheck-01
python scripts/testnet_audit.py compare audit-recheck-01/chain-audit.json https://raw.githubusercontent.com/PakHeiPoon/agent-profile-thesis-evidence/c242d992a5016c6fe05a534532b2c994c9654a4c/run-20260915-public/views audit-recheck-01/view-comparison.json
```

Historical RPC data and HTTP availability remain external dependencies. The
archived raw receipts, logs and responses allow offline inspection if endpoints
change. The auditor is a separate experimental program, not an upgrade of the
original online indexer. Hashes in `SHA256SUMS` cover the public archive files.

`deployment/contract-artifact.json` freezes the exact compiler input, ABI and
bytecode. Historical protocol literals and source comments are intentionally
preserved to allow byte-for-byte verification. Explorer source verification is
not claimed. The transaction runner is included for inspection, but broadcasting
a new run requires deliberate configuration of an isolated deployment and wallet;
do not blindly repeat the archived signed requests.

GitHub publication enables public inspection and mirroring; it is not a promise
of permanent availability. Download and preserve the evidence with its checksum
manifest. All identities and capability claims in these fixtures are fictional.
