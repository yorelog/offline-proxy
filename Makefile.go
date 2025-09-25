.PHONY: help build install clean test lint format run-cache run-offline

# Default target
help:
	@echo "Available targets:"
	@echo "  build        - Build the offline-proxy binary"
	@echo "  install      - Install dependencies"
	@echo "  clean        - Clean up build artifacts"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code"
	@echo "  run-cache    - Run server in cache mode"
	@echo "  run-offline  - Run server in offline mode"

# Build
build:
	go build -o bin/offline-proxy ./cmd/offline-proxy

# Install dependencies
install:
	go mod download
	go mod tidy

# Testing
test:
	go test -v ./...

test-coverage:
	go test -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out

# Code quality
lint:
	golangci-lint run

format:
	go fmt ./...
	goimports -w .

# Cleanup
clean:
	rm -rf bin/
	rm -f coverage.out
	go clean

# Development servers
run-cache:
	go run ./cmd/offline-proxy server start --mode cache --verbose

run-offline:
	go run ./cmd/offline-proxy server start --mode offline --verbose

# Setup helpers
setup-ssl:
	go run ./cmd/offline-proxy ssl setup

setup-hosts:
	sudo go run ./cmd/offline-proxy hosts setup

# Cache management
cache-stats:
	go run ./cmd/offline-proxy cache stats

cache-clear:
	go run ./cmd/offline-proxy cache clear

# Git operations
git-mirror-python:
	go run ./cmd/offline-proxy git mirror https://github.com/python/cpython.git

# PyPI operations  
pypi-mirror-requests:
	go run ./cmd/offline-proxy pypi mirror requests

# APT operations
apt-mirror-ubuntu:
	go run ./cmd/offline-proxy apt mirror --distribution ubuntu --release focal

# Install binary
install-binary: build
	sudo cp bin/offline-proxy /usr/local/bin/

# Uninstall binary
uninstall-binary:
	sudo rm -f /usr/local/bin/offline-proxy

# Create release
release: clean
	mkdir -p dist
	GOOS=linux GOARCH=amd64 go build -o dist/offline-proxy-linux-amd64 ./cmd/offline-proxy
	GOOS=darwin GOARCH=amd64 go build -o dist/offline-proxy-darwin-amd64 ./cmd/offline-proxy
	GOOS=windows GOARCH=amd64 go build -o dist/offline-proxy-windows-amd64.exe ./cmd/offline-proxy