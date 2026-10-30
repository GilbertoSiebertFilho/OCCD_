@echo off
rem OCCD - Olds College Cleaning Data: install on a new computer.
rem Creates a private Python environment (.venv) in this folder and installs the packages of requirements.txt.
rem Needs Python 3.12 or newer and internet access (about 600 MB of packages); the versions are the tested ones of
rem constraints.txt. Run it once; then start the app with
rem run_app.bat. Running it again repairs or updates the packages.
cd /d "%~dp0"
echo.
echo  OCCD - installing in %CD%
echo.

set "PYL="
py -3 --version >nul 2>nul && set "PYL=py -3"
if not defined PYL python --version >nul 2>nul && set "PYL=python"
if not defined PYL goto nopython

for /f "tokens=2" %%v in ('%PYL% --version 2^>^&1') do set "PYV=%%v"
echo  Python %PYV% found (%PYL%)
%PYL% -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 goto oldpython

if not exist ".venv\Scripts\python.exe" (
    echo  creating the environment .venv ...
    %PYL% -m venv .venv
    if errorlevel 1 goto novenv
)
echo  installing the packages (a few minutes) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt -c constraints.txt
if errorlevel 1 goto pipfailed
".venv\Scripts\python.exe" -c "import streamlit, geopandas, pyogrio, pyproj, scipy, skimage, reportlab, pymupdf; print(' packages OK: streamlit', streamlit.__version__)"
if errorlevel 1 goto pipfailed
echo.
echo  Done. Start the app with run_app.bat (it opens http://localhost:8501 in the browser).
echo.
pause
exit /b 0

:nopython
echo  Python was not found. Install Python 3.12 or newer from https://www.python.org/downloads/
echo  (tick "Add python.exe to PATH" in the installer), or run:  winget install Python.Python.3.14
echo  then run install_occd.bat again.
pause
exit /b 1

:oldpython
echo  OCCD needs Python 3.12 or newer; this computer has %PYV%. Install a newer Python and run this again.
pause
exit /b 1

:novenv
echo  Could not create the environment .venv in %CD% (no write permission?). Copy the OCCD folder to a local folder
echo  of your own (for example C:\Olds College Projects) and run install_occd.bat there.
pause
exit /b 1

:pipfailed
echo  The package installation failed (see the messages above). Check the internet connection (or the proxy) and
echo  run install_occd.bat again.
pause
exit /b 1
