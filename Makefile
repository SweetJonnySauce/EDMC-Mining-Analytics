SHELL := /bin/bash

VENV ?= .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest

.PHONY: help venv install-dev test test-harness check clean

help:
	@echo "Targets:"
	@echo "  venv          Create local virtualenv ($(VENV))"
	@echo "  install-dev   Install/update dev dependencies"
	@echo "  test          Run full pytest suite"
	@echo "  test-harness  Run harness smoke test only"
	@echo "  check         Run project checks (currently: pytest)"
	@echo "  clean         Remove test/bytecode caches"

venv:
	python3 -m venv $(VENV)

install-dev: venv
	$(PIP) install -U pip
	$(PIP) install -r requirements-dev.txt

test:
	$(PYTEST)

test-harness:
	$(PYTEST) -q tests/test_harness_smoke.py

check: test

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
