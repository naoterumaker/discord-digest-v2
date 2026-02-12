# discord-digest-v2

OpenClaw / Clawdbot 用のDiscordダイジェスト生成スキル。  
外部Pythonスクリプトでメッセージを取得し、LLMコンテキストを汚さずに大量データを安全に処理・要約します。

## 概要

従来のサブエージェント方式ではDiscord APIを叩くとコンテキストオーバーフロー（200K+ tokens）が発生していました。

**このスキルの解決策:**
1. `exec` で外部Pythonスクリプト（`discord_fetcher.py`）を実行
2. メッセージがJSONファイルに保存される（LLMコンテキスト外）
3. エージェントがファイルを1ページずつ読んで要約を生成
4. 最終ダイジェストをMarkdownで出力

## セットアップ

### 前提条件

- Python 3.8+
- OpenClaw / Clawdbot が動作している環境
- Discord Bot トークン

### 1. discord.py のインストール

```bash
pip install discord.py
```

### 2. スクリプトの配置

```bash
# スクリプトをワークスペースに配置
cp discord_fetcher.py ~/clawd/scripts/discord_fetcher.py
chmod +x ~/clawd/scripts/discord_fetcher.py
```

### 3. スキルの配置

```bash
# スキル定義を配置
mkdir -p ~/clawd/skills/discord-digest-v2
cp SKILL.md ~/clawd/skills/discord-digest-v2/SKILL.md
```

### 4. Discord Bot トークンの設定

トークンは以下の順序で自動取得されます：

1. 環境変数 `DISCORD_BOT_TOKEN`（あれば優先）
2. `~/.clawdbot/clawdbot.json` の `channels.discord.token`

OpenClawでDiscord連携を設定済みなら、追加設定は不要です。

## 使い方

### 基本的な使い方

エージェントに以下のように依頼するだけです：

```
2月9日から12日のダイジェスト作って
```

```
#質問チャンネル の1月分をまとめて
```

### 手動でスクリプトを実行する場合

```bash
python3 discord_fetcher.py \
  --channel 977473910402609162 \
  --start 2026-01-01 \
  --end 2026-01-31 \
  --output ~/clawd/discord-data/job-001
```

### オプション

| オプション | 必須 | 説明 |
|-----------|------|------|
| `--channel` | ✅ | Discord チャンネルID |
| `--start` | ✅ | 開始日 (YYYY-MM-DD) |
| `--end` | ✅ | 終了日 (YYYY-MM-DD) |
| `--output` | - | 出力ディレクトリ（デフォルト: `~/clawd/discord-data/<channel>-<start>`） |

## ファイル構造

```
~/clawd/
├── scripts/
│   └── discord_fetcher.py       # データ取得スクリプト
├── skills/
│   └── discord-digest-v2/
│       └── SKILL.md             # スキル定義
├── discord-data/                 # 取得した生データ
│   └── <job_id>/
│       ├── manifest.json         # メタデータ（ステータス、件数等）
│       ├── page-0001.json        # 1ページ目（最大100件）
│       ├── page-0002.json
│       └── ...
└── discord-digests/              # 生成したダイジェスト
    └── <date>/
        └── final-digest.md       # 最終ダイジェスト
```

## 出力形式

### manifest.json

```json
{
  "channel_id": "977473910402609162",
  "channel_name": "収益剥奪や収益審査の情報交換",
  "start_date": "2026-01-01T00:00:00+00:00",
  "end_date": "2026-01-31T23:59:59+00:00",
  "total_pages": 15,
  "total_messages": 1423,
  "fetched_at": "2026-02-04T06:30:00+00:00",
  "status": "completed"
}
```

### page-NNNN.json

```json
[
  {
    "id": "1234567890",
    "author": "username",
    "author_display_name": "Display Name",
    "author_id": "9876543210",
    "content": "メッセージ本文",
    "timestamp": "2026-01-15T10:30:00+00:00",
    "attachments": [{"url": "...", "filename": "..."}],
    "embeds": [{"title": "...", "description": "..."}],
    "reactions": [{"emoji": "👍", "count": 5}],
    "reply_to": "1234567889"
  }
]
```

## トラブルシューティング

| エラー | 原因 | 対処法 |
|--------|------|--------|
| `Channel not found` | チャンネルIDが間違っている | チャンネルIDを確認 |
| `No permission` | Botがチャンネルにアクセスできない | Bot権限を確認 |
| `DISCORD_BOT_TOKEN not set` | トークンが見つからない | 環境変数を設定するか、clawdbot.jsonを確認 |

## 注意事項

- 1ページ = 最大100メッセージ
- レート制限対策として0.5秒間隔でリクエスト
- 1ヶ月分の大量データ（数千件）は取得に5〜10分かかる場合あり

## ライセンス

MIT
