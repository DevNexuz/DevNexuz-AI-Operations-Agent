# =============================================================================
# AI Operations Agent — Makefile
# =============================================================================
# A single entry point for the most common dev / demo / docker tasks.
#
# Quick start:
#   make help        Show all available commands
#   make install     Set up venv + install deps
#   make demo        Run the demo (no API key needed)
#   make run GOAL="Analyze data/sales.csv"
#
# Tip: targets are grouped by category (Setup / Run / Docker / Clean / Misc).
# =============================================================================

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
PYTHON       := python3
VENV         := venv
VENV_PY      := $(VENV)/bin/python
VENV_PIP     := $(VENV)/bin/pip
IMAGE_NAME   := ai-operations-agent
COMPOSE      := docker compose

# Default goal when running `make run` without GOAL=
GOAL         ?= Analyze data/sales.csv and find the top 3 regions

# -----------------------------------------------------------------------------
# Color helpers (terminal output)
# -----------------------------------------------------------------------------
CYAN    := \033[0;36m
GREEN   := \033[0;32m
YELLOW  := \033[1;33m
BLUE    := \033[0;34m
RED     := \033[0;31m
RESET   := \033[0m

# -----------------------------------------------------------------------------
# Make `help` the default target.
# Running `make` with no args prints the menu.
# -----------------------------------------------------------------------------
.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help menu
	@echo ""
	@echo "$(CYAN)╔════════════════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(CYAN)║              AI Operations Agent — Make Targets                ║$(RESET)"
	@echo "$(CYAN)╚════════════════════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@echo "$(YELLOW)📦 Setup$(RESET)"
	@echo "  $(GREEN)make install$(RESET)         Create venv and install Python dependencies"
	@echo "  $(GREEN)make data$(RESET)            Generate sample CSV datasets"
	@echo "  $(GREEN)make env$(RESET)             Copy .env.example to .env (if missing)"
	@echo ""
	@echo "$(YELLOW)🚀 Run$(RESET)"
	@echo "  $(GREEN)make demo$(RESET)            Run demo mode (no API key required)"
	@echo "  $(GREEN)make run$(RESET)             Run agent with the default goal"
	@echo "  $(GREEN)make run GOAL=\"...\"$(RESET)  Run agent with a custom goal"
	@echo "  $(GREEN)make examples$(RESET)        List example goals"
	@echo "  $(GREEN)make report$(RESET)          Show the latest generated report"
	@echo ""
	@echo "$(YELLOW)🐳 Docker$(RESET)"
	@echo "  $(GREEN)make docker-build$(RESET)    Build the Docker image"
	@echo "  $(GREEN)make docker-demo$(RESET)     Run demo inside Docker"
	@echo "  $(GREEN)make docker-run$(RESET)      Run agent inside Docker (uses GOAL=)"
	@echo "  $(GREEN)make docker-shell$(RESET)    Open a shell inside the container"
	@echo "  $(GREEN)make ollama-up$(RESET)       Start local Ollama service"
	@echo "  $(GREEN)make ollama-down$(RESET)     Stop local Ollama service"
	@echo "  $(GREEN)make ollama-pull$(RESET)     Pull a model into Ollama (MODEL=llama3.1)"
	@echo ""
	@echo "$(YELLOW)🧹 Clean$(RESET)"
	@echo "  $(GREEN)make clean$(RESET)           Remove caches and outputs"
	@echo "  $(GREEN)make clean-venv$(RESET)      Remove the virtual environment"
	@echo "  $(GREEN)make clean-docker$(RESET)    Remove Docker artifacts"
	@echo "  $(GREEN)make clean-all$(RESET)       Nuke everything (venv + outputs + docker)"
	@echo ""
	@echo "$(YELLOW)🔍 Misc$(RESET)"
	@echo "  $(GREEN)make verify$(RESET)          Verify imports and project layout"
	@echo "  $(GREEN)make tree$(RESET)            Show project structure"
	@echo "  $(GREEN)make stats$(RESET)           Show project stats (LOC, files)"
	@echo ""
	@echo "$(BLUE)Examples:$(RESET)"
	@echo "  make install && make demo"
	@echo "  make run GOAL=\"Detect anomalies in data/employees.csv\""
	@echo "  make docker-build && make docker-demo"
	@echo ""

# =============================================================================
# 📦 Setup
# =============================================================================

.PHONY: install
install: ## Create venv and install Python dependencies
	@echo "$(BLUE)📦 Creating virtual environment...$(RESET)"
	@$(PYTHON) -m venv $(VENV)
	@echo "$(BLUE)⬆️  Upgrading pip...$(RESET)"
	@$(VENV_PIP) install --upgrade pip --quiet
	@echo "$(BLUE)📚 Installing dependencies...$(RESET)"
	@$(VENV_PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Install complete.$(RESET)"
	@echo "$(YELLOW)→ Activate with: source $(VENV)/bin/activate$(RESET)"

.PHONY: data
data: ## Generate sample CSV datasets
	@echo "$(BLUE)📊 Generating sample datasets...$(RESET)"
	@$(VENV_PY) data/generate_samples.py
	@echo "$(GREEN)✓ Datasets ready in data/$(RESET)"

.PHONY: env
env: ## Copy .env.example to .env if .env is missing
	@if [ -f .env ]; then \
		echo "$(YELLOW)⚠ .env already exists; not overwriting.$(RESET)"; \
	else \
		cp .env.example .env; \
		echo "$(GREEN)✓ .env created from .env.example$(RESET)"; \
		echo "$(YELLOW)→ Edit .env to add your API key.$(RESET)"; \
	fi

# =============================================================================
# 🚀 Run
# =============================================================================

.PHONY: demo
demo: ## Run the agent in demo mode (no API key needed)
	@$(VENV_PY) main.py --demo

.PHONY: run
run: ## Run the agent. Override goal with: make run GOAL="..."
	@echo "$(BLUE)🤖 Running agent with goal:$(RESET) $(GOAL)"
	@$(VENV_PY) main.py --goal "$(GOAL)"

.PHONY: examples
examples: ## Show example goals
	@$(VENV_PY) main.py --list-examples

.PHONY: report
report: ## Show the latest generated report (Markdown)
	@if [ -f outputs/report.md ]; then \
		cat outputs/report.md; \
	else \
		echo "$(RED)✗ No report found. Run 'make demo' or 'make run' first.$(RESET)"; \
	fi

# =============================================================================
# 🐳 Docker
# =============================================================================

.PHONY: docker-build
docker-build: ## Build the Docker image
	@echo "$(BLUE)🐳 Building Docker image...$(RESET)"
	@$(COMPOSE) build agent
	@echo "$(GREEN)✓ Image built: $(IMAGE_NAME):latest$(RESET)"

.PHONY: docker-demo
docker-demo: ## Run demo mode inside Docker
	@$(COMPOSE) run --rm agent --demo

.PHONY: docker-run
docker-run: ## Run the agent inside Docker. Use GOAL="..." for custom goal
	@$(COMPOSE) run --rm agent --goal "$(GOAL)"

.PHONY: docker-shell
docker-shell: ## Open a bash shell inside the container
	@$(COMPOSE) run --rm --entrypoint /bin/bash agent

.PHONY: ollama-up
ollama-up: ## Start local Ollama service (offline mode)
	@$(COMPOSE) --profile ollama up -d ollama
	@echo "$(GREEN)✓ Ollama running on http://localhost:11434$(RESET)"
	@echo "$(YELLOW)→ Pull a model: make ollama-pull MODEL=llama3.1$(RESET)"

.PHONY: ollama-down
ollama-down: ## Stop local Ollama service
	@$(COMPOSE) --profile ollama down

.PHONY: ollama-pull
ollama-pull: ## Pull a model into Ollama. Use MODEL=<name>
	@if [ -z "$(MODEL)" ]; then \
		echo "$(RED)✗ Specify a model: make ollama-pull MODEL=llama3.1$(RESET)"; \
		exit 1; \
	fi
	@echo "$(BLUE)🦙 Pulling model: $(MODEL)$(RESET)"
	@$(COMPOSE) --profile ollama exec ollama ollama pull $(MODEL)

# =============================================================================
# 🧹 Clean
# =============================================================================

.PHONY: clean
clean: ## Remove Python caches and run outputs
	@echo "$(BLUE)🧹 Cleaning caches and outputs...$(RESET)"
	@find . -type d -name "__pycache__" -not -path "./$(VENV)/*" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -not -path "./$(VENV)/*" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -not -path "./$(VENV)/*" -delete 2>/dev/null || true
	@rm -rf outputs/charts/* outputs/*.md outputs/*.json 2>/dev/null || true
	@touch outputs/.gitkeep
	@echo "$(GREEN)✓ Clean.$(RESET)"

.PHONY: clean-venv
clean-venv: ## Remove the virtual environment
	@echo "$(BLUE)🧹 Removing $(VENV)/...$(RESET)"
	@rm -rf $(VENV)
	@echo "$(GREEN)✓ Virtual environment removed.$(RESET)"

.PHONY: clean-docker
clean-docker: ## Remove Docker containers, images, and volumes for this project
	@echo "$(BLUE)🧹 Cleaning Docker artifacts...$(RESET)"
	@$(COMPOSE) --profile ollama down -v --rmi local 2>/dev/null || true
	@echo "$(GREEN)✓ Docker artifacts removed.$(RESET)"

.PHONY: clean-all
clean-all: clean clean-venv clean-docker ## Nuke everything (caches, venv, outputs, docker)
	@echo "$(GREEN)✓ Project fully cleaned.$(RESET)"

# =============================================================================
# 🔍 Misc / Diagnostics
# =============================================================================

.PHONY: verify
verify: ## Verify imports and project layout
	@echo "$(BLUE)🧪 Verifying project...$(RESET)"
	@$(VENV_PY) -c "\
from agent import get_llm, AgentMemory, Planner, Executor; \
from tools import ALL_TOOLS, build_tools_catalog; \
from prompts import build_planner_prompt, build_executor_prompt; \
print('  ✓ Core imports OK'); \
print(f'  ✓ {len(ALL_TOOLS)} tools registered'); \
print(f'  ✓ Tools: {[t.name for t in ALL_TOOLS]}')"

.PHONY: tree
tree: ## Show project structure (excluding venv and caches)
	@if command -v tree >/dev/null 2>&1; then \
		tree -a -I 'venv|__pycache__|.git|*.pyc|outputs/charts'; \
	else \
		find . -not -path '*/\.*' \
			-not -path '*venv*' \
			-not -path '*__pycache__*' \
			-not -path '*outputs/charts*' \
			| sort; \
	fi

.PHONY: stats
stats: ## Show project stats (lines of code, file counts)
	@echo "$(BLUE)📊 Project statistics$(RESET)"
	@echo ""
	@echo "$(YELLOW)Python files:$(RESET)"
	@find . -name "*.py" -not -path "./$(VENV)/*" -not -path "./.git/*" | wc -l | xargs printf "  Count: %s\n"
	@find . -name "*.py" -not -path "./$(VENV)/*" -not -path "./.git/*" -exec cat {} + | wc -l | xargs printf "  LOC:   %s\n"
	@echo ""
	@echo "$(YELLOW)Docs:$(RESET)"
	@find . -name "*.md" -not -path "./$(VENV)/*" -not -path "./.git/*" | wc -l | xargs printf "  Count: %s\n"
	@echo ""
	@echo "$(YELLOW)Tools registered:$(RESET)"
	@$(VENV_PY) -c "from tools import ALL_TOOLS; print(f'  Count: {len(ALL_TOOLS)}')" 2>/dev/null || echo "  (run 'make install' first)"
