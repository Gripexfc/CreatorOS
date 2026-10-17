"""Start and supervise the local API and Vite together (macOS/Linux)."""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
API_PORT = 8000


class StartupError(RuntimeError):
    pass


class StopRequested(BaseException):
    def __init__(self, signum: int):
        self.signum = signum


def on_signal(signum: int, _frame: object) -> None:
    raise StopRequested(signum)


def check_dependencies(root: Path) -> str:
    node = shutil.which("node")
    if not node:
        raise StartupError("找不到 Node.js，请安装 Node.js 20+，再运行 make install。")
    version = subprocess.check_output([node, "--version"], text=True).strip()
    if int(version.lstrip("v").split(".")[0]) < 20:
        raise StartupError("需要 Node.js 20+，当前版本为 " + version)
    missing = [name for name in ("uvicorn", "fastapi", "sqlalchemy", "alembic")
               if importlib.util.find_spec(name) is None]
    if missing or not (root / "web/frontend/node_modules/vite/bin/vite.js").is_file():
        raise StartupError("项目依赖不完整，请先运行 make install。")
    return node


def check_ports(ports: list[int]) -> None:
    if len(set(ports)) != len(ports):
        raise StartupError("前端端口不能与 API 端口 8000 相同。")
    for port in ports:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as error:
                raise StartupError(
                    f"无法使用本地端口 {port}：{error}。请先停止占用它的服务；"
                    "前端也可用 make dev FRONTEND_PORT=5176 更换端口。"
                ) from error


def check_children(children: list[tuple[str, subprocess.Popen]]) -> None:
    for name, process in children:
        code = process.poll()
        if code is not None:
            raise StartupError(f"{name} 已退出（退出码 {code}），正在停止其余服务。请查看上方日志。")


def wait_ready(children: list[tuple[str, subprocess.Popen]], urls: list[str], timeout: float = 60) -> None:
    pending = set(urls)
    deadline = time.monotonic() + timeout
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while pending:
        check_children(children)
        for url in tuple(pending):
            try:
                with client.open(url, timeout=1) as response:
                    if response.status == 200:
                        pending.remove(url)
            except (OSError, urllib.error.URLError):
                pass
        check_children(children)
        if not pending:
            return
        if time.monotonic() >= deadline:
            raise StartupError("服务在 60 秒内未就绪：" + ", ".join(sorted(pending)))
        time.sleep(0.2)


def stop_children(children: list[tuple[str, subprocess.Popen]]) -> None:
    for _, process in children:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and any(p.poll() is None for _, p in children):
        time.sleep(0.05)
    for _, process in children:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description="同时启动 CreatorOS API 和前端；Ctrl-C 同时停止。")
    parser.add_argument("--frontend-port", type=int, default=5173)
    args = parser.parse_args()
    if not 1024 <= args.frontend_port <= 65535:
        parser.error("前端端口需要在 1024–65535 之间")
    children: list[tuple[str, subprocess.Popen]] = []
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, on_signal)
    try:
        node = check_dependencies(ROOT)
        check_ports([API_PORT, args.frontend_port])
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["VITE_API_BASE_URL"] = f"http://127.0.0.1:{API_PORT}"
        env["CREATOROS_FRONTEND_ORIGIN"] = f"http://127.0.0.1:{args.frontend_port}"
        commands = [
            ("API", [sys.executable, "-m", "uvicorn", "creatoros.api.app:app",
                     "--host", "127.0.0.1", "--port", str(API_PORT)], ROOT),
            ("前端", [node, "node_modules/vite/bin/vite.js", "--host", "127.0.0.1",
                      "--port", str(args.frontend_port), "--strictPort"], ROOT / "web/frontend"),
        ]
        for name, command, cwd in commands:
            print(f"[CreatorOS] 正在启动{name}…", flush=True)
            process = subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True)
            children.append((name, process))
        frontend_url = f"http://127.0.0.1:{args.frontend_port}"
        wait_ready(children, [f"http://127.0.0.1:{API_PORT}/api/v1/status", frontend_url])
        print(f"\n[CreatorOS] 前后端均已就绪：{frontend_url}/#/create\n"
              "[CreatorOS] 按 Ctrl-C 同时停止两个服务。\n", flush=True)
        while True:
            check_children(children)
            time.sleep(0.25)
    except StopRequested as error:
        print("\n[CreatorOS] 正在停止前后端…", flush=True)
        return 128 + error.signum
    except (StartupError, OSError, subprocess.SubprocessError) as error:
        print(f"\n[CreatorOS] 启动失败：{error}", file=sys.stderr, flush=True)
        return 1
    finally:
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, signal.SIG_IGN)
        stop_children(children)


if __name__ == "__main__":
    sys.exit(main())
