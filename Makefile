.PHONY: install backend frontend dev test lint db-upgrade check-python

PYTHON := .venv312/bin/python
FRONTEND_PORT ?= 5173

install:
	@command -v uv >/dev/null || { echo "请先安装 uv（https://docs.astral.sh/uv/）。"; exit 1; }
	@command -v npm >/dev/null || { echo "请先安装 Node.js 20+（包含 npm）。"; exit 1; }
	@test -x $(PYTHON) || uv venv --python 3.12 .venv312
	uv pip install --python $(PYTHON) -e '.[dev]'
	cd web/frontend && npm ci

check-python:
	@test -x $(PYTHON) || { echo "尚未安装 Python 环境，请先运行 make install。"; exit 1; }

backend: check-python
	$(PYTHON) -m uvicorn creatoros.api.app:app --host 127.0.0.1 --port 8000

frontend:
	cd web/frontend && npm run dev -- --host 127.0.0.1 --port $(FRONTEND_PORT) --strictPort

dev: check-python
	$(PYTHON) scripts/dev.py --frontend-port $(FRONTEND_PORT)

test: check-python
	$(PYTHON) -m pytest
	cd web/frontend && npm test -- --run

lint: check-python
	PYTHONPYCACHEPREFIX=/tmp/creatoros-pycache $(PYTHON) -m compileall creatoros tests scripts/dev.py
	cd web/frontend && npm run typecheck

db-upgrade: check-python
	$(PYTHON) -c 'from creatoros.cli import main; main()' db upgrade
