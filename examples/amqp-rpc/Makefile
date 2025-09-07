VENV_NAME := .venv
PYTHON := $(VENV_NAME)/bin/python
CODEGEN := $(VENV_NAME)/bin/asyncapi-python-codegen
PIP := $(VENV_NAME)/bin/pip
PACKAGE_VERSION := 0.1.0


venv:
	python3 -m venv $(VENV_NAME)

install:
	$(PIP) install -e ../../[amqp,codegen]

generate:
	$(CODEGEN) spec/client.asyncapi.yaml client --force
	$(CODEGEN) spec/server.asyncapi.yaml server --force

client:
	$(PYTHON) main-client.py

server: 
	$(PYTHON) main-server.py

clean:
	rm -rf $(VENV_NAME)

.PHONY: client server
