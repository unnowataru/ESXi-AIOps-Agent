import os
import re
import json
import time
import sys
from typing import List, Dict, Any, Optional

import paramiko
from playwright.sync_api import sync_playwright
from google import genai

# =========================
# 設定ロード & バリデーション
# =========================

try:
    import local_config
except ImportError:
    print("[CRITICAL] local_config.py が見つかりません。")
    sys.exit(1)

def get_conf(key: str, default: Any = None) -> Any:
    """local_config または 環境変数から値を取得"""
    # 1. 環境変数を優先 (CI/CD対応)
    env_val = os.environ.get(key)
    if env_val is not None:
        return env_val
    
    # 2. local_config の値を参照
    if hasattr(local_config, key):
        return getattr(local_config, key)
    
    # 3. デフォルト値
    return default

# 必須パラメータの読み込み
CFG_HOST = get_conf("ESXI_HOST")
CFG_USER = get_conf("ESXI_USER")
CFG_PASS = get_conf("ESXI_PASS")
CFG_API_KEY = get_conf("GEMINI_API_KEY")

# オプションパラメータの読み込み
CFG_SSH_PORT = int(get_conf("ESXI_SSH_PORT", 22))
CFG_SSH_TIMEOUT = int(get_conf("ESXI_SSH_TIMEOUT", 10))
CFG_UI_URL = get_conf("ESXI_UI_URL") or f"https://{CFG_HOST}/ui/#/host"

CFG_MODEL = get_conf("GEMINI_MODEL", "gemini-2.0-flash")
CFG_MAX_RETRIES = int(get_conf("GEMINI_MAX_RETRIES", 3))
CFG_RETRY_DELAY = int(get_conf("GEMINI_RETRY_DELAY", 2))

CFG_HEADLESS = get_conf("BROWSER_HEADLESS", False)
CFG_VIEWPORT = get_conf("BROWSER_VIEWPORT", {"width": 1280, "height": 720})
CFG_BROWSER_TIMEOUT = int(get_conf("BROWSER_TIMEOUT", 15000))
CFG_LOGIN_WAIT = int(get_conf("BROWSER_LOGIN_WAIT", 3000))

CFG_DEFAULT_VM = get_conf("DEFAULT_VM_NAME", "ubuntu01")
CFG_SNAP_MEM = get_conf("SNAPSHOT_MEMORY", 0)
CFG_SNAP_QUIESCE = get_conf("SNAPSHOT_QUIESCE", 0)

CFG_PROMPT = get_conf("SYSTEM_PROMPT", "")

def validate_config():
    missing = []
    if not CFG_HOST: missing.append("ESXI_HOST")
    if not CFG_USER: missing.append("ESXI_USER")
    if not CFG_PASS: missing.append("ESXI_PASS")
    if not CFG_API_KEY: missing.append("GEMINI_API_KEY")
    
    if missing:
        print(f"[FATAL] 設定不足: {', '.join(missing)}")
        sys.exit(1)

# =========================
# SSH / ESXi 操作モジュール
# =========================

def ssh_run(command: str) -> str:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            CFG_HOST,
            port=CFG_SSH_PORT,
            username=CFG_USER,
            password=CFG_PASS,
            look_for_keys=False,
            allow_agent=False,
            timeout=CFG_SSH_TIMEOUT
        )
        stdin, stdout, stderr = client.exec_command(command)
        out = stdout.read().decode("utf-8", errors="ignore")
        err = stderr.read().decode("utf-8", errors="ignore")
        
        # エラーハンドリング: stderrがあり、かつstdoutが空の場合は異常とみなす
        if err and not out:
             raise RuntimeError(f"SSH stderr: {err.strip()}")
        return out
    except Exception as e:
        raise RuntimeError(f"SSH connection failed to {CFG_HOST}:{CFG_SSH_PORT} - {e}")
    finally:
        client.close()

def list_vms() -> str:
    return ssh_run("vim-cmd vmsvc/getallvms")

def get_vm_id(vm_name: str) -> str:
    out = list_vms()
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("Vmid"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        vmid, name = parts[0], parts[1]
        if name == vm_name:
            return vmid
    raise RuntimeError(f"VM '{vm_name}' not found.")

def get_power_state(vmid: str) -> str:
    out = ssh_run(f"vim-cmd vmsvc/power.getstate {vmid}")
    for line in out.splitlines():
        if "Powered" in line:
            return line.strip()
    raise RuntimeError(f"Failed to get power state for VMID {vmid}")

def power_off_vm(vmid: str):
    state = get_power_state(vmid)
    if "Powered off" in state:
        print(f"[INFO] VM {vmid} is already off.")
        return
    ssh_run(f"vim-cmd vmsvc/power.off {vmid}")
    print(f"[INFO] Power off command sent: VMID={vmid}")
    time.sleep(5)

def power_on_vm(vmid: str):
    state = get_power_state(vmid)
    if "Powered on" in state:
        print(f"[INFO] VM {vmid} is already on.")
        return
    ssh_run(f"vim-cmd vmsvc/power.on {vmid}")
    print(f"[INFO] Power on command sent: VMID={vmid}")
    time.sleep(5)

def create_snapshot(vmid: str, name: str, description: str):
    # 設定ファイルからオプション値を参照
    cmd = f'vim-cmd vmsvc/snapshot.create {vmid} "{name}" "{description}" {CFG_SNAP_MEM} {CFG_SNAP_QUIESCE}'
    ssh_run(cmd)
    print(f"[INFO] Snapshot created: VMID={vmid}, Name={name}")

def resolve_vmid(act: Dict[str, Any], last_vmid: Optional[str]) -> str:
    vmid = act.get("vm_id")
    if vmid and str(vmid).strip().isdigit():
        return str(vmid).strip()
    
    if last_vmid and str(last_vmid).strip().isdigit():
        return str(last_vmid).strip()

    raise RuntimeError("Valid VMID not provided and could not rely on context.")

# =========================
# UI 操作モジュール (Playwright)
# =========================

def open_esxi_ui():
    p = sync_playwright().start()
    # 設定ファイルからヘッドレス設定を反映
    browser = p.chromium.launch(headless=CFG_HEADLESS)
    context = browser.new_context(
        ignore_https_errors=True,
        viewport=CFG_VIEWPORT,
    )
    page = context.new_page()

    print(f"[UI] Navigating to {CFG_UI_URL} ...")
    try:
        page.goto(CFG_UI_URL, wait_until="load", timeout=CFG_BROWSER_TIMEOUT)
    except Exception as e:
        print(f"[WARN] Page load timeout/error: {e}")

    try:
        page.fill("#username", CFG_USER)
        page.fill("#password", CFG_PASS)
        
        try:
            page.click("#login")
        except Exception:
            page.get_by_role("button", name=re.compile("ログイン|Log in", re.I)).click()
        
        page.wait_for_timeout(CFG_LOGIN_WAIT)
        print("[UI] Login attempt finished.")
    except Exception as e:
        print(f"[ERROR] UI Login failed: {e}")

    return p, browser, page

# =========================
# Gemini AI モジュール
# =========================

def build_gemini_client() -> genai.Client:
    return genai.Client(api_key=CFG_API_KEY)

def parse_json_response(text: str) -> dict:
    raw = text.strip()
    if not raw:
        raise RuntimeError("Empty response from AI")

    # Clean up Markdown block
    if raw.startswith("```"):
        m = re.search(r"```(?:json)?\s*(.*)```", raw, re.DOTALL | re.IGNORECASE)
        if m:
            raw = m.group(1).strip()

    # Fallback extraction
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"actions": [], "reply": text}

def call_gemini(client: genai.Client, user_text: str, history: List[Dict]) -> Dict:
    messages = [{"role": "user", "parts": [{"text": CFG_PROMPT}]}]
    messages += history
    messages.append({"role": "user", "parts": [{"text": user_text}]})

    for attempt in range(1, CFG_MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(
                model=CFG_MODEL,
                contents=messages,
            )
            return parse_json_response(resp.text or "")
        except Exception as e:
            print(f"[AI] Error (Attempt {attempt}/{CFG_MAX_RETRIES}): {e}")
            if attempt == CFG_MAX_RETRIES:
                raise
            time.sleep(CFG_RETRY_DELAY)
    return {}

# =========================
# Main Loop
# =========================

def main():
    validate_config()
    print(f"[INIT] Host: {CFG_HOST}, Model: {CFG_MODEL}")

    # UI起動
    p, browser, page = open_esxi_ui()
    
    # AIクライアント起動
    try:
        client = build_gemini_client()
    except Exception as e:
        print(f"[FATAL] Gemini Client Init Failed: {e}")
        browser.close()
        p.stop()
        return

    history: List[Dict[str, Any]] = []
    last_vmid: Optional[str] = None

    print("\n=== ESXi AIOps Agent Started ===")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input("esxi> ").strip()
        except EOFError:
            break

        if not user_input: continue
        if user_input.lower() in ("exit", "quit"): break

        # AI推論
        try:
            plan = call_gemini(client, user_input, history)
        except Exception as e:
            print(f"[ERROR] AI communication failed: {e}")
            continue

        # 結果の解析
        actions = plan.get("actions", [])
        reply = plan.get("reply", "")

        if reply:
            print(f"[AI] {reply}")

        # アクション実行
        for act in actions:
            tool = act.get("tool")
            try:
                if tool == "list_vms":
                    print(list_vms())
                
                elif tool == "get_vm_id":
                    name = act.get("vm_name") or CFG_DEFAULT_VM
                    last_vmid = get_vm_id(name)
                    print(f"[OK] VMID found: {last_vmid} ({name})")
                
                elif tool == "get_power_state":
                    vmid = resolve_vmid(act, last_vmid)
                    print(f"[OK] {get_power_state(vmid)}")
                
                elif tool == "power_off_vm":
                    vmid = resolve_vmid(act, last_vmid)
                    power_off_vm(vmid)
                
                elif tool == "power_on_vm":
                    vmid = resolve_vmid(act, last_vmid)
                    power_on_vm(vmid)
                
                elif tool == "create_snapshot":
                    vmid = resolve_vmid(act, last_vmid)
                    name = act.get("name") or "AutoSnap"
                    desc = act.get("description") or ""
                    create_snapshot(vmid, name, desc)
                
                else:
                    print(f"[WARN] Unknown tool: {tool}")

            except Exception as e:
                print(f"[EXEC ERROR] Tool '{tool}' failed: {e}")

        # 履歴更新
        history.append({"role": "user", "parts": [{"text": user_input}]})
        if reply:
            history.append({"role": "model", "parts": [{"text": reply}]})

    print("Shutting down...")
    browser.close()
    p.stop()

if __name__ == "__main__":
    main()