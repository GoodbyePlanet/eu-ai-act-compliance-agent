.PHONY: all venv install reinstall install-test activate web run-api run-ui run-ui-traefik run-db-local stop-db-local clean help test-all

VENV_DIR = .venv
PYTHON = python3
VENV_BIN = $(VENV_DIR)/bin
UV = uv
# Marker file to track if package is installed
INSTALL_MARKER = $(VENV_DIR)/.installed

# Target: The default target if you just run 'make'
all: web

help:
	@echo "--- Available make commands ---"
	@grep "^##" $(MAKEFILE_LIST) | sed -E 's/## ([a-zA-Z_-]+): (.*)/\1: \2/' | column -t -s ":"

## venv: Creates the Python virtual environment if it doesn't exist.
venv:
	@if [ ! -d $(VENV_DIR) ]; then \
		echo "Creating virtual environment in $(VENV_DIR)..."; \
		$(PYTHON) -m venv $(VENV_DIR); \
		echo "Virtual environment created."; \
	else \
		echo "Virtual environment already exists in $(VENV_DIR)."; \
	fi

## install: Installs the package in development mode (only runs once).
install: venv
	@if [ ! -f $(INSTALL_MARKER) ]; then \
		echo "--- Installing package in development mode ---"; \
		$(UV) sync; \
		touch $(INSTALL_MARKER); \
	else \
		echo "Package already installed. Run 'make reinstall' to force reinstall."; \
	fi

## reinstall: Force reinstalls the package in development mode.
reinstall: venv
	@echo "--- Reinstalling package in development mode ---"
	$(UV) sync --reinstall
	@touch $(INSTALL_MARKER)

## install-test: Installs test dependencies.
install-test: install
	@echo "--- Installing test dependencies ---"
	$(UV) sync --extra test

## web: Starts the ADK web server on port 8000.
web: install
	@echo "--- Starting ADK web on port 8000 ---"
	$(VENV_BIN)/adk web --port 8000

## activate: Prints the command to manually source the virtual environment.
activate: venv
	@echo "--- Activating virtual environment ---"
	@echo "Run the following command manually in your terminal:"
	@echo "source $(VENV_DIR)/bin/activate"

## run-api: Starts the FastAPI server via uvicorn on port 8000.
run-api: install
	@echo "--- Starting API on port 8000 ---"
	$(VENV_BIN)/uvicorn main:app --port 8000 --reload

## run-ui: Starts Streamlit UI for local mode (http://localhost:8501).
run-ui: install
	@echo "--- Switching Streamlit auth profile to local ---"
	./scripts/use_streamlit_auth_profile.sh local
	@echo "--- Starting Streamlit UI on http://localhost:8501 ---"
	$(VENV_BIN)/streamlit run ui.py

## run-ui-traefik: Starts Streamlit UI with Traefik auth redirect profile.
run-ui-traefik: install
	@echo "--- Switching Streamlit auth profile to traefik ---"
	./scripts/use_streamlit_auth_profile.sh traefik
	@echo "--- Starting Streamlit UI (Traefik profile) ---"
	$(VENV_BIN)/streamlit run ui.py

## run-db-local: Starts only Postgres with localhost:5432 binding for local make run-api.
run-db-local:
	@echo "--- Starting local Postgres on localhost:5432 ---"
	docker compose -f docker-compose.yml -f docker-compose.local.yml up -d db

## stop-db-local: Stops local Postgres started via run-db-local.
stop-db-local:
	@echo "--- Stopping local Postgres ---"
	docker compose -f docker-compose.yml -f docker-compose.local.yml stop db

## clean: Removes the virtual environment directory (.venv).
clean:
	@echo "--- Removing virtual environment directory ($(VENV_DIR)) ---"
	rm -rf $(VENV_DIR)

## test: Run all tests
test-all: install-test
	@echo "--- Running all tests ---"
	$(UV) run pytest tests/ -v
