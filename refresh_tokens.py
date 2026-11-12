import json
import os
import sys
import time
import threading
from pathlib import Path
import requests

UID_FILE = Path("Uid_bd.json")
TOKEN_FILE = Path("token_bd.json")

# ✅ স্ক্রিনশটের দুটি API এবং Key ডিফল্ট হিসেবে যুক্ত
API_URL_1 = os.getenv("JWT_API_URL_1", "https://flash-token-api.vercel.app/token")
API_URL_2 = os.getenv("JWT_API_URL_2", "https://flash-token-v2.vercel.app/token")
API_KEY = os.getenv("JWT_API_KEY", "Flash")


def extract_token(data):
    """রেসপন্স থেকে মূল বড় JWT Token ফিল্ডটি বের করার ফাংশন"""
    if isinstance(data, str) and data.strip():
        return data.strip()
    if isinstance(data, dict):
        # বড় হাতের 'Token' সবার আগে চেক করা হচ্ছে
        for key in ("Token", "token", "jwt_token", "jwt", "Access_Token"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("data", "result", "response"):
            if key in data:
                value = extract_token(data[key])
                if value:
                    return value
    if isinstance(data, list):
        for item in data:
            value = extract_token(item)
            if value:
                return value
    return None


def main():
    if not UID_FILE.exists():
        print(f"ERROR: {UID_FILE} not found", file=sys.stderr)
        return 2

    try:
        accounts = json.loads(UID_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: Could not read {UID_FILE}: {e}", file=sys.stderr)
        return 2

    if not isinstance(accounts, list) or len(accounts) == 0:
        raise ValueError("Uid_bd.json must contain a non-empty JSON list")

    total_accs = len(accounts)
    print(f"[*] Loaded {total_accs} account(s) from {UID_FILE}")
    print(f"[*] API 1: {API_URL_1}")
    print(f"[*] API 2: {API_URL_2}")
    print("[*] Starting dual-speed token refresh (Start -> Middle <- End)...\n")

    # শেয়ার্ড পয়েন্টার ও থ্রেডিং লক
    left_ptr = 0
    right_ptr = total_accs - 1
    ptr_lock = threading.Lock()
    print_lock = threading.Lock()

    new_tokens = [None] * total_accs
    failed = []
    session = requests.Session()

    def process_account(idx, api_url, worker_name):
        account = accounts[idx]
        uid = str(account.get("uid", "")).strip()
        password = str(account.get("password", "")).strip()

        if not uid or not password:
            with print_lock:
                failed.append((idx + 1, uid or "<missing>", "missing uid/password"))
                print(f"[{worker_name}] [{idx+1}/{total_accs}] FAILED: missing uid/password", file=sys.stderr)
            return

        params = {
            "uid": uid,
            "password": password,
            "key": API_KEY
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": "OB55-Token-Refresh/2.0"
        }

        try:
            resp = session.get(api_url, params=params, headers=headers, timeout=25)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError:
                data = resp.text

            token = extract_token(data)
            if not token:
                raise ValueError("Response did not contain valid 'Token'")

            new_tokens[idx] = {"token": token}
            with print_lock:
                print(f"[{worker_name}] [{idx+1}/{total_accs}] OK {uid}")

        except Exception as exc:
            with print_lock:
                failed.append((idx + 1, uid, str(exc)))
                print(f"[{worker_name}] [{idx+1}/{total_accs}] FAILED {uid}: {exc}", file=sys.stderr)

    # Worker 1: শুরু থেকে সামনের দিকে
    def worker_start():
        nonlocal left_ptr, right_ptr
        while True:
            with ptr_lock:
                if left_ptr > right_ptr:
                    break
                idx = left_ptr
                left_ptr += 1
            process_account(idx, API_URL_1, "API-1 (Start)")
            time.sleep(0.15)

    # Worker 2: শেষ থেকে পেছনের দিকে
    def worker_end():
        nonlocal left_ptr, right_ptr
        while True:
            with ptr_lock:
                if left_ptr > right_ptr:
                    break
                idx = right_ptr
                right_ptr -= 1
            process_account(idx, API_URL_2, "API-2 (End)")
            time.sleep(0.15)

    # ডুয়াল থ্রেড চালু করা
    t1 = threading.Thread(target=worker_start)
    t2 = threading.Thread(target=worker_end)

    start_time = time.time()
    t1.start()
    t2.start()

    t1.join()
    t2.join()
    elapsed = round(time.time() - start_time, 2)

    # সাকসেসফুল টোকেন ফিল্টার করা
    valid_tokens = [t for t in new_tokens if t is not None]

    print("\n" + "=" * 50)
    print(f"Finished in {elapsed}s | Success: {len(valid_tokens)}/{total_accs} | Failed: {len(failed)}")
    print("=" * 50)

    # যদি কিছু ফেইলও হয় কিন্তু মেজরিটি সাকসেসফুল থাকে, ফাইল সেভ করা
    if len(valid_tokens) == 0:
        print(f"[!] No valid tokens obtained; keeping existing {TOKEN_FILE}.", file=sys.stderr)
        return 1

    tmp = TOKEN_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(valid_tokens, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    tmp.replace(TOKEN_FILE)
    print(f"[✓] Successfully refreshed {len(valid_tokens)} tokens into {TOKEN_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())