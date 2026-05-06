@echo off
REM =============================================================================
REM docker-run.bat — convenience wrapper around docker compose (Windows)
REM =============================================================================
REM Usage:
REM   docker-run.bat build              -> Build the image
REM   docker-run.bat demo               -> Run the demo (no API key needed)
REM   docker-run.bat goal "..."         -> Run with a custom goal
REM   docker-run.bat shell              -> Open a shell inside the container
REM   docker-run.bat ollama-up          -> Start Ollama service
REM   docker-run.bat ollama-down        -> Stop Ollama service
REM   docker-run.bat ollama-pull <model> -> Pull a model into Ollama
REM   docker-run.bat clean              -> Remove everything
REM =============================================================================

setlocal enabledelayedexpansion

set CMD=%1
if "%CMD%"=="" set CMD=help

if "%CMD%"=="build" (
    docker compose build agent
    goto :eof
)

if "%CMD%"=="demo" (
    docker compose run --rm agent --demo
    goto :eof
)

if "%CMD%"=="goal" (
    if "%~2"=="" (
        echo Usage: docker-run.bat goal "your goal here"
        exit /b 1
    )
    docker compose run --rm agent --goal %2
    goto :eof
)

if "%CMD%"=="shell" (
    docker compose run --rm --entrypoint /bin/bash agent
    goto :eof
)

if "%CMD%"=="ollama-up" (
    docker compose --profile ollama up -d ollama
    echo [OK] Ollama running on http://localhost:11434
    echo      Pull a model: docker-run.bat ollama-pull llama3.1
    goto :eof
)

if "%CMD%"=="ollama-down" (
    docker compose --profile ollama down
    goto :eof
)

if "%CMD%"=="ollama-pull" (
    if "%~2"=="" (
        echo Usage: docker-run.bat ollama-pull ^<model^>
        echo Example: docker-run.bat ollama-pull llama3.1
        exit /b 1
    )
    docker compose --profile ollama exec ollama ollama pull %2
    goto :eof
)

if "%CMD%"=="clean" (
    docker compose --profile ollama down -v --rmi local
    echo [OK] Cleaned containers, images, and volumes.
    goto :eof
)

REM Default: help
echo AI Operations Agent — Docker helper
echo.
echo Commands:
echo   build                   Build the Docker image
echo   demo                    Run demo mode (no API key needed)
echo   goal "^<goal^>"           Run the agent with a custom goal
echo   shell                   Open a bash shell in the container
echo   ollama-up               Start Ollama service (offline mode)
echo   ollama-down             Stop Ollama service
echo   ollama-pull ^<model^>     Pull a model into Ollama
echo   clean                   Remove all Docker artifacts
echo.
echo Examples:
echo   docker-run.bat build
echo   docker-run.bat demo
echo   docker-run.bat goal "Analyze data/sales.csv and find top regions"

endlocal
