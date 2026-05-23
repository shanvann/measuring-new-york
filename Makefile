# measuring-new-york — Makefile
#
# Conventions
#   make venv                  one-time: create .venv and install deps
#   make geographies           one-time: download canonical boundary files
#   make fetch-gtfs            on-demand: download MTA GTFS (~200MB)
#   make chapter-N             rebuild chapter N from cache (idempotent)
#   make chapter-N FRESH=1     re-fetch from upstream sources, then rebuild
#   make publish CHAPTER=N     copy chapter N artifacts into the website repo
#   make clean                 wipe cache (keeps cache/MANIFEST.json)
#   make lint                  ruff + black --check
#   make nbexec NB=path        execute a notebook in place (for CI/CD later)
#
# All commands assume the .venv is activated. The venv path is honored
# explicitly so `make` works without sourcing.

PYTHON       ?= /usr/bin/python3
VENV         := .venv
VENV_PY      := $(VENV)/bin/python
VENV_PIP     := $(VENV)/bin/pip
WEBSITE_REPO ?= ../personal-website
CHAPTER      ?=
FRESH        ?= 0

.PHONY: help venv geographies fetch-gtfs chapter-% publish clean lint nbexec

help:
	@grep -E '^(##|[a-zA-Z_-]+:.*?##)' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

# ---------- environment ----------

venv: ## Create .venv and install requirements
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip setuptools wheel
	$(VENV_PIP) install -r requirements.txt
	@echo "venv ready. Activate with: source $(VENV)/bin/activate"

# ---------- one-time fetches ----------

geographies: ## Download canonical boundary files (~50MB)
	$(VENV_PY) scripts/download_geographies.py

fetch-gtfs: ## Download MTA GTFS bundles (~200MB)
	$(VENV_PY) -m pipelines.mta_gtfs --fetch

# ---------- chapter rebuilds ----------

# `make chapter-0`        -> replay from cache
# `make chapter-0 FRESH=1` -> re-fetch upstream first
chapter-%: ## Rebuild chapter N (FRESH=1 to re-fetch sources)
	@N=$*; \
	if [ "$(FRESH)" = "1" ]; then \
		echo "[chapter-$$N] FRESH=1 — re-fetching upstream sources"; \
		$(VENV_PY) -m pipelines.refresh --chapter $$N; \
	fi; \
	NB="analyses/chapter-$$(printf '%02d' $$N)/notebook.py"; \
	if [ ! -f "$$NB" ]; then echo "no notebook: $$NB"; exit 1; fi; \
	$(VENV_PY) "$$NB"

# ---------- publish ----------

publish: ## Copy artifacts to the website repo. Requires CHAPTER=N.
	@if [ -z "$(CHAPTER)" ]; then echo "usage: make publish CHAPTER=N"; exit 1; fi
	$(VENV_PY) -m shared.publish --chapter $(CHAPTER) --website-repo $(WEBSITE_REPO)

# ---------- housekeeping ----------

clean: ## Wipe cache contents (keeps MANIFEST.json)
	find cache -type f ! -name 'MANIFEST.json' -delete
	find cache -type d -empty -delete || true
	@echo "cache cleaned (manifest kept)"

lint: ## Lint + format check (no fixes)
	$(VENV_PY) -m ruff check . || true
	$(VENV_PY) -m black --check . || true

nbexec: ## Execute a notebook in place. Usage: make nbexec NB=analyses/chapter-00/notebook.ipynb
	@if [ -z "$(NB)" ]; then echo "usage: make nbexec NB=path/to/notebook.ipynb"; exit 1; fi
	$(VENV_PY) -m jupyter nbconvert --to notebook --execute --inplace "$(NB)"
