SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := conform
MAKEFLAGS += --warn-undefined-variables --no-builtin-rules
.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'
.PHONY: deps
deps: ## install the pinned toolchain and collections
	python3 -m pip install --quiet -r test-requirements.txt
	ansible-galaxy collection install -r requirements.yml -p ~/.ansible/collections
.PHONY: lint
lint: ## every prek hook on every file
	prek run --all-files --show-diff-on-failure
.PHONY: pins
pins: ## pin discipline (requirements.yml)
	python3 scripts/check-pins.py
.PHONY: conform
conform: lint ## the house gate: yamllint, ansible-lint, syntax-check, pins, static gates, role must-haves
	./scripts/conform
	@echo "conform: OK"
.PHONY: upgrade
upgrade: ## raise every collection pin, keep the result only if conform passes
	./scripts/upgrade
