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
.PHONY: lint-source
lint-source: ## Ludus source/template/blueprint linter (scripts/ludus_source_lint.py)
	python3 scripts/ludus_source_lint.py --root .
.PHONY: test-source
test-source: ## the linter self-tests (tests/)
	python3 -m pytest -q tests
.PHONY: packer-tools
packer-tools: ## install Packer + the Ludus plugin set into .tools/ (ludus-reference/versions.json)
	scripts/install_ludus_packer.sh
.PHONY: packer-fmt
packer-fmt: ## rewrite the templates with packer fmt
	packer fmt -recursive templates
.PHONY: packer-validate
packer-validate: ## packer fmt -check + validate every template the way Ludus builds it
	scripts/packer_smoke.sh
.PHONY: check-reference
check-reference: ## fail if upstream Ludus main drifted from ludus-reference/
	python3 scripts/update_ludus_reference.py --check
.PHONY: update-reference
update-reference: ## regenerate ludus-reference/ from upstream Ludus main
	python3 scripts/update_ludus_reference.py
