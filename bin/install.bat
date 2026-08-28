@echo off
REM Instalacao no Windows: cria o ambiente virtual .venv e instala as dependencias.
setlocal
cd /d "%~dp0.."

where py >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale o Python 3.10 ou superior de
    echo        https://www.python.org/downloads/windows/ marcando "Add python.exe to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Criando ambiente virtual .venv ...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
)

echo [INFO] Instalando dependencias ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias.
    pause
    exit /b 1
)

echo.
echo [OK] Instalacao concluida. Execute "executar.bat" para abrir o programa.
echo      O EnergyPlus 9.4 tambem precisa estar instalado (padrao: C:\EnergyPlusV9-4-0).
pause
