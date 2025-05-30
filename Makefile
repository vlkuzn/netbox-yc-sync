.PHONY: help install clean test lint run dry-run docker-build docker-run

# Default target
help:
	@echo "NetBox Yandex Cloud Sync - Available commands:"
	@echo ""
	@echo "  install     - Install dependencies"
	@echo "  clean       - Clean up temporary files"
	@echo "  test        - Run validation tests"
	@echo "  lint        - Run code linting"
	@echo "  run         - Run synchronization"
	@echo "  dry-run     - Run in dry-run mode"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run  - Run in Docker container"
	@echo "  docker-dry  - Run dry-run in Docker container"

# Install dependencies
install:
	pip install -r requirements.txt

# Clean up temporary files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.log" -delete
	find . -type f -name "*.tmp" -delete

# Run validation tests
test:
	python examples/test_sync.py

# Quick configuration check
check:
	python quick_check.py



# Run code linting
lint:
	python -m py_compile main.py
	python -m py_compile clients/*.py
	python -m py_compile sync/*.py
	python -m py_compile config.py

# Run synchronization
run:
	python main.py

# Run in dry-run mode
dry-run:
	python main.py --dry-run

# Build Docker image
docker-build:
	docker build -t netbox-yc-sync .

# Run in Docker container
docker-run:
	docker run --env-file .env netbox-yc-sync

# Run dry-run in Docker container
docker-dry:
	docker run --env-file .env netbox-yc-sync python main.py --dry-run

# Development setup
dev-setup: install
	cp .env.example .env
	@echo "Development setup complete!"
	@echo "Please edit .env file with your configuration."

# Check configuration
check-config:
	@echo "Checking configuration..."
	@python -c "from config import Config; Config.from_env(); print('Configuration is valid!')"

# Help with troubleshooting
help-debug:
	@echo "Debugging tools:"
	@echo "  make check     - Quick configuration and connectivity check"
	@echo "  make test      - Full validation tests"
	@echo "  make dry-run   - Preview sync actions"