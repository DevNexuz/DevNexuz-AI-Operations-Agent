#!/bin/bash

# =============================================================================
# docker-run.sh — convenience wrapper around docker compose
# =============================================================================
# Usage:
#   ./docker-run.sh build              -> Build the image
#   ./docker-run.sh demo               -> Run the demo (no API key needed)
#   ./docker-run.sh goal "..."         -> Run with a custom goal
#   ./docker-run.sh shell              -> Open a shell inside the container
#   ./docker-run.sh ollama-up          -> Start Ollama service
#   ./docker-run.sh ollama-down        -> Stop Ollama service
#   ./docker-run.sh ollama-pull <model> -> Pull a model into Ollama
#   ./docker-run.sh clean              -> Remove containers + image + volumes
# =============================================================================

set -e

CMD=${1:-help}
shift || true

case "$CMD" in
    build)
        docker compose build agent
        ;;

    demo)
        docker compose run --rm agent --demo
        ;;

    goal)
        if [ -z "$1" ]; then
            echo "Usage: ./docker-run.sh goal \"<your goal here>\""
            exit 1
        fi
        docker compose run --rm agent --goal "$*"
        ;;

    shell)
        docker compose run --rm --entrypoint /bin/bash agent
        ;;

    ollama-up)
        docker compose --profile ollama up -d ollama
        echo "✓ Ollama running on http://localhost:11434"
        echo "  Don't forget to pull a model: ./docker-run.sh ollama-pull llama3.1"
        ;;

    ollama-down)
        docker compose --profile ollama down
        ;;

    ollama-pull)
        if [ -z "$1" ]; then
            echo "Usage: ./docker-run.sh ollama-pull <model>"
            echo "Example: ./docker-run.sh ollama-pull llama3.1"
            exit 1
        fi
        docker compose --profile ollama exec ollama ollama pull "$1"
        ;;

    clean)
        docker compose --profile ollama down -v --rmi local
        echo "✓ Cleaned containers, images, and volumes."
        ;;

    help|*)
        echo "AI Operations Agent — Docker helper"
        echo ""
        echo "Commands:"
        echo "  build                   Build the Docker image"
        echo "  demo                    Run demo mode (no API key needed)"
        echo "  goal \"<goal>\"           Run the agent with a custom goal"
        echo "  shell                   Open a bash shell in the container"
        echo "  ollama-up               Start Ollama service (offline mode)"
        echo "  ollama-down             Stop Ollama service"
        echo "  ollama-pull <model>     Pull a model into Ollama"
        echo "  clean                   Remove all Docker artifacts"
        echo ""
        echo "Examples:"
        echo "  ./docker-run.sh build"
        echo "  ./docker-run.sh demo"
        echo "  ./docker-run.sh goal \"Analyze data/sales.csv and find top regions\""
        ;;
esac
