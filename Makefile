PY ?= python3
SING_BOX ?= sing-box

export PYTHONPATH := src

.PHONY: help build build-fast list test lint clean verify

help:
	@echo "make build      # 完整构建（JSON + SRS，需 sing-box >= 1.14）"
	@echo "make build-fast # 只生成 JSON，跳过 SRS 编译"
	@echo "make list       # 列出规则集与依赖"
	@echo "make test       # 单元测试（无第三方依赖）"
	@echo "make lint       # ruff + 语法检查"
	@echo "make clean      # 清理 dist/ 与缓存"

build:
	$(PY) -m geobuild build --out dist --sing-box $(SING_BOX)

build-fast:
	$(PY) -m geobuild build --out dist --no-srs --no-readme

list:
	$(PY) -m geobuild list

test:
	$(PY) -m unittest discover -s tests -v

lint:
	ruff check src tests
	ruff format --check src tests

clean:
	rm -rf dist .cache build
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

# trigger test
