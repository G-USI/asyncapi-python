.PHONY: venv install generate publisher subscriber1 subscriber2 clean help

# Virtual environment
VENV_NAME := .venv
PYTHON := $(VENV_NAME)/bin/python
PIP := $(VENV_NAME)/bin/pip
CODEGEN := $(VENV_NAME)/bin/asyncapi-python-codegen

help:
	@echo "Available targets:"
	@echo "  make venv         - Create virtual environment"
	@echo "  make install      - Install dependencies"
	@echo "  make generate     - Generate code from AsyncAPI specs"
	@echo "  make publisher    - Run the publisher"
	@echo "  make subscriber1  - Run subscriber 1"
	@echo "  make subscriber2  - Run subscriber 2"
	@echo "  make clean        - Remove virtual environment and generated code"

venv:
	@echo "Creating virtual environment..."
	python3 -m venv $(VENV_NAME)
	@echo "✅ Virtual environment created"

install: venv
	@echo "Installing dependencies..."
	$(PIP) install -e ../../[amqp,codegen]
	@echo "✅ Dependencies installed"

generate: install
	@echo "Generating publisher code..."
	$(CODEGEN) spec/publisher.asyncapi.yaml publisher --force
	@echo "✅ Publisher code generated"
	@echo ""
	@echo "Generating subscriber1 code..."
	$(CODEGEN) spec/subscriber1.asyncapi.yaml subscriber1 --force
	@echo "✅ Subscriber1 code generated"
	@echo ""
	@echo "Generating subscriber2 code..."
	$(CODEGEN) spec/subscriber2.asyncapi.yaml subscriber2 --force
	@echo "✅ Subscriber2 code generated"

publisher: generate
	@echo "Starting publisher..."
	@echo ""
	$(PYTHON) main-publisher.py

subscriber1: generate
	@echo "Starting subscriber 1..."
	@echo ""
	$(PYTHON) main-subscriber1.py

subscriber2: generate
	@echo "Starting subscriber 2..."
	@echo ""
	$(PYTHON) main-subscriber2.py

clean:
	@echo "Cleaning up..."
	rm -rf $(VENV_NAME)
	rm -rf publisher/
	rm -rf subscriber1/
	rm -rf subscriber2/
	rm -rf __pycache__
	@echo "✅ Cleanup complete"
