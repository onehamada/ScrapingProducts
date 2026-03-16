@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 launcher.py %*
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python launcher.py %*
    exit /b %errorlevel%
)

echo Python nao foi encontrado nesta maquina.
echo Instale o Python 3 e tente novamente.
pause
exit /b 1
