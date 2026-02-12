---
name: discord-digest-v2
description: 外部スクリプトでDiscordメッセージを取得し、要約を生成する。「ダイジェスト作って」「1月まとめて」「チャンネルの情報まとめて」などで使用。exec方式でLLMコンテキストを汚さない。大量データも安全に処理できる。
---

# discord-digest-v2 - 外部スクリプト方式ダイジェスト生成

## 概要

**従来の問題:** サブエージェントがDiscord APIを叩くとコンテキストオーバーフロー（217K tokens）

**解決策:** 
1. exec で外部Pythonスクリプトを実行（Discord API直接叩く）
2. メッセージがJSONファイルに保存される（LLMと無関係）
3. clawdbotがファイルを読んで要約

## 前提条件

- `discord.py` がインストールされていること: `pip install discord.py`
- スクリプト: `~/clawd/scripts/discord_fetcher.py`

**トークンは自動取得:**
1. 環境変数 `DISCORD_BOT_TOKEN`（あれば）
2. `~/.clawdbot/clawdbot.json` の `channels.discord.token`（自動で読む）

→ 環境変数の設定は不要！clawdbot.json にトークンがあればOK。

## ワークフロー

### Phase 1: パラメータ確認

ユーザーから以下を確認:
- チャンネルID（または名前から特定）
- 期間（開始日、終了日）

### Phase 2: データ取得（exec）

```json
{
  "tool": "exec",
  "command": "python3 ~/clawd/scripts/discord_fetcher.py --channel <channel_id> --start <YYYY-MM-DD> --end <YYYY-MM-DD> --output ~/clawd/discord-data/<job_id>",
  "background": true,
  "timeout": 3600
}
```

**例:**
```json
{
  "tool": "exec",
  "command": "python3 ~/clawd/scripts/discord_fetcher.py --channel 977473910402609162 --start 2026-01-01 --end 2026-01-31 --output ~/clawd/discord-data/shuekirakudatsu-jan-2026",
  "background": true,
  "timeout": 3600
}
```

### Phase 3: 完了待ち

process ツールでジョブの完了を確認:

```json
{"tool": "process", "action": "poll", "sessionId": "<id>"}
```

または、出力ディレクトリの `manifest.json` を確認:
- `status: "completed"` → 成功
- `status: "error"` → エラー（error フィールドに詳細）

### Phase 4: 要約生成

**重要: セッションにデータを溜め込まない！**

1. `manifest.json` を読んで総ページ数を確認
2. 各ページ（page-0001.json など）を1つずつ読む
3. ページごとに要点を抽出してファイルに書き出す
4. 次のページへ（生データは破棄）
5. 全ページの要点を統合して最終ダイジェストを生成

```
ループ:
  1. page-NNNN.json を読む
  2. 要点を抽出（トピック、決定事項、質問、重要発言）
  3. 要点を ~/clawd/discord-digests/<date>/page-summary-NNNN.md に書く
  4. 生データを忘れる（次のページへ）

全ページ完了後:
  1. page-summary-*.md を全部読む
  2. 統合ダイジェストを生成
  3. final-digest.md に保存
```

### Phase 5: 結果報告

最終ダイジェストをユーザーに報告。

## ファイル構造

```
~/clawd/
├── scripts/
│   └── discord_fetcher.py       # データ取得スクリプト
│
├── discord-data/                 # 取得した生データ
│   └── <job_id>/
│       ├── manifest.json         # メタデータ
│       ├── page-0001.json        # 1ページ目（最大100件）
│       ├── page-0002.json
│       └── ...
│
└── discord-digests/              # 生成したダイジェスト
    └── <YYYY-MM-DD>/
        ├── page-summary-0001.md  # ページごとの要約
        ├── page-summary-0002.md
        └── final-digest.md       # 最終ダイジェスト
```

## manifest.json の構造

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

## page-NNNN.json の構造

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

## 要約時の抽出ポイント

各ページから以下を抽出:
- **主要トピック**: 何について話しているか
- **決定事項**: 結論が出たこと
- **質問と回答**: Q&A形式の重要な情報
- **重要な発言**: 参考になる情報、リンク、ノウハウ
- **活発な参加者**: 誰がよく発言しているか

## ダイジェストの書き方ガイドライン

**目指すレベル: 「週間ニュースレター」**

忙しい人が2〜3分で読めて、サーバーの流れを把握できるレベル。

### ✅ やること
- **冒頭にハイライト（3〜5行）**: 今週の最重要トピックを箇条書きで一目でわかるように
- **チャンネルごとにセクション分け**: 各チャンネルの内容をまとめる
- **各セクションは2〜4段落**: トピックごとに簡潔にまとめ、誰が何を言ったかを要約（1〜2文で）
- **具体的な数字・名前を入れる**: 「登録者5万人」「月収40万」「着手金6万円」など
- **重要な意見は発言者名付きで引用**: ただし原文そのままではなく要約で
- **成果報告はテーブル形式で一覧化**: 見やすさ重視
- **末尾にキーワードタグ**: 主要トピックを一覧化

### ❌ やらないこと
- 会話の一言一言を再現しない（「〇〇が△△と言い、□□が返した」の連鎖は冗長）
- 全メンバーの発言を網羅しない（重要な発言だけピックアップ）
- リアクション数やemoji名を逐一記載しない（「反響が大きかった」程度でOK）
- 朝活のタイムスケジュール等の定型文はそのまま載せない（「朝活開催」の一言でOK）

### 📏 目安ボリューム
- 全体で**1500〜3000文字**程度（日本語）
- 1チャンネルあたり**100〜300文字**
- メッセージ100件以下なら短め、500件以上なら長めに調整

## 障害対応

### exec がタイムアウトした場合
- `manifest.json` を確認
- `status` が `"completed"` でなければ再実行
- データ取得を再開する場合は `--output` を同じにして再実行（上書き）

### compaction で落ちた場合
- `manifest.json` を確認
- データは既にファイルにあるので、Phase 4（要約生成）から再開

### スクリプトがエラーになった場合
- `manifest.json` の `error` フィールドを確認
- よくあるエラー:
  - `Channel not found`: チャンネルIDが間違っている
  - `No permission`: Botがチャンネルにアクセスできない
  - `DISCORD_BOT_TOKEN not set`: 環境変数が未設定

## 注意事項

- **1ページ = 最大100メッセージ**
- **レート制限**: スクリプト内で0.5秒間隔を入れている
- **大量データ**: 1ヶ月分で数千メッセージある場合、取得に5-10分かかることがある
- **環境変数**: `DISCORD_BOT_TOKEN` は clawdbot 起動時に設定しておく必要がある
