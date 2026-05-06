@echo off
REM =============================================================================
REM AI Operations Agent — Project Setup Script (Windows .bat)
REM =============================================================================
REM Creates the full folder structure and empty files for the project.
REM After running this, you only need to paste the contents from the chat
REM into each file.
REM =============================================================================

setlocal enabledelayedexpansion
set PROJECT_NAME=ai-operations-agent

REM Windows compatibility improvements
chcp 65001 >nul 2>&1  # Set UTF-8 codepage for better encoding support

echo.
echo ============================================
echo  Setting up %PROJECT_NAME%...
echo ============================================
echo.

REM -----------------------------------------------------------------------------
REM 1. Create main project folder
REM -----------------------------------------------------------------------------
if exist "%PROJECT_NAME%" (
    echo [WARN] Folder "%PROJECT_NAME%" already exists.
    set /p confirm=Continue anyway? (y/N): 
    if /i not "!confirm!"=="y" (
        echo Aborted.
        exit /b 1
    )
) else (
    mkdir "%PROJECT_NAME%"
)

cd "%PROJECT_NAME%"

REM -----------------------------------------------------------------------------
REM 2. Create folder structure
REM -----------------------------------------------------------------------------
echo [INFO] Creating folder structure...

if not exist "agent" mkdir agent
if not exist "tools" mkdir tools
if not exist "prompts" mkdir prompts
if not exist "data" mkdir data
if not exist "examples" mkdir examples
if not exist "outputs" mkdir outputs
if not exist ".github" mkdir .github
if not exist ".github\ISSUE_TEMPLATE" mkdir .github\ISSUE_TEMPLATE

echo   [OK] Folders created

REM -----------------------------------------------------------------------------
REM 3. Create root files
REM -----------------------------------------------------------------------------
echo [INFO] Creating root files...

type nul > README.md
type nul > LICENSE
type nul > CONTRIBUTING.md
type nul > .gitignore
type nul > .env.example
type nul > requirements.txt
type nul > main.py
type nul > demo_mode.py

echo   [OK] Root files created

REM -----------------------------------------------------------------------------
REM 4. Create agent\ files
REM -----------------------------------------------------------------------------
echo [INFO] Creating agent\ files...

type nul > agent\__init__.py
type nul > agent\llm_factory.py
type nul > agent\memory.py
type nul > agent\planner.py
type nul > agent\executor.py
type nul > agent\logger.py

echo   [OK] agent\ files created

REM -----------------------------------------------------------------------------
REM 5. Create tools\ files
REM -----------------------------------------------------------------------------
echo [INFO] Creating tools\ files...

type nul > tools\__init__.py
type nul > tools\_state.py
type nul > tools\csv_tools.py
type nul > tools\analysis_tools.py
type nul > tools\report_tools.py

echo   [OK] tools\ files created

REM -----------------------------------------------------------------------------
REM 6. Create prompts\ files
REM -----------------------------------------------------------------------------
echo [INFO] Creating prompts\ files...

type nul > prompts\__init__.py
type nul > prompts\prompts.py

echo   [OK] prompts\ files created

REM -----------------------------------------------------------------------------
REM 7. Create data\ files
REM -----------------------------------------------------------------------------
echo [INFO] Creating data\ files...

type nul > data\__init__.py
type nul > data\generate_samples.py

echo   [OK] data\ files created

REM -----------------------------------------------------------------------------
REM 8. Create examples\ files
REM -----------------------------------------------------------------------------
echo [INFO] Creating examples\ files...

type nul > examples\__init__.py
type nul > examples\example_goals.md

echo   [OK] examples\ files created

REM -----------------------------------------------------------------------------
REM 9. Create outputs\.gitkeep with content
REM -----------------------------------------------------------------------------
echo [INFO] Creating outputs\ placeholder...

(
    echo # This file keeps the outputs/ directory in git.
    echo # Generated reports, charts, and memory dumps will land here when the agent runs.
) > outputs\.gitkeep

echo   [OK] outputs\.gitkeep created

REM -----------------------------------------------------------------------------
REM 10. Create .github\ files
REM -----------------------------------------------------------------------------
echo [INFO] Creating .github\ files...

type nul > .github\PULL_REQUEST_TEMPLATE.md
type nul > .github\ISSUE_TEMPLATE\bug_report.md
type nul > .github\ISSUE_TEMPLATE\feature_request.md

echo   [OK] .github\ files created

REM -----------------------------------------------------------------------------
REM 11. Show structure
REM -----------------------------------------------------------------------------
echo.
echo ============================================
echo  Project structure:
echo ============================================
tree /F /A

REM -----------------------------------------------------------------------------
REM 12. Done!
REM -----------------------------------------------------------------------------
echo.
echo ============================================
echo  Project structure created successfully!
echo ============================================
echo.
echo Next steps:
echo   1. cd %PROJECT_NAME%
echo   2. Open the project in your editor (e.g. 'code .')
echo   3. Paste the content from the chat into each file
echo   4. Run install.bat to set up environment and dependencies
echo.

pause
endlocal
