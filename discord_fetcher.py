#!/usr/bin/env python3
"""
Discord メッセージ取得スクリプト
clawdbotのexecツールから呼び出して使う

使い方:
  python3 discord_fetcher.py --channel 977473910402609162 --start 2026-01-01 --end 2026-01-31 --output ~/clawd/discord-data/job-001

トークンは以下の順序で自動取得:
  1. 環境変数 DISCORD_BOT_TOKEN
  2. ~/.clawdbot/clawdbot.json の channels.discord.token
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import discord
except ImportError:
    print("Error: discord.py is not installed. Run: pip install discord.py")
    sys.exit(1)


def get_discord_token() -> str:
    """Discord トークンを取得（環境変数 → clawdbot.json の順）"""
    
    # 1. 環境変数から
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if token:
        print("[INFO] Using token from DISCORD_BOT_TOKEN environment variable")
        return token
    
    # 2. clawdbot.json から
    config_paths = [
        Path("~/.clawdbot/clawdbot.json").expanduser(),
        Path("~/.clawdbot-dev/clawdbot.json").expanduser(),
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                token = config.get("channels", {}).get("discord", {}).get("token")
                if token:
                    print(f"[INFO] Using token from {config_path}")
                    return token
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[WARN] Failed to read token from {config_path}: {e}")
    
    return None


# 設定
DISCORD_TOKEN = get_discord_token()


class MessageFetcher(discord.Client):
    def __init__(self, channel_id: int, start_date: datetime, end_date: datetime, output_dir: Path):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.channel_id = channel_id
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def on_ready(self):
        print(f"[INFO] Logged in as {self.user}")
        try:
            await self.fetch_messages()
        except Exception as e:
            print(f"[ERROR] {e}")
            # エラー時もマニフェストを書く
            self._write_manifest(status="error", error=str(e))
        finally:
            await self.close()
    
    async def fetch_messages(self):
        channel = self.get_channel(self.channel_id)
        if not channel:
            # チャンネルが見つからない場合、フェッチを試みる
            try:
                channel = await self.fetch_channel(self.channel_id)
            except discord.NotFound:
                raise Exception(f"Channel {self.channel_id} not found")
            except discord.Forbidden:
                raise Exception(f"No permission to access channel {self.channel_id}")
        
        print(f"[INFO] Fetching messages from #{channel.name} ({channel.id})")
        print(f"[INFO] Period: {self.start_date.date()} to {self.end_date.date()}")
        
        page = 1
        total_messages = 0
        reached_start = False
        
        # ページングで取得（最新から古い順）
        last_message = None
        
        while not reached_start:
            messages = []
            
            # 100件ずつ取得
            kwargs = {"limit": 100}
            if last_message:
                kwargs["before"] = last_message
            
            async for msg in channel.history(**kwargs):
                messages.append(msg)
            
            if not messages:
                print(f"[INFO] No more messages")
                break
            
            last_message = messages[-1]
            oldest_date = messages[-1].created_at.replace(tzinfo=timezone.utc)
            newest_date = messages[0].created_at.replace(tzinfo=timezone.utc)
            
            print(f"[DEBUG] Page {page}: {len(messages)} messages ({newest_date.date()} to {oldest_date.date()})")
            
            # 対象期間でフィルタリング
            filtered = []
            for m in messages:
                msg_date = m.created_at.replace(tzinfo=timezone.utc)
                if msg_date < self.start_date:
                    # 対象期間より前に到達
                    reached_start = True
                    continue
                if msg_date <= self.end_date:
                    filtered.append(m)
            
            if filtered:
                # ファイルに保存
                output_file = self.output_dir / f"page-{page:04d}.json"
                data = [self._message_to_dict(m) for m in filtered]
                
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                total_messages += len(filtered)
                print(f"[INFO] Page {page}: {len(filtered)} messages saved")
                page += 1
            
            # レート制限対策
            await asyncio.sleep(0.5)
            
            # 対象期間より前のメッセージだけだった場合
            if oldest_date < self.start_date:
                reached_start = True
        
        # マニフェスト作成
        self._write_manifest(
            status="completed",
            channel_name=channel.name,
            total_pages=page - 1,
            total_messages=total_messages
        )
        
        print(f"[SUCCESS] Done! {total_messages} messages in {page - 1} pages")
    
    def _message_to_dict(self, m) -> dict:
        """メッセージをdict形式に変換"""
        return {
            "id": str(m.id),
            "author": m.author.name,
            "author_display_name": m.author.display_name,
            "author_id": str(m.author.id),
            "content": m.content,
            "timestamp": m.created_at.isoformat(),
            "attachments": [{"url": a.url, "filename": a.filename} for a in m.attachments],
            "embeds": [{"title": e.title, "description": e.description} for e in m.embeds if e.title or e.description],
            "reactions": [{"emoji": str(r.emoji), "count": r.count} for r in m.reactions] if m.reactions else [],
            "reply_to": str(m.reference.message_id) if m.reference else None
        }
    
    def _write_manifest(self, status: str, **kwargs):
        """マニフェストファイルを書き出す"""
        manifest = {
            "channel_id": str(self.channel_id),
            "channel_name": kwargs.get("channel_name", ""),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_pages": kwargs.get("total_pages", 0),
            "total_messages": kwargs.get("total_messages", 0),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "status": status
        }
        
        if "error" in kwargs:
            manifest["error"] = kwargs["error"]
        
        manifest_file = self.output_dir / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] Manifest written to {manifest_file}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Fetch Discord messages and save to JSON files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch January 2026 messages
  python3 discord_fetcher.py --channel 977473910402609162 --start 2026-01-01 --end 2026-01-31

  # Specify output directory
  python3 discord_fetcher.py --channel 123456 --start 2026-01-01 --end 2026-01-31 --output ~/data/job-001

Environment:
  DISCORD_BOT_TOKEN  Discord bot token (required)
"""
    )
    parser.add_argument("--channel", type=int, required=True, help="Discord channel ID")
    parser.add_argument("--start", type=str, required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default=None, help="Output directory (default: ~/clawd/discord-data/<channel>-<start>)")
    
    args = parser.parse_args()
    
    # トークンチェック
    if not DISCORD_TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable is not set")
        print("Run: export DISCORD_BOT_TOKEN='your_bot_token'")
        sys.exit(1)
    
    # 日付パース
    try:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_date = datetime.strptime(args.end, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc
        )
    except ValueError as e:
        print(f"Error: Invalid date format. Use YYYY-MM-DD. ({e})")
        sys.exit(1)
    
    # 出力ディレクトリ
    if args.output:
        output_dir = Path(args.output).expanduser()
    else:
        output_dir = Path(f"~/clawd/discord-data/{args.channel}-{args.start}").expanduser()
    
    print(f"[INFO] Channel: {args.channel}")
    print(f"[INFO] Period: {args.start} to {args.end}")
    print(f"[INFO] Output: {output_dir}")
    
    # 実行
    client = MessageFetcher(args.channel, start_date, end_date, output_dir)
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
