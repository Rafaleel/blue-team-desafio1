SHELL := /bin/bash

PYTHON := .venv/bin/python
PYTHONPATH := src
UV_CACHE_DIR ?= .cache/uv
UV_PYTHON_INSTALL_DIR ?= .tools/python
HF_HOME ?= .cache/huggingface

export PYTHONPATH UV_CACHE_DIR UV_PYTHON_INSTALL_DIR HF_HOME

.PHONY: setup verify-assets test calibrate eval margin-audit benchmark benchmark-enforce determinism run

setup:
	uv python install 3.12.13
	@test -x $(PYTHON) || uv venv --python 3.12.13 .venv
	@$(PYTHON) -c 'import platform, sys; expected="3.12.13"; actual=platform.python_version(); sys.exit(0 if actual == expected else "Python incompatível: esperado=" + expected + " atual=" + actual)'
	uv pip sync --python $(PYTHON) --require-hashes requirements.lock
	$(PYTHON) scripts/fetch_model.py
	$(PYTHON) scripts/build_prototypes.py
	$(PYTHON) scripts/verify_assets.py

verify-assets:
	$(PYTHON) scripts/verify_assets.py

test: verify-assets
	$(PYTHON) -m pytest

calibrate: verify-assets
	$(PYTHON) scripts/calibrate.py

eval: verify-assets
	$(PYTHON) scripts/evaluate.py
	$(PYTHON) scripts/generate_report.py

margin-audit: verify-assets
	$(PYTHON) scripts/audit_decision_margins.py --enforce

benchmark: verify-assets
	$(PYTHON) scripts/benchmark.py

benchmark-enforce: verify-assets
	$(PYTHON) scripts/benchmark.py --enforce-budget

determinism: verify-assets
	$(PYTHON) scripts/check_determinism.py --runs 100

run: verify-assets
	printf '%s\n' 'Qual argamassa devo usar para porcelanato externo?' | $(PYTHON) -m domain_guard classify --stdin
