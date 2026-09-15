"""Read-only, fixed-snapshot reconstruction and public directory-view comparison.

No signing keys and no blockchain transactions. This is an experimental auditor,
not a claim that the legacy production indexer supports confirmations or reorgs.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from web3 import Web3
from web3._utils.events import get_event_data
from eth_utils import event_abi_to_log_topic

from testnet_mechanisms import BACKUP_RPC, CONTRACT, connect, digest, fetch, plain, require, save

DEPLOYMENT_BLOCK = 262631620
CONFIRMATIONS = 12


def reconstruct(manifest_path, artifact_path, results_path, output):
    manifest = json.loads(Path(manifest_path).read_text())
    results = json.loads(Path(results_path).read_text())
    w3, contract = connect(artifact_path, BACKUP_RPC)
    snapshot = results["end_block"]
    head = w3.eth.block_number
    require(head >= snapshot+CONFIRMATIONS, "Insufficient confirmation depth; check again later")
    block = w3.eth.get_block(snapshot)
    require(block.hash.to_0x_hex() == results["end_block_hash"], "Snapshot hash changed")
    out = Path(output)
    out.mkdir()
    event_abis = {event_abi_to_log_topic(a): a for a in contract.abi if a["type"] == "event"}
    logs = []
    for start in range(DEPLOYMENT_BLOCK, snapshot+1, 1500):
        logs.extend(w3.eth.get_logs({"address": CONTRACT, "fromBlock": start,
                                     "toBlock": min(start+1499, snapshot)}))
    logs.sort(key=lambda e: (e.blockNumber, e.transactionIndex, e.logIndex))
    require(len({(x.transactionHash.to_0x_hex(), x.logIndex) for x in logs}) == len(logs), "Duplicate logs")
    events = []
    state = {}
    for log in logs:
        event = get_event_data(w3.codec, event_abis[bytes(log.topics[0])], log)
        item = plain(event)
        events.append(item)
        a, kind = item["args"], item["event"]
        identifier = a["agentIdHash"]
        if kind in {"Registered", "Updated"}:
            state[identifier] = [a["key"], a["cardHash"], a["ts"], 1, a["cardURI"]]
        elif kind == "KeyRotated":
            state[identifier][0], state[identifier][2] = a["newKey"], a["ts"]
        elif kind == "Revoked":
            state[identifier][2], state[identifier][3] = a["ts"], 2
    expected_ids = {Web3.keccak(text=v).to_0x_hex(): v for v in manifest["identities"].values()}
    require(set(state) == set(expected_ids), "Unexpected identity set in isolated contract")
    require(len(events) == 14, "Unexpected event count")
    rows, responses = [], []
    for identifier, fields in sorted(state.items()):
        actual = plain(contract.functions.getByHash(bytes.fromhex(identifier[2:])).call(block_identifier=snapshot))
        require(fields == actual, "Event reconstruction differs from fixed-block contract state")
        row = {"id_hash": identifier, "expected_synthetic_id": expected_ids[identifier], "state": actual}
        if actual[3] == 2:
            row["classification"] = "revoked"
        else:
            response = fetch(actual[4])
            responses.append(response)
            if response["status"] != 200:
                row["classification"] = "unavailable"
                row["http_status"] = response["status"]
            else:
                card = json.loads(response["body_utf8"])
                row["retrieved_id"] = card.get("agent_id")
                row["computed_hash"] = digest(card)
                if not isinstance(card.get("agent_id"), str) or Web3.keccak(text=card["agent_id"]).to_0x_hex() != identifier:
                    row["classification"] = "identity_mismatch"
                elif "0x"+digest(card) != actual[1]:
                    row["classification"] = "hash_mismatch"
                else:
                    require(contract.functions.verify(card["agent_id"], digest(card)).call(block_identifier=snapshot)[0], "Contract verify mismatch")
                    row["classification"] = "verified"
        rows.append(row)
    counts = dict(Counter(r["classification"] for r in rows))
    require(counts == manifest["expected_directory"], "Unexpected directory classification")
    # Recheck after HTTP work: a snapshot must not silently change during audit.
    require(w3.eth.get_block(snapshot).hash == block.hash, "Snapshot changed during audit")
    transactions = []
    for result in results["transactions"]:
        receipt = w3.eth.get_transaction_receipt(result["hash"])
        tx = w3.eth.get_transaction(result["hash"])
        require(receipt.status == result["status"] and receipt.blockHash.to_0x_hex() == result["block_hash"], "Receipt differs on audit RPC")
        require(tx["from"] == manifest["relayer"] and tx["to"] == CONTRACT and tx["value"] == 0, "Transaction parties mismatch")
        transactions.append({"receipt": plain(receipt), "transaction": plain(tx)})
    scope = {"contract": CONTRACT, "chain_id": 71, "snapshot_block": snapshot,
             "snapshot_hash": block.hash.to_0x_hex(), "run_id": manifest["run_id"],
             "filter": "all active records with retrievable, verified originals in this run"}
    audit = {"scope": scope, "observed_head": head, "minimum_successor_blocks": CONFIRMATIONS,
        "observed_successor_blocks": head-snapshot, "rpc": BACKUP_RPC,
        "rpc_operator_independence": False, "finality_proof": False,
        "event_count": len(events), "counts": counts, "records": rows,
        "verified_ids": sorted(r["retrieved_id"] for r in rows if r["classification"] == "verified"),
        "all_event_states_match_contract": True, "all_19_receipts_rechecked": True}
    save(out / "chain-audit.json", audit)
    save(out / "events.json", events)
    save(out / "http-snapshot.json", responses)
    save(out / "transactions-rechecked.json", transactions)
    # The full and omitted views are explicit fixtures, not an observed provider attack.
    views = out / "views"
    views.mkdir()
    for name, labels in [("full", "ABCD"), ("user", "ACD")]:
        ids = [manifest["identities"][label] for label in labels]
        for n, start in enumerate(range(0, len(ids), 2), 1):
            save(views / f"{name}-{n}.json", {"scope": scope, "page": n,
                 "ids": ids[start:start+2], "next": f"{name}-{n+1}.json" if start+2 < len(ids) else None,
                 "total": len(ids), "fixture": True})
    print(json.dumps({"audit": counts, "events": len(events), "snapshot": snapshot}), flush=True)


def compare(audit_path, base, output):
    audit = json.loads(Path(audit_path).read_text())
    require(base.startswith("https://raw.githubusercontent.com/"), "Use public GitHub view URLs")
    require(len(base.split("/")[5]) == 40, "View URL must contain a full commit ID")
    fetched = []
    views = {}
    verified = set(audit["verified_ids"])
    for name in ["full", "user"]:
        page, ids, seen = f"{name}-1.json", [], set()
        while page is not None:
            require(page not in seen and len(seen) < 10 and page.startswith(name+"-") and "/" not in page, "Invalid pagination")
            seen.add(page)
            response = fetch(base+"/"+page)
            fetched.append(response)
            require(response["status"] == 200, "View unavailable")
            data = json.loads(response["body_utf8"])
            require(data["scope"] == audit["scope"], "Snapshot or scope mismatch")
            require(data["page"] == len(seen), "Wrong page sequence")
            ids.extend(data["ids"])
            page = data["next"]
        require(len(ids) == data["total"] and len(set(ids)) == len(ids), "Incomplete/duplicate directory")
        require(set(ids) <= verified, "View includes an unverified record")
        views[name] = {"ids": ids, "pages": len(seen), "all_individual_entries_valid": True,
                       "omitted_ids": sorted(verified-set(ids))}
    require(views["full"]["omitted_ids"] == [], "Full control has omissions")
    require(views["user"]["omitted_ids"] == [audit["scope"]["run_id"]+"-B"], "Wrong omission")
    save(output, {"scope": audit["scope"], "public_base": base, "views": views,
                  "http_responses": fetched, "controlled_static_views": True})
    print(json.dumps({"comparison": {k: v["omitted_ids"] for k,v in views.items()}}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("reconstruct")
    for name in ["manifest", "artifact", "results", "output"]:
        p.add_argument(name)
    p = sub.add_parser("compare")
    for name in ["audit", "base", "output"]:
        p.add_argument(name)
    args = parser.parse_args()
    if args.command == "reconstruct":
        reconstruct(args.manifest, args.artifact, args.results, args.output)
    else:
        compare(args.audit, args.base, args.output)
