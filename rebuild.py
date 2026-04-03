import json
import sqlite3
import hashlib
import os
import time

def get_scripthash(hex_script):
    script_bytes = bytes.fromhex(hex_script)
    sha256_hash = hashlib.sha256(script_bytes).digest()
    return sha256_hash[::-1].hex()

def rebuild():
    json_file = 'p2pk_map.json'
    db_file = 'p2pk_data.db'
    
    if not os.path.exists(json_file):
        print(f"오류: {json_file} 파일을 찾을 수 없습니다.")
        return

    if os.path.exists(db_file): os.remove(db_file)
    
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute('CREATE TABLE p2pk (address TEXT, script TEXT, scripthash TEXT)')
    
    print(f"[{time.ctime()}] JSON 로드 중...")
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    total = len(data)
    print(f"[{time.ctime()}] 총 {total}개의 데이터를 DB에 삽입합니다.")
    
    count = 0
    batch = []
    for addr, script in data.items():
        # 스크립트가 41...ac 형태인지 확인하고 scripthash 계산
        clean_script = script.strip().lower()
        sh = get_scripthash(clean_script)
        batch.append((addr, clean_script, sh))
        
        count += 1
        if len(batch) >= 5000:
            cur.executemany('INSERT INTO p2pk VALUES (?, ?, ?)', batch)
            conn.commit()
            batch = []
            print(f"진행 중... {count}/{total} ({(count/total)*100:.1f}%)")
    
    if batch: 
        cur.executemany('INSERT INTO p2pk VALUES (?, ?, ?)', batch)
        conn.commit()

    print(f"[{time.ctime()}] 인덱스 생성 중 (가장 중요한 단계)...")
    cur.execute('CREATE INDEX idx_addr ON p2pk (address)')
    cur.execute('CREATE INDEX idx_scr ON p2pk (script)')
    cur.execute('CREATE INDEX idx_sh ON p2pk (scripthash)')
    
    conn.close()
    print(f"[{time.ctime()}] 완료: {count}개의 데이터가 p2pk_data.db에 저장되었습니다.")

if __name__ == "__main__":
    rebuild()
