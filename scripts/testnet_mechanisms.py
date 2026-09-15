"""Public chain-71 experiments, with offline device signing and remote gas payment.

cards freezes unsigned public files; prepare signs their already published CID.
Device keys are ephemeral and are never stored in the public directory.
run reads the existing relayer key only on its host; no key is exported.
No local EVM, production identities, retries, or contract deployments are used.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sys
import time
from urllib.request import urlopen
from urllib.error import HTTPError

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

CONTRACT = "0x49Fda55aEFfa835375290217Cd69E9bFFf17039b"
RELAYER = "0x172Ed629a857d67149FDFbcEac2436f1EdA866B9"
RPC = "https://evmtestnet.confluxrpc.com"
BACKUP_RPC = "https://evmtestnet.confluxrpc.org"
MAX_TX_FEE = 20_000_000_000_000_000  # 0.02 test CFX
MAX_RUN_FEE = 300_000_000_000_000_000  # 0.3 test CFX


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def plain(value):
    return json.loads(Web3.to_json(value))


def digest(card):
    content = {k: v for k, v in card.items() if k != "_sig"}
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def message(step):
    a = step["args"]
    if step["function"] == "anchor":
        return f"achat-yp-register|{a[0]}|{a[1]}|{a[4]}|{a[2]}"
    if step["function"] == "rotateKey":
        return f"achat-rotate|{a[0]}|{a[1].lower()}|{a[2]}"
    return f"achat-revoke|{a[0]}|{a[1]}"


def prepare_cards(output):
    out = Path(output)
    out.mkdir()
    (out / "public").mkdir()
    (out / "originals").mkdir()
    run_id = out.name
    require(re.fullmatch(r"run-[a-zA-Z0-9-]+", run_id), "Unsafe run ID")
    cards = {label: {"agent_id": f"{run_id}-{label}", "display_name": f"Synthetic agent {label}",
             "offers": ["学术资料检索"], "version": 1, "synthetic": True,
             "notice": "Public thesis test data; capability is an unverified claim."} for label in "ABCDEFGHL"}
    for label, card in cards.items():
        save(out / "originals" / f"{label}.json", card)
        served = copy.deepcopy(card)
        if label == "F":
            served["version"] = 999
        if label == "H":
            served["agent_id"] = f"{run_id}-incorrect-id"
        if label != "E":
            save(out / "public" / f"{label}.json", served)
    updated = {**cards["A"], "version": 2}
    save(out / "originals/A-v2.json", updated)
    save(out / "public/A-v2.json", updated)
    save(out / "cards-manifest.json", {"run_id": run_id,
        "files": {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for folder in ["public", "originals"] for p in sorted((out/folder).glob("*.json"))},
        "storage_status": "prepared_only_not_uploaded_or_pinned",
        "note": "Pin only public/ as the card directory. Signatures are generated after CID is known, avoiding a self-referential CID."})
    print(json.dumps({"prepared_cards": str(out), "private_keys_generated": False}))


def prepare(output, base):
    ipfs = re.fullmatch(r"ipfs://(?:b[a-z2-7]{20,}|Qm[1-9A-HJ-NP-Za-km-z]{44})", base)
    github = re.fullmatch(r"https://raw\.githubusercontent\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+/[0-9a-f]{40}/[A-Za-z0-9/_-]+", base)
    require(ipfs or github, "Expected IPFS CID or immutable GitHub commit URL")
    out = Path(output)
    require(not (out / "run-manifest.json").exists(), "Manifest exists; do not regenerate keys or signatures")
    frozen = json.loads((out / "cards-manifest.json").read_text())
    for filename, expected in frozen["files"].items():
        require(hashlib.sha256((out/filename).read_bytes()).hexdigest() == expected, "Frozen card changed")
    run_id = frozen["run_id"]
    keys = {label: Account.create() for label in "ABCDEFGHL"}
    replacement = Account.create()
    cards = {label: json.loads((out / "originals" / f"{label}.json").read_text()) for label in keys}
    uris = {label: f"{base}/{label}.json" for label in keys}
    steps = []
    ts = int(time.time())

    def step(name, function, args, key, expected=1):
        item = {"name": name, "function": function, "args": args, "expected_status": expected}
        item["signed_message"] = message(item)
        item["expected_message_signer"] = key.address if key else RELAYER
        if key:
            args[3 if function != "revoke" else 2] = key.sign_message(
                encode_defunct(text=item["signed_message"])).signature.to_0x_hex()
        steps.append(item)
        return item

    for label, card in cards.items():
        step(f"register_{label}", "anchor", [card["agent_id"], digest(card), ts, None, uris[label]], keys[label])

    updated = {**cards["A"], "version": 2}
    update_uri = f"{base}/A-v2.json"
    update = step("authorized_update", "anchor", [updated["agent_id"], digest(updated), ts + 1, None, update_uri], keys["A"])
    step("relayer_forgery", "anchor", [updated["agent_id"], digest(updated), ts + 2, None, update_uri], None, 0)
    replay = copy.deepcopy(update)
    replay.update(name="replay", expected_status=0)
    steps.append(replay)
    swapped = step("uri_swap", "anchor", [updated["agent_id"], digest(updated), ts + 2, None, update_uri], keys["A"], 0)
    swapped["args"][4] = uris["B"]  # signature retains A-v2, submitted URI is B
    card = cards["L"]
    step("rotate_key", "rotateKey", [card["agent_id"], replacement.address, ts+1, None], keys["L"])
    step("old_key_update", "anchor", [card["agent_id"], digest(card), ts+2, None, uris["L"]], keys["L"], 0)
    step("new_key_update", "anchor", [card["agent_id"], digest(card), ts+2, None, uris["L"]], replacement)
    step("revoke_L", "revoke", [card["agent_id"], ts+3, None], replacement)
    step("revoked_update", "anchor", [card["agent_id"], digest(card), ts+4, None, uris["L"]], replacement, 0)
    step("revoke_G", "revoke", [cards["G"]["agent_id"], ts+1, None], keys["G"])
    manifest = {"run_id": run_id, "chain_id": 71, "contract": CONTRACT, "relayer": RELAYER,
        "base_url": base, "utc": datetime.now(timezone.utc).isoformat(), "protocol_timestamp": ts,
        "public_file_sha256": {Path(p).name: h for p, h in frozen["files"].items() if p.startswith("public/")},
        "identities": {k: v["agent_id"] for k, v in cards.items()},
        "device_addresses": [k.address for k in keys.values()] + [replacement.address],
        "steps": steps, "expected_transactions": 19, "expected_success": 14, "expected_reverts": 5,
        "expected_directory": {"verified": 4, "unavailable": 1, "hash_mismatch": 1, "identity_mismatch": 1, "revoked": 2},
        "scope": "Synthetic controlled mechanism cases, not a representative population or security proof"}
    save(out / "run-manifest.json", manifest)
    require(len(steps) == 19, "Unexpected transaction count")
    print(json.dumps({"prepared": str(out), "transactions": len(steps), "private_keys_written": False}))


def connect(artifact_path, rpc=RPC):
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
    require(w3.eth.chain_id == 71, "Wrong network")
    artifact = json.loads(Path(artifact_path).read_text())
    require(bytes(w3.eth.get_code(CONTRACT)) == bytes.fromhex(artifact["runtime"]), "Runtime mismatch")
    return w3, w3.eth.contract(address=CONTRACT, abi=artifact["abi"])


def fetch(url):
    # The on-chain URI remains ipfs://. A public HTTP gateway is a transport,
    # not a trust root: application hashes are still checked against the chain.
    requested_uri = url
    if url.startswith("ipfs://"):
        url = "https://ipfs.io/ipfs/" + url[7:]
    started = time.monotonic()
    try:
        with urlopen(url, timeout=20) as response:
            body = response.read(1_000_001)
            require(len(body) <= 1_000_000, "Oversized response")
            return {"uri": requested_uri, "url": url, "status": response.status, "body_sha256": hashlib.sha256(body).hexdigest(),
                    "body_utf8": body.decode(), "elapsed_s": time.monotonic()-started,
                    "utc": datetime.now(timezone.utc).isoformat()}
    except HTTPError as error:
        return {"uri": requested_uri, "url": url, "status": error.code, "utc": datetime.now(timezone.utc).isoformat()}


def preflight_http(manifest):
    observations = []
    for label in "ABCDEFGHL":
        result = fetch(f"{manifest['base_url']}/{label}.json")
        require(result["status"] == (404 if label == "E" else 200), "Unexpected hosting response")
        if label != "E":
            require(result["body_sha256"] == manifest["public_file_sha256"][f"{label}.json"], "Public file differs from frozen input")
        observations.append(result)
    result = fetch(f"{manifest['base_url']}/A-v2.json")
    require(result["status"] == 200, "Updated card is unavailable")
    require(result["body_sha256"] == manifest["public_file_sha256"]["A-v2.json"], "Updated public file differs from input")
    observations.append(result)
    return observations


def run(manifest_path, artifact_path, env_file, output, send):
    manifest = json.loads(Path(manifest_path).read_text())
    require(manifest["contract"] == CONTRACT and manifest["relayer"] == RELAYER and manifest["chain_id"] == 71, "Manifest target mismatch")
    require(len(manifest["steps"]) == 19, "Unexpected step count")
    w3, contract = connect(artifact_path)
    # Read the single necessary credential, not unrelated environment settings.
    key = next((line.split("=", 1)[1].strip().strip('\"').strip("'")
                for line in Path(env_file).read_text().splitlines()
                if line.startswith("ACHAT_CHAIN_RELAYER_KEY=")), "")
    signer = Account.from_key(key)
    del key
    require(signer.address == RELAYER, "Wrong relayer")
    observations = preflight_http(manifest)
    for agent_id in manifest["identities"].values():
        require(contract.functions.get(agent_id).call()[3] == 0, "Run identity already exists; do not repeat")
    before = w3.eth.block_number
    device_before = {a: {"balance": w3.eth.get_balance(a, before), "nonce": w3.eth.get_transaction_count(a, before)} for a in manifest["device_addresses"]}
    require(all(v == {"balance": 0, "nonce": 0} for v in device_before.values()), "Device is funded or previously active")
    print(json.dumps({"preflight": "passed", "chain_id": 71, "transactions": 19, "send": send}), flush=True)
    if not send:
        return
    out = Path(output)
    out.mkdir()  # no resume or overwrite; journal inspection is mandatory after interruption
    save(out / "http-before.json", observations)
    save(out / "environment.json", {"python": sys.version.split()[0], "web3": importlib.metadata.version("web3"),
        "eth-account": importlib.metadata.version("eth-account"), "rpc": RPC, "start_block": before,
        "device_before": device_before, "manifest_sha256": hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    budget = 0
    results = []
    for i, original in enumerate(manifest["steps"]):
        item = copy.deepcopy(original)
        if item["name"] == "relayer_forgery":
            item["args"][3] = signer.sign_message(encode_defunct(text=item["signed_message"])).signature.to_0x_hex()
        sig_index = 2 if item["function"] == "revoke" else 3
        recovered = Account.recover_message(encode_defunct(text=item["signed_message"]), signature=item["args"][sig_index])
        require(recovered == item["expected_message_signer"], "Message signature mismatch")
        call = getattr(contract.functions, item["function"])(*item["args"])
        block_before = w3.eth.block_number
        state_before = plain(contract.functions.get(item["args"][0]).call(block_identifier=block_before))
        reason = None
        try:
            call.call({"from": RELAYER}, block_identifier=block_before)
            require(item["expected_status"] == 1, "Attack unexpectedly accepted in preflight")
        except Exception as error:
            # Only retain allowlisted known revert text, never arbitrary exception arguments.
            reason = next((s for s in ["not owner key", "stale ts", "revoked"] if s in str(error)), None)
            require(item["expected_status"] == 0 and reason, "Unexpected preflight failure")
        gas = (call.estimate_gas({"from": RELAYER}) * 12 + 9)//10 if item["expected_status"] else 250_000
        price = w3.eth.gas_price
        budget += gas * price
        require(gas <= 800_000 and gas*price <= MAX_TX_FEE and budget <= MAX_RUN_FEE, "Budget exceeded")
        nonce = w3.eth.get_transaction_count(RELAYER, "pending")
        require(nonce == w3.eth.get_transaction_count(RELAYER, "latest"), "Relayer has pending transactions")
        balance_before = w3.eth.get_balance(RELAYER)
        require(balance_before >= gas*price, "Insufficient test funds")
        tx = call.build_transaction({"from": RELAYER, "chainId": 71, "nonce": nonce, "gas": gas, "gasPrice": price, "value": 0})
        signed = signer.sign_transaction(tx)
        txhash = Web3.keccak(signed.raw_transaction).to_0x_hex()
        require(w3.eth.get_transaction_count(RELAYER, "pending") == nonce, "Nonce changed before broadcast")
        prefix = f"{i+1:02d}-{item['name']}"
        save(out / f"{prefix}-submitted.json", {"step": item, "transaction": tx, "hash": txhash,
            "state_before": state_before, "block_before": block_before, "preflight_revert": reason})
        started = time.monotonic()
        require(w3.eth.send_raw_transaction(signed.raw_transaction).to_0x_hex() == txhash, "RPC hash mismatch")
        receipt = w3.eth.wait_for_transaction_receipt(txhash, timeout=55, poll_latency=2)
        save(out / f"{prefix}-receipt.json", plain(receipt))
        state_after = plain(contract.functions.get(item["args"][0]).call(block_identifier=receipt.blockNumber))
        require(receipt.status == item["expected_status"], "Unexpected receipt status")
        if not receipt.status:
            require(state_after == state_before, "Rejected transaction changed state")
        elif item["function"] == "anchor":
            a = item["args"]
            require(state_after == [recovered, "0x"+a[1], a[2], 1, a[4]], "Authorized anchor state mismatch")
        elif item["function"] == "rotateKey":
            expected_state = list(state_before)
            expected_state[0], expected_state[2] = item["args"][1], item["args"][2]
            require(state_after == expected_state, "Rotation state mismatch")
        else:
            expected_state = list(state_before)
            expected_state[2], expected_state[3] = item["args"][1], 2
            require(state_after == expected_state, "Revocation state mismatch")
        charged = max(receipt.gasUsed, (3*gas+3)//4)
        result = {"name": item["name"], "hash": txhash, "status": receipt.status,
            "block": receipt.blockNumber, "block_hash": receipt.blockHash.to_0x_hex(), "nonce": nonce,
            "gas_limit": gas, "gas_used": receipt.gasUsed, "gas_charged": charged, "gas_price": price,
            "fee_wei": charged*price, "balance_delta_wei": balance_before-w3.eth.get_balance(RELAYER),
            "receipt_observation_s": time.monotonic()-started, "state_after": state_after,
            "state_unchanged": state_after == state_before, "preflight_revert": reason,
            "message_signer": recovered, "transaction_sender": RELAYER}
        save(out / f"{prefix}-result.json", result)
        results.append(result)
        print(json.dumps({"completed": i+1, "name": item["name"], "status": receipt.status, "hash": txhash}), flush=True)
    end = results[-1]["block"]
    device_after = {a: {"balance": w3.eth.get_balance(a, end), "nonce": w3.eth.get_transaction_count(a, end)} for a in manifest["device_addresses"]}
    require(device_after == device_before, "Device balance/nonce changed")
    require(sum(r["status"] for r in results) == 14, "Wrong success count")
    save(out / "run-results.json", {"transactions": results, "end_block": end,
        "end_block_hash": results[-1]["block_hash"], "device_before": device_before, "device_after": device_after,
        "total_fee_wei": sum(r["fee_wei"] for r in results), "success": 14, "reverts": 5})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("cards")
    p.add_argument("output")
    p = sub.add_parser("prepare")
    p.add_argument("output")
    p.add_argument("--base-url", required=True)
    p = sub.add_parser("run")
    p.add_argument("manifest")
    p.add_argument("artifact")
    p.add_argument("--env-file", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--send", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "cards":
            prepare_cards(args.output)
        elif args.command == "prepare":
            prepare(args.output, args.base_url)
        else:
            run(args.manifest, args.artifact, args.env_file, args.output, args.send)
    except Exception as error:
        print(json.dumps({"stopped": type(error).__name__, "action": "Inspect public journals; do not automatically resubmit."}), file=sys.stderr)
        sys.exit(1)
