# WealthOps analytics workbench.
# Quick start:
#   make setup
#   make demo
#   make dashboard

PYTHON ?= .venv/bin/python
WEALTHOPS ?= .venv/bin/wealthops
QUESTION ?= net new assets by month
PORT ?= 8501

.PHONY: setup generate load transform build quality export test demo dashboard nlq status clean help

help:
	@echo "WealthOps targets"
	@echo "  make setup       Create .venv and install the project"
	@echo "  make demo        Full build (reset DB), quality checks and tests"
	@echo "  make build       Generate/load/transform/quality/export (reset DB)"
	@echo "  make generate    Generate synthetic parquet raw data"
	@echo "  make load        Load parquet data into operational tables"
	@echo "  make transform   Build dimensional, fact and KPI views"
	@echo "  make quality     Run data-quality checks only"
	@echo "  make export      Export governed KPI views to CSV"
	@echo "  make test        Run pytest"
	@echo "  make dashboard   Launch Streamlit on http://localhost:$(PORT)"
	@echo "  make nlq QUESTION='...'   Governed NL-to-SQL query"
	@echo "  make status      Show warehouse and data quality status"
	@echo "  make clean       Remove generated data, database and exports"

setup:
	@test -d .venv || python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip -q
	$(PYTHON) -m pip install -e ".[dev]" -q
	@echo "Setup complete. Next: make demo"

generate:
	$(WEALTHOPS) generate

load:
	$(WEALTHOPS) load

transform:
	$(WEALTHOPS) transform

build:
	$(WEALTHOPS) build --reset

quality:
	$(WEALTHOPS) quality

export:
	$(WEALTHOPS) export

test:
	$(PYTHON) -m pytest

demo: setup build test
	@echo ""
	@echo "Demo ready. Start the dashboard with: make dashboard"
	@echo "Open http://localhost:$(PORT)"

dashboard:
	$(PYTHON) -m streamlit run dashboard/app.py --server.port $(PORT)

nlq:
	$(WEALTHOPS) nlq "$(QUESTION)" --show-sql

status:
	$(WEALTHOPS) status

clean:
	rm -f data/wealthops.duckdb data/wealthops.duckdb.wal
	rm -f data/raw/*.parquet data/raw/_manifest.json
	rm -f exports/*.csv exports/*.json
	rm -rf .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	@echo "Generated data, database, exports and caches removed."
