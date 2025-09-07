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
	$(CODEGEN) spec/subscriber.asyncapi.yaml subscriber --force
	$(CODEGEN) spec/publisher.asyncapi.yaml publisher --force

client:
	$(PYTHON) main-publisher.py

server: 
	$(PYTHON) main-subscriber.py

clean:
	rm -rf $(VENV_NAME)

.PHONY: client server
