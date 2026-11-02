@echo off
setlocal
cd /d "%~dp0"

if "%MARKETPLACE_AUTO_UPDATE%"=="" set "MARKETPLACE_AUTO_UPDATE=true"

py -3.14 -c "import sys; print(sys.version_info[:2])" 2>nul | findstr /c:"(3, 14)" >nul
if not errorlevel 1 goto run_py_314

py -3.13 -c "import sys; print(sys.version_info[:2])" 2>nul | findstr /c:"(3, 13)" >nul
if not errorlevel 1 goto run_py_313

py -3.12 -c "import sys; print(sys.version_info[:2])" 2>nul | findstr /c:"(3, 12)" >nul
if not errorlevel 1 goto run_py_312

py -3.11 -c "import sys; print(sys.version_info[:2])" 2>nul | findstr /c:"(3, 11)" >nul
if not errorlevel 1 goto run_py_311

python --version >nul 2>nul
if not errorlevel 1 goto run_python

py -3 --version >nul 2>nul
if not errorlevel 1 goto run_py

echo Python compativel nao foi encontrado nesta maquina.
echo Instale Python 3.13 (ou uma versao entre 3.11 e 3.14) e tente novamente.
goto launch_failed

:run_py_314
py -3.14 launcher.py %*
if errorlevel 1 goto launch_failed
exit /b 0

:run_py_313
py -3.13 launcher.py %*
if errorlevel 1 goto launch_failed
exit /b 0

:run_py_312
py -3.12 launcher.py %*
if errorlevel 1 goto launch_failed
exit /b 0

:run_py_311
py -3.11 launcher.py %*
if errorlevel 1 goto launch_failed
exit /b 0

:run_python
python launcher.py %*
if errorlevel 1 goto launch_failed
exit /b 0

:run_py
py -3 launcher.py %*
if errorlevel 1 goto launch_failed
exit /b 0

:launch_failed
echo.
echo O launcher encontrou um erro. Leia a mensagem acima e tente novamente.
pause
exit /b 1
