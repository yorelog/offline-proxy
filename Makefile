.PHONY: help install dev-install test clean lint format docker run-cache run-offline uv-install uv-dev-install

# Default target
help:
	@echo "Available targets:"
	@echo "  install      - Install the package"
	@echo "  dev-install  - Install in development mode with dev dependencies"
	@echo "  uv-install   - Install using uv (recommended)"
	@echo "  uv-dev-install - Install dev dependencies using uv (recommended)"
	@echo "  test         - Run tests"
	@echo "  clean        - Clean up build artifacts and cache"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code"
	@echo "  docker       - Build Docker image"
	@echo "  run-cache    - Run server in cache mode"
	@echo "  run-offline  - Run server in offline mode"

# Installation
install:
	uv pip install -r requirements.txt
	uv pip install -e .

dev-install:
	uv pip install -r requirements-dev.txt
	uv pip install -e .

# UV-specific installation (recommended)
uv-install:
	uv sync
	uv pip install -e .

uv-dev-install:
	uv sync --extra dev
	uv pip install -e .

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=offline_proxy --cov-report=html

# Code quality
lint:
	flake8 src/offline_proxy
	mypy src/offline_proxy

format:
	black src/offline_proxy tests/
	isort src/offline_proxy tests/

# Cleanup
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Docker
docker:
	docker build -t offline-proxy .

docker-run:
	docker run -p 8080:8080 -p 8443:8443 -v $(PWD)/data:/app/data offline-proxy

# Development servers
run-cache:
	offline-proxy server start --mode cache --verbose

run-offline:
	offline-proxy server start --mode offline --verbose

# Setup helpers
setup-ssl:
	offline-proxy ssl setup

setup-hosts:
	sudo offline-proxy hosts setup

install-certs:
	offline-proxy ssl install

# Cache management
cache-stats:
	offline-proxy cache stats

cache-clear:
	offline-proxy cache clear

# Git operations
git-mirror-python:
	offline-proxy git mirror https://github.com/python/cpython.git

# PyPI operations  
pypi-mirror-common:
	offline-proxy pypi mirror requests
	offline-proxy pypi mirror numpy
	offline-proxy pypi mirror pandas
	offline-proxy pypi mirror flask

pypi-mirror-requirements:
	offline-proxy pypi mirror-requirements examples/requirements.txt

# APT operations
apt-mirror-ubuntu:
	offline-proxy apt mirror --distribution ubuntu --release focal

# Full setup for development
dev-setup: uv-dev-install setup-ssl
	@echo "Development environment ready!"
	@echo "Run 'make run-cache' to start caching mode"
	@echo "Run 'make run-offline' to start offline mode"

# Full cache example
cache-example: pypi-mirror-common git-mirror-python
	@echo "Example resources cached!"
	@echo "Check with 'make cache-stats'"