# ESXi AIOps Agent (Powered by Gemini)

Google Gemini (生成AI) を用いて、自然言語で VMware ESXi ホストを操作・管理する AIOps エージェントです。
SSH によるコマンド実行と、Playwright による Web UI ログインを組み合わせて、インフラ運用を自動化します。

## 🚀 特徴

  - **自然言語インターフェース:** 「VMの一覧を見せて」「ubuntu01を再起動して」といった日本語の指示で操作可能。
  - **自律的なプランニング:** Gemini がユーザーの意図を理解し、必要なコマンド (VMID特定 → 状態確認 → 実行) を自動で組み立てます。
  - **ハイブリッド操作:** SSH (paramiko) と ブラウザ自動操作 (playwright) の両方を使用します。

## 📋 前提条件 (Prerequisites)

  - **OS:** Windows, macOS, または Linux
  - **VMware ESXi:** SSH サービスが有効になっていること
  - **Google Account:** Google AI Studio の API Key (Gemini)

-----

## 🛠️ インストール手順 (Installation)

ゼロから環境構築を行う手順です。

### Step 0: Python 3.x のインストール

このツールを実行するには Python が必要です。まだインストールしていない場合は、以下の手順で行ってください。

**Windows の場合:**

1.  [Python 公式サイト](https://www.python.org/downloads/) から最新のインストーラー ("Download Python 3.x.x") をダウンロードします。
2.  インストーラーを起動し、**必ず "Add Python to PATH" にチェックを入れてから** "Install Now" をクリックします。
    > ※ "Add to PATH" を忘れると、コマンドラインで `python` が使えません。

**macOS の場合:**

  - Homebrew を使用する場合: `brew install python`
  - または [Python 公式サイト](https://www.python.org/downloads/macos/) からインストーラーを使用してください。

確認のため、ターミナル(またはコマンドプロンプト)で以下を実行し、バージョンが表示されればOKです。

```bash
python --version
# または python3 --version
```

### Step 1: プロジェクトの準備

このリポジトリをダウンロード（または `git clone`）し、そのフォルダに移動します。

```bash
cd esxi-aiops-agent
```

### Step 2: 仮想環境 (venv) の作成

システム環境を汚さないために、このプロジェクト専用の部屋（仮想環境）を作成します。

**Windows (PowerShell) の場合:**

```powershell
# 仮想環境を作成
python -m venv venv

# 仮想環境を有効化
.\venv\Scripts\activate
```

**macOS / Linux の場合:**

```bash
# 仮想環境を作成
python3 -m venv venv

# 仮想環境を有効化
source venv/bin/activate
```

> **成功確認:** ターミナルの行頭に `(venv)` と表示されていればOKです。

### Step 3: ライブラリの一括インストール

`requirements.txt` に記載された必要なライブラリ（`paramiko`, `playwright`, `google-genai`）を一括でインストールします。

```bash
pip install -r requirements.txt
```

### Step 4: Playwright ブラウザのセットアップ

Web UI 操作に必要なブラウザ本体 (Chromium) をダウンロードします。これを行わないとエラーになります。

```bash
playwright install chromium
```

-----

## ⚙️ 設定 (Configuration)

セキュリティのため、IPアドレスやパスワードはコードに直書きせず、設定ファイルで管理します。

1.  プロジェクトフォルダ内に `local_config.py` という名前でファイルを新規作成します。
2.  以下の内容をコピーし、ご自身の環境に合わせて書き換えて保存してください。

<!-- end list -->

```python
# local_config.py

# ==========================================
# 1. VMware ESXi 接続設定 (必須)
# ==========================================
ESXI_HOST = "192.168.1.50"      # ESXiのIPアドレス
ESXI_USER = "root"              # ログインユーザー名
ESXI_PASS = "YourPassword!"     # ログインパスワード

# ==========================================
# 2. Google Gemini API 設定 (必須)
# ==========================================
# Google AI Studio で取得したキーを入力
GEMINI_API_KEY = "AIzaSy..."

# ==========================================
# 3. オプション設定 (任意)
# ==========================================
# SSH設定
ESXI_SSH_PORT = 22

# ブラウザ設定 (Trueにすると画面を表示せずに実行)
BROWSER_HEADLESS = False

# デフォルトVM名 (省略時に使用)
DEFAULT_VM_NAME = "ubuntu01"
```

> **⚠️ 重要:** `local_config.py` には機密情報が含まれます。Git 等でバージョン管理しないよう、`.gitignore` に追加されています。

-----

## ▶️ 実行方法 (Usage)

仮想環境が有効 (`(venv)`) な状態で、以下のコマンドを実行します。

```bash
python esxi_aiops.py
```

### 操作の流れ

1.  **起動:** ブラウザが立ち上がり、ESXi UI への自動ログインが行われます。
2.  **対話:** コンソールに `esxi>` プロンプトが表示されます。
3.  **指示:** 日本語で指示を入力してください。

**コマンド例:**

```text
esxi> 現在のVM一覧を表示して
esxi> ubuntu01 の電源状態はどうなってる？
esxi> ubuntu01 をシャットダウンして
esxi> web-server-01 のスナップショットをとって。名前は「作業前バックアップ」で。
```

4.  **終了:** `exit` または `quit` と入力すると終了し、ブラウザも閉じます。

-----

## 📂 ファイル構成

```text
.
├── esxi_aiops.py       # メインプログラム (ロジック本体)
├── requirements.txt    # 必要なライブラリリスト
├── README.md           # 本説明書
├── .gitignore          # Git除外設定
└── local_config.py     # ★ユーザーが作成する設定ファイル (除外対象)
```

## ⚠️ 免責事項

本ツールは ESXi ホストに対し、電源操作（起動・停止）やスナップショット作成などの変更操作を自動で行います。
意図しない操作によるデータ損失やシステムの不具合について、開発者は一切の責任を負いません。必ず検証環境で動作を確認してから使用してください。
