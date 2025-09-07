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
	$(CODEGEN) spec/producer.asyncapi.yaml producer --force
	$(CODEGEN) spec/worker.asyncapi.yaml worker --force

producer:
	$(PYTHON) main-producer.py

worker1:
	$(PYTHON) main-worker.py worker1

worker2:
	$(PYTHON) main-worker.py worker2

worker3:
	$(PYTHON) main-worker.py worker3

test-workqueue:
	$(PYTHON) test_workqueue.py

clean:
	rm -rf $(VENV_NAME)

.PHONY: producer worker1 worker2 worker3 test-workqueue