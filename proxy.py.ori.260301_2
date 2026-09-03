import requests
import sqlite3
import time
import json
import subprocess
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

# --- [설정 변수] ---
ELECTRS_URL = "http://127.0.0.1:3002"
RPC_CMD = ["/root/bitever/src/bitcoin-cli", "-datadir=/root/myfork", "-rpcuser=user", "-rpcpassword=pass", "-rpcport=8334"]
DB_FILE = "p2pk_data.db"
CACHE_FILE = "p2pk_scan_results.json"
CACHE_TTL = 300

SATOSHI_GENESIS_ADDR = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
SATOSHI_GENESIS_TXID = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
GENESIS_REWARD_SATS = 5000000000

# 캐시 로드
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r") as f: SCAN_CACHE = json.load(f)
    except: SCAN_CACHE = {}
else: SCAN_CACHE = {}

def get_db_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def resolve_p2pk_info(input_val):
    val = input_val.lower().strip()
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM p2pk WHERE address = ? OR script = ? OR script = ?", 
                (input_val, f"41{val}ac", f"21{val}ac"))
    res = cur.fetchone()
    conn.close()
    return res

def is_hex_pubkey(val):
    v = val.lower().strip()
    return (len(v) == 66 and v.startswith(('02', '03'))) or (len(v) == 130 and v.startswith('04'))

def get_rpc_utxo_data(address, script):
    """scantxoutset를 통해 실제 노드의 UTXO 잔액을 확인합니다."""
    now = time.time()
    if address in SCAN_CACHE:
        entry = SCAN_CACHE[address]
        if isinstance(entry, dict) and now - entry.get("timestamp", 0) < CACHE_TTL:
            return entry.get("data")
    try:
        subprocess.run(RPC_CMD + ["scantxoutset", "abort"], capture_output=True)
        time.sleep(0.1)
        res = subprocess.check_output(RPC_CMD + ["scantxoutset", "start", f'["raw({script})"]'])
        result = json.loads(res)
        if result.get("success"):
            SCAN_CACHE[address] = {"timestamp": now, "data": result}
            with open(CACHE_FILE, "w") as f: json.dump(SCAN_CACHE, f, indent=4)
            return result
    except: return None
    return None

# --- [API 엔드포인트] ---

@app.get("/api/address/{address}")
async def get_address(address: str):
    is_pubkey = is_hex_pubkey(address)
    p2pk_info = resolve_p2pk_info(address)
    target_addr = p2pk_info['address'] if p2pk_info else address
    
    # 1. 기초 데이터 생성
    if is_pubkey:
        data = {"address": address, "chain_stats": {"funded_txo_sum": 0, "tx_count": 0, "spent_txo_sum": 0, "funded_txo_count": 0}, "mempool_stats": {"funded_txo_sum": 0, "tx_count": 0, "spent_txo_sum": 0, "funded_txo_count": 0}}
    else:
        resp = requests.get(f"{ELECTRS_URL}/address/{target_addr}")
        data = resp.json()

    # 2. P2PK 잔액 합산 (RPC 기반 - 확실한 잔액)
    if p2pk_info:
        rpc_data = get_rpc_utxo_data(target_addr, p2pk_info['script'])
        if rpc_data:
            p2pk_sats = int(rpc_data.get("total_amount", 0) * 100000000)
            p2pk_count = len(rpc_data.get("unspents", []))
            data["chain_stats"]["funded_txo_sum"] += p2pk_sats
            data["chain_stats"]["tx_count"] += p2pk_count
            data["chain_stats"]["funded_txo_count"] += p2pk_count

    # 3. 제네시스 보정
    if target_addr == SATOSHI_GENESIS_ADDR:
        data["chain_stats"]["funded_txo_sum"] += GENESIS_REWARD_SATS
        data["chain_stats"]["tx_count"] += 1
        data["chain_stats"]["funded_txo_count"] += 1

    return data

@app.get("/api/address/{address}/{sub_path:path}")
async def proxy_address_subpath(address: str, sub_path: str):
    is_pubkey = is_hex_pubkey(address)
    p2pk_info = resolve_p2pk_info(address)
    target_addr = p2pk_info['address'] if p2pk_info else address

    # P2PKH 거래 목록 (Electrs)
    electrs_data = [] if is_pubkey else requests.get(f"{ELECTRS_URL}/address/{target_addr}/{sub_path}").json()

    # P2PK 거래 목록 및 UTXO
    extra_data = []
    if p2pk_info:
        # 과거 거래는 scripthash로, 현재 잔액은 RPC 결과로 보완
        sh_res = requests.get(f"{ELECTRS_URL}/scripthash/{p2pk_info['scripthash']}/{sub_path}")
        if sh_res.status_code == 200:
            extra_data = sh_res.json()
        
        # [중요] Electrs가 놓친 UTXO(Coinbase 등)를 RPC 결과에서 수동 추가
        if sub_path == "utxo" or sub_path == "txs":
            rpc_data = get_rpc_utxo_data(target_addr, p2pk_info['script'])
            if rpc_data:
                for item in rpc_data.get("unspents", []):
                    if not any(x['txid'] == item['txid'] for x in extra_data):
                        if sub_path == "utxo":
                            extra_data.append({"txid": item["txid"], "vout": item["vout"], "value": int(item["amount"] * 100000000), "status": {"confirmed": True, "block_height": item["height"]}})
                        else:
                            # txs 요청 시 트랜잭션 상세 정보 생성
                            try:
                                raw_tx = subprocess.check_output(RPC_CMD + ["getrawtransaction", item["txid"], "1"])
                                tx_info = json.loads(raw_tx)
                                # coinbase 트랜잭션 규격 보정 (undefined:undefined 방지)
                                if "vin" in tx_info and len(tx_info["vin"]) > 0 and "coinbase" in tx_info["vin"][0]:
                                    vins = [{"coinbase": tx_info["vin"][0]["coinbase"], "sequence": 4294967295}]
                                else: vins = tx_info.get("vin", [])
                                
                                vouts = []
                                for vo in tx_info.get("vout", []):
                                    vouts.append({"value": int(vo["value"] * 100000000), "scriptpubkey": vo["scriptPubKey"].get("hex", ""), "scriptpubkey_type": vo["scriptPubKey"].get("type", ""), "scriptpubkey_address": vo["scriptPubKey"].get("address", "")})
                                
                                extra_data.append({"txid": item["txid"], "version": tx_info["version"], "locktime": tx_info["locktime"], "vin": vins, "vout": vouts, "status": {"confirmed": True, "block_height": item["height"], "block_hash": tx_info.get("blockhash")}, "fee": 0})
                            except: pass

    # 제네시스 특수 처리
    if target_addr == SATOSHI_GENESIS_ADDR:
        if not any(x['txid'] == SATOSHI_GENESIS_TXID for x in extra_data):
            if sub_path == "utxo":
                extra_data.append({"txid": SATOSHI_GENESIS_TXID, "vout": 0, "value": GENESIS_REWARD_SATS, "status": {"confirmed": True, "block_height": 0}})
            elif sub_path == "txs":
                extra_data.append({"txid": SATOSHI_GENESIS_TXID, "version": 1, "locktime": 0, "vin": [{"coinbase": "04ffff001d0104455468652054696d65732030332f4a616e2f32303039204368616e63656c6c6f72206f6e206272696e6b206f66207365636f6e64206261696c6f757420666f722062616e6b73", "sequence": 4294967295}], "vout": [{"value": GENESIS_REWARD_SATS, "scriptpubkey": p2pk_info['script'] if p2pk_info else "", "scriptpubkey_type": "p2pk", "scriptpubkey_address": SATOSHI_GENESIS_ADDR}], "status": {"confirmed": True, "block_height": 0, "block_hash": "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"}, "fee": 0})

    return (electrs_data if isinstance(electrs_data, list) else []) + extra_data

@app.get("/api/{path:path}")
async def catch_all(path: str, request: Request):
    resp = requests.get(f"{ELECTRS_URL}/{path}", params=request.query_params)
    try: return JSONResponse(content=resp.json())
    except: return JSONResponse(content={})
