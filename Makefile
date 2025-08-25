VENV ?= .venv
PYVER ?= 312

.PHONY: help
help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: test
test: ## Run unit tests
	virtualenv $(VENV) && \
	source $(VENV)/bin/activate && \
	python3 -m pip install --upgrade pip && \
	pip install -r requirements.txt -r test-requirements.txt && \
	pip install tox && \
	tox


.PHONY: clean
clean: ## Clean artifacts
	rm -rf $(VENV) .tox __pycache__ *.egg-info
