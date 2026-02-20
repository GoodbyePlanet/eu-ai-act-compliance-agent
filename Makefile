.PHONY: all venv install activate web run-api run-ui clean help

VENV_DIR = .venv
PYTHON = python3
VENV_BIN = $(VENV_DIR)/bin
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
		$(VENV_BIN)/pip install -e .; \
		touch $(INSTALL_MARKER); \
	else \
		echo "Package already installed. Run 'make reinstall' to force reinstall."; \
	fi

## reinstall: Force reinstalls the package in development mode.
reinstall: venv
	@echo "--- Reinstalling package in development mode ---"
	$(VENV_BIN)/pip install -e .
	@touch $(INSTALL_MARKER)

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

## run-ui: Starts the Streamlit UI.
run-ui: install
	@echo "--- Starting Streamlit UI ---"
	$(VENV_BIN)/streamlit run ui.py

## clean: Removes the virtual environment directory (.venv).
clean:
	@echo "--- Removing virtual environment directory ($(VENV_DIR)) ---"
	rm -rf $(VENV_DIR)

## test: Run all tests
test-all:
	@echo "--- Running all tests ---"
	.venv/bin/pytest tests/ -v
