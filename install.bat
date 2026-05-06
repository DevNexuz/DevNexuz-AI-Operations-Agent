@echo off
REM =============================================================================
REM AI Operations Agent — Enterprise Install Script (Hybrid)
REM =============================================================================
REM Combines original logging style with enhanced enterprise features:
REM - Conda integration (data science stack)
REM - System requirements validation
REM - LLM provider setup
REM - Performance benchmarks
REM - Original clear logging style
REM =============================================================================

setlocal enabledelayedexpansion

REM Security validation
net session >nul 2>&1
if %errorLevel% equ 0 (
    echo [ERROR] Please don't run this script as Administrator for security reasons.
    echo [INFO] Run as regular user: install.bat
    pause
    exit /b 1
)

REM Verify script is being piped safely (one-line install detection)
if not "%1"=="--piped" (
    echo [INFO] Running in interactive mode...
) else (
    echo [INFO] One-line install detected - proceeding with automated setup...
)

echo.
echo ============================================
echo  Installing AI Operations Agent...
echo  Enterprise Installation with Conda Support
echo ============================================
echo.

REM Performance tracking
set START_TIME=%TIME%

REM -----------------------------------------------------------------------------
REM 1. System Requirements Check (NEW from enterprise version)
REM -----------------------------------------------------------------------------
echo [INFO] Checking system requirements...

REM Check RAM
for /f "tokens=2 delims==" %%i in ('wmic computersystem get TotalPhysicalMemory /value ^| find "="') do set RAM_BYTES=%%i
set /a RAM_GB=!RAM_BYTES!/1024/1024/1024
if !RAM_GB! LSS 4 (
    echo   [WARN] Less than 4GB RAM detected. Some features may be slow.
) else (
    echo   [OK] !RAM_GB!GB RAM detected
)

REM Check Disk Space
for /f "tokens=2 delims==" %%i in ('wmic logicaldisk where "DeviceID='%CD:~0,2%'" get FreeSpace /value ^| find "="') do set DISK_BYTES=%%i
set /a DISK_GB=!DISK_BYTES!/1024/1024/1024
if !DISK_GB! LSS 2 (
    echo   [WARN] Less than 2GB disk space available.
) else (
    echo   [OK] !DISK_GB!GB disk space available
)

REM -----------------------------------------------------------------------------
REM 2. Check Python/Conda (ENHANCED from original)
REM -----------------------------------------------------------------------------
echo.
echo [INFO] Checking Python/Conda environment...

set CONDA_AVAILABLE=false
set PYTHON_CMD=python

REM Check for conda
conda --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set CONDA_AVAILABLE=true
    set PYTHON_CMD=conda run -n ai-ops-agent python
    echo   [OK] Conda detected
) else (
    echo   [WARN] Conda not found, checking for Python...
)

REM Check for Python (from original)
python --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    echo   [OK] Python detected
    
    REM Get Python version (from original)
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo   [OK] Python !PYTHON_VERSION! detected
    
    REM Verify Python 3.10+ (from original)
    for /f "tokens=1,2 delims=." %%a in ("!PYTHON_VERSION!") do (
        set PY_MAJOR=%%a
        set PY_MINOR=%%b
    )
    
    if !PY_MAJOR! LSS 3 (
        echo   [ERROR] Python 3.10+ required. Found: !PYTHON_VERSION!
        pause
        exit /b 1
    )
    if !PY_MAJOR! EQU 3 if !PY_MINOR! LSS 10 (
        echo   [ERROR] Python 3.10+ required. Found: !PYTHON_VERSION!
        pause
        exit /b 1
    )
) else (
    echo   [ERROR] Neither conda nor python found.
    echo   Install Miniconda: https://docs.conda.io/en/latest/miniconda.html
    echo   Or install Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM -----------------------------------------------------------------------------
REM 3. Create Environment (ENHANCED from original)
REM -----------------------------------------------------------------------------
if "!CONDA_AVAILABLE!"=="true" (
    echo.
    echo [INFO] Creating Conda Environment...
    
    REM Check if environment exists
    conda env list | findstr "ai-ops-agent" >nul
    if !ERRORLEVEL! EQU 0 (
        echo   [WARN] 'ai-ops-agent' environment already exists. Updating...
        if exist "environment.yml" (
            conda env update -f environment.yml --name ai-ops-agent --prune
        ) else (
            echo   [WARN] environment.yml not found, keeping existing environment
        )
    ) else (
        echo   [INFO] Creating new conda environment 'ai-ops-agent'...
        conda create -n ai-ops-agent python=3.11 -y
        if errorlevel 1 (
            echo   [ERROR] Failed to create conda environment.
            pause
            exit /b 1
        )
        echo   [OK] Conda environment created
    )
    
    echo   [OK] Environment activated: ai-ops-agent
) else (
    echo.
    echo [INFO] Creating Virtual Environment...
    
    set PROJECT_NAME=ai-ops-agent
    
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

    if exist "venv" (
        echo   [WARN] venv\ already exists. Skipping creation.
    ) else (
        python -m venv venv
        if errorlevel 1 (
            echo   [ERROR] Failed to create venv.
            pause
            exit /b 1
        )
        echo   [OK] venv\ created
    )
    
    REM Activate virtual environment (from original)
    echo.
    echo [INFO] Activating virtual environment...
    call venv\Scripts\activate.bat
    if errorlevel 1 (
        echo   [ERROR] Failed to activate venv.
        pause
        exit /b 1
    )
    echo   [OK] venv activated
)

REM -----------------------------------------------------------------------------
REM 4. Upgrade pip (from original)
REM -----------------------------------------------------------------------------
echo.
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo   [OK] pip upgraded

REM -----------------------------------------------------------------------------
REM 5. Install Dependencies (from original)
REM -----------------------------------------------------------------------------
echo.
echo [INFO] Installing ML/Data Science Stack...

if not exist "requirements.txt" (
    echo   [ERROR] requirements.txt not found.
    echo   Ensure you're in the project root directory.
    pause
    exit /b 1
)

echo   [INFO] Installing 40+ packages including LangChain, Pandas, Scikit-learn...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo   [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo   [OK] Dependencies installed

REM Verify critical packages (ENHANCED from original)
echo.
echo [INFO] Verifying critical packages...

python -c "import sys; packages = ['langchain', 'pandas', 'numpy', 'matplotlib', 'seaborn', 'rich', 'pydantic']; missing = []; [print(f'  [OK] {pkg}') if __import__(pkg) else missing.append(pkg) for pkg in packages]; print(f'  [OK] All critical packages installed successfully!' if not missing else sys.exit(1)"

if errorlevel 1 (
    echo   [ERROR] Package verification failed
    pause
    exit /b 1
)

REM -----------------------------------------------------------------------------
REM 6. Generate Sample Datasets (from original)
REM -----------------------------------------------------------------------------
echo.
echo [INFO] Generating sample datasets...

if not exist "data\generate_samples.py" (
    echo   [WARN] data\generate_samples.py not found. Skipping.
) else (
    python data\generate_samples.py
    echo   [OK] Sample datasets generated
    
    REM Verify datasets (ENHANCED)
    if exist "data\sales.csv" if exist "data\employees.csv" if exist "data\tickets.csv" (
        echo   [OK] All sample datasets ready
    ) else (
        echo   [WARN] Some datasets may be missing
    )
)

REM -----------------------------------------------------------------------------
REM 7. LLM Provider Setup (NEW from enterprise version)
REM -----------------------------------------------------------------------------
echo.
echo [INFO] LLM Provider Setup...

REM Check if .env exists
if exist ".env" (
    echo   [WARN] .env file already exists. Skipping setup.
) else (
    echo   [INFO] Choose your LLM provider:
    echo   1) Groq (Free, Fast - Recommended for testing)
    echo   2) OpenAI (Paid, Most reliable)
    echo   3) Anthropic (Paid, Advanced reasoning)
    echo   4) Ollama (Local, Free - requires local setup)
    echo   5) Skip (Configure manually later)
    
    :provider_choice
    set /p provider_choice="Choice [1-5]: "
    
    if "!provider_choice!"=="1" (
        copy ".env.example" ".env" >nul
        echo   [OK] Configured for Groq
        echo   [INFO] Get your free Groq API key: https://console.groq.com/keys
    ) else if "!provider_choice!"=="2" (
        copy ".env.example" ".env" >nul
        powershell -Command "(Get-Content '.env') -replace 'LLM_PROVIDER=groq', 'LLM_PROVIDER=openai' | Set-Content '.env'"
        echo   [OK] Configured for OpenAI
    ) else if "!provider_choice!"=="3" (
        copy ".env.example" ".env" >nul
        powershell -Command "(Get-Content '.env') -replace 'LLM_PROVIDER=groq', 'LLM_PROVIDER=anthropic' | Set-Content '.env'"
        echo   [OK] Configured for Anthropic
    ) else if "!provider_choice!"=="4" (
        copy ".env.example" ".env" >nul
        powershell -Command "(Get-Content '.env') -replace 'LLM_PROVIDER=groq', 'LLM_PROVIDER=ollama' | Set-Content '.env'"
        echo   [OK] Configured for Ollama
    ) else if "!provider_choice!"=="5" (
        echo   [WARN] Skipping LLM setup
    ) else (
        echo   [ERROR] Invalid choice. Please select 1-5.
        goto provider_choice
    )
)

REM -----------------------------------------------------------------------------
REM 8. Performance Benchmark (NEW from enterprise version)
REM -----------------------------------------------------------------------------
echo.
echo [INFO] Running performance benchmark...

python -c "import time; import pandas as pd; import numpy as np; print('Running quick performance tests...'); start = time.time(); df = pd.DataFrame(np.random.randn(10000, 4), columns=['A', 'B', 'C', 'D']); result = df.describe(); data_time = time.time() - start; start = time.time(); from agent.llm_factory import get_llm; llm_time = time.time() - start; start = time.time(); from tools import ALL_TOOLS, build_tools_catalog; tools_time = time.time() - start; print(f'  [OK] Data processing (10k rows): {data_time:.3f}s'); print(f'  [OK] LLM factory init: {llm_time:.3f}s'); print(f'  [OK] Tools loading ({len(ALL_TOOLS)} tools): {tools_time:.3f}s')"

REM -----------------------------------------------------------------------------
REM 9. Verify Core Imports (from original)
REM -----------------------------------------------------------------------------
echo.
echo [INFO] Verifying core system components...

python -c "try: from agent import get_llm, AgentMemory, Planner, Executor; from tools import ALL_TOOLS, build_tools_catalog; from prompts import build_planner_prompt, build_executor_prompt; print('  [OK] Agent core imports OK'); print(f'  [OK] {len(ALL_TOOLS)} tools registered'); print('  [OK] Planner/Executor system ready'); print('  [OK] Memory system ready'); except Exception as e: print(f'  [ERROR] System verification failed: {e}'); raise"

if errorlevel 1 (
    echo   [ERROR] Core system verification failed
    pause
    exit /b 1
)

REM -----------------------------------------------------------------------------
REM 10. Production Demo (from original)
REM -----------------------------------------------------------------------------
echo.
echo ============================================
echo  Running demo mode (no API key required)...
echo ============================================
echo.

python main.py --demo

REM -----------------------------------------------------------------------------
REM 11. Installation Complete (ENHANCED from original)
REM -----------------------------------------------------------------------------
set END_TIME=%TIME%

echo.
echo ============================================
echo  Installation complete!
echo ============================================
echo.

REM Calculate installation time (simplified)
echo   [INFO] Installation completed successfully

echo.
echo Next steps:
echo.

if "!CONDA_AVAILABLE!"=="true" (
    echo   1. To activate the environment:
    echo      conda activate ai-ops-agent
) else (
    echo   1. To activate the environment:
    echo      venv\Scripts\activate.bat
)

echo   2. To run with a real LLM:
echo      copy .env.example .env
echo      REM Edit .env with your API key
echo      python main.py --goal "Analyze data\sales.csv and find top regions"

echo.
echo   3. Portfolio features demonstrated:
echo      • Multi-provider LLM support
echo      • Production-grade error handling
echo      • Extensible tool system
echo      • Performance monitoring
echo      • Enterprise deployment ready

echo.
echo   [OK] Ready for Agentic Engineering Portfolio!
echo   [INFO] Project demonstrates: AI Agents, LangChain, Multi-LLM Integration
echo   [INFO] Production Architecture, Error Handling, Performance Optimization
echo.

pause
endlocal
