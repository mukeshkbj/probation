# Probation - common tasks. Uses uv when it is installed, otherwise a local .venv.
# Usage: make install | test | register | spike-connect | spike-room | warden | shim | redteam-flintai

SHELL := /bin/bash
UV := $(shell command -v uv 2>/dev/null)
ifeq ($(UV),)
PY := .venv/bin/python
else
PY := uv run python
endif

CANDIDATE ?= scout
FLINTAI_CONFIG ?= redteam/config.example.json

.PHONY: help install test warden shim register spike-connect spike-rooms spike-room redteam-flintai clean

help:
	@echo "make install          install dependencies (uv sync, or .venv + pip)"
	@echo "make test             run the test suite"
	@echo "make register         register Warden with Switch (prints WARDEN_* lines for .env)"
	@echo "make spike-connect    spike 1: connect over WebSocket, print events, post 'Warden online'"
	@echo "make spike-rooms      list the rooms Warden is in (to find TEAM_ROOM_ID)"
	@echo "make spike-room       spike 4: create a probation side room (CANDIDATE=scout USER_NAME=<discord username>)"
	@echo "make warden           run Warden"
	@echo "make shim             run the HTTP shim the Switch Trust CLI (flintai) calls"
	@echo "make redteam-flintai  run the Switch Trust CLI eval against CANDIDATE through the shim"

install:
ifeq ($(UV),)
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -e '.[dev]'
else
	uv sync
endif

test:
	$(PY) -m pytest -q

warden:
	$(PY) -m warden

shim:
	$(PY) -m shim

register:
	$(PY) scripts/register_warden.py

spike-connect:
	$(PY) scripts/spike_connect.py

spike-rooms:
	$(PY) scripts/spike_connect.py --rooms

spike-room:
	$(PY) scripts/spike_create_room.py --candidate $(CANDIDATE) $(if $(USER_NAME),--user $(USER_NAME),)

# Needs `pip install switch-trust-cli` first (see docs/SETUP.md), and `make shim` running.
redteam-flintai:
	switch-trust eval run --model $(CANDIDATE) --config $(FLINTAI_CONFIG)

clean:
	rm -rf .pytest_cache; find . -name __pycache__ -type d -prune -exec rm -rf {} +
