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

## Initial publication

`run-20260915-public/cards/` contains nine published JSON files. Identity E has an
intentionally missing path; F contains a content mismatch; H has a mismatching
identity. These are controlled negative inputs, not observations of natural users.
`originals/` preserves the intended pre-mutation cards, including E. L is a
separate lifecycle subject. A-v2 is a legitimate update.

Cards are published before device signing so on-chain URIs can point to immutable
commit URLs. Signatures and transaction receipts will be added separately after
execution. Until then no completed mechanism experiment is claimed here.

GitHub publication enables public inspection and mirroring; it is not a promise
of permanent availability. Download and preserve the evidence with its checksum
manifest. All identities and capability claims in these fixtures are fictional.
