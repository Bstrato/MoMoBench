.PHONY: install test lint smoke doctor

install:
	python3.11 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip -q && pip install -e ".[dev]" -q

test:
	. .venv/bin/activate && pytest -q --cov=momobench

lint:
	. .venv/bin/activate && ruff check momobench tests

smoke:
	. .venv/bin/activate && \
	momobench scenarios generate --suite smoke --seed 42 && \
	momobench scenarios validate data/scenarios/smoke && \
	momobench run --experiment config/experiments/smoke.yaml && \
	echo "smoke suite complete — see runs/ for the latest run directory"

doctor:
	. .venv/bin/activate && momobench doctor --agents config/agents.yaml
