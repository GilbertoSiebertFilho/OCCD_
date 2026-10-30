@echo off
rem OCCD - Olds College Cleaning Data: start the Streamlit app (it opens in the browser at http://localhost:8501)
rem The private environment .venv of install_occd.bat is used when it exists, else the Python on the PATH.
cd /d "%~dp0"
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
"%PY%" -m streamlit run app\app.py
pause
