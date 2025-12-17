.PHONY: all venv activate web run-api run-ui clean help

VENV_DIR = .venv
PYTHON = python3

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

## web: Activates the environment and starts the ADK web server on port 8000.
web: venv
	@echo "--- Starting ADK web on port 8000 ---"
	. $(VENV_DIR)/bin/activate; adk web --port 8000

## activate: Prints the command to manually source the virtual environment.
activate: venv
	@echo "--- Activating virtual environment ---"
	@echo "Run the following command manually in your terminal:"
	@echo "source $(VENV_DIR)/bin/activate"

## run-api: Activates the environment and starts the FastAPI server via uvicorn on port 8000.
run-api: venv
	@echo "--- Starting API on port 8000 ---"
	. $(VENV_DIR)/bin/activate; uvicorn pd_ai_tool_assessment_agent.__main__:app --port 8000

## run-ui: Activates the environment and starts the Streamlit UI.
run-ui: venv
	@echo "--- Starting Streamlit UI ---"
	. $(VENV_DIR)/bin/activate; streamlit run ui.py

## clean: Removes the virtual environment directory (.venv).
clean:
	@echo "--- Removing virtual environment directory ($(VENV_DIR)) ---"
	rm -rf $(VENV_DIR)