import json
import sqlite3
import hashlib
import os

def get_scripthash(hex_script):
    script_bytes = bytes.fromhex(hex_script)
    sha256_hash = hashlib.sha256(script_bytes).digest()
    return sha256_hash[::-1].hex()

def convert():
    json_file = 'p2pk_map.json'
    db_file = 'p2pk_data.db'
    
    if os.path.exists(db_file): os.remove(db_file)
    
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute('CREATE TABLE p2pk (address TEXT, script TEXT, scripthash TEXT)')
    
    print("JSON 로드 중...")
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    print("DB 삽입 중 (이 과정은 시간이 조금 걸릴 수 있습니다)...")
    batch = []
    for addr, script in data.items():
        sh = get_scripthash(script)
        batch.append((addr, script, sh))
        if len(batch) >= 10000:
            cur.executemany('INSERT INTO p2pk VALUES (?, ?, ?)', batch)
            batch = []
    
    if batch: cur.executemany('INSERT INTO p2pk VALUES (?, ?, ?)', batch)
    
    print("인덱스 생성 중 (검색 속도의 핵심)...")
    cur.execute('CREATE INDEX idx_address ON p2pk (address)')
    cur.execute('CREATE INDEX idx_script ON p2pk (script)')
    cur.execute('CREATE INDEX idx_scripthash ON p2pk (scripthash)')
    
    conn.commit()
    conn.close()
    print("변환 완료: p2pk_data.db 생성됨.")

if __name__ == "__main__":
    convert()
