import os

# ==========================================
# 1. VMware ESXi 接続設定
# ==========================================
# 必須設定
ESXI_HOST = "192.168.0.0"
ESXI_USER = "root"
ESXI_PASS = "パスワード"

# オプション設定
ESXI_SSH_PORT = 22
ESXI_SSH_TIMEOUT = 10  # 秒

# UI接続用URL (Noneの場合は https://<HOST>/ui/#/host を自動生成)
ESXI_UI_URL = None 

# ==========================================
# 2. Google Gemini API 設定
# ==========================================
# 必須設定
GEMINI_API_KEY = "APIキー"

# モデル設定
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MAX_RETRIES = 3
GEMINI_RETRY_DELAY = 2  # 秒

# ==========================================
# 3. Playwright (ブラウザ) 設定
# ==========================================
BROWSER_HEADLESS = False       # Trueなら画面を表示せずに実行
BROWSER_VIEWPORT = {"width": 1280, "height": 720}
BROWSER_TIMEOUT = 15000        # ミリ秒
BROWSER_LOGIN_WAIT = 3000      # ログイン後の待機時間(ミリ秒)

# ==========================================
# 4. AIOps 運用デフォルト値
# ==========================================
DEFAULT_VM_NAME = "ubuntu01"

# スナップショット設定
SNAPSHOT_MEMORY = 0  # 1=メモリも含める, 0=含めない
SNAPSHOT_QUIESCE = 0 # 1=静止点を作成, 0=しない

# ==========================================
# 5. システムプロンプト (AIの頭脳定義)
# ==========================================
SYSTEM_PROMPT = """
あなたは ESXi ホスト を SSH 経由で操作する SRE アシスタントです。
ユーザーの日本語の要望を受け取り、実行すべき ESXi コマンドのシーケンスを JSON で返してください。

出力は必ず次の JSON フォーマット「のみ」とします（前後に余計な文字を付けてはいけません）:

{
  "actions": [
    { "tool": "<tool_name>", ...params... }
  ],
  "reply": "<ユーザーへの簡単な説明>"
}

利用可能な tool_name とパラメータ:
1. "list_vms" (引数なし): 全VM一覧を取得。
2. "get_vm_id" (引数: "vm_name"): VM名からIDを取得。
3. "get_power_state" (引数: "vm_id"): 電源状態を確認。
4. "power_off_vm" (引数: "vm_id"): VMを停止。
5. "power_on_vm" (引数: "vm_id"): VMを起動。
6. "create_snapshot" (引数: "vm_id", "name", 任意 "description"): スナップショット作成。

制約事項:
- "vm_id" は必ず数値文字列を使用すること。不明な場合は直前で get_vm_id を呼ぶこと。
- 危険な操作の前にはユーザーに確認を促すような reply を含めること。
"""