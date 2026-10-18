from __future__ import annotations

import argparse
import json

import uvicorn

from creatoros.config import load_settings
from creatoros.db.migrations import run_migrations
from creatoros.services.trend_service import TREND_SOURCES, TrendService


def main() -> None:
    parser = argparse.ArgumentParser(prog="creatoros")
    subcommands = parser.add_subparsers(dest="command")
    web = subcommands.add_parser("web", help="启动 CreatorOS API 服务")
    web.add_argument("--host", default=None)
    web.add_argument("--port", type=int, default=None)
    db = subcommands.add_parser("db", help="管理本地数据库")
    db.add_argument("action", choices=["upgrade"])
    trends = subcommands.add_parser("fetch-trends", help="抓取并缓存公开热点榜单")
    trends.add_argument("--platforms", default="douyin,weibo,zhihu")
    trends.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    settings = load_settings()
    if args.command == "web":
        uvicorn.run(
            "creatoros.api.app:app",
            host=args.host or settings.host,
            port=args.port or settings.port,
            reload=False,
        )
        return
    if args.command == "db" and args.action == "upgrade":
        run_migrations(settings)
        print(f"数据库已升级：{settings.database_path}")
        return
    if args.command == "fetch-trends":
        platforms = list(dict.fromkeys(item.strip() for item in args.platforms.split(",") if item.strip()))
        if not platforms or any(platform not in TREND_SOURCES for platform in platforms):
            parser.error("--platforms 只能包含：" + ", ".join(TREND_SOURCES))
        settings.ensure_dirs()
        result = TrendService(cache_path=settings.data_dir / "trend-cache.json").get_trends(
            platforms, limit=args.limit, refresh=True
        )
        print(json.dumps({
            "fetched_at": result["trends"][0].get("fetched_at") if result["trends"] else None,
            "feeds": [
                {"platform": feed["platform"], "status": feed["status"], "items": len(feed["items"])}
                for feed in result["trends"]
            ],
            "cache": str(settings.data_dir / "trend-cache.json"),
        }, ensure_ascii=False))
        return
    parser.print_help()
