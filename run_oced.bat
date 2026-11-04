@echo off
rem OCED - Olds College Extract Data: start the Streamlit app (it opens in the browser at http://localhost:8502)
rem Part of OCCD: raw yield data of any monitor OCCD reads -> maps of every attribute -> SMS 3-sigma -> clean
rem shapefiles. The private environment .venv of install_occd.bat is used when it exists, else the Python on
rem the PATH. OCCD (run_app.bat, port 8501) and OCED can run at the same time.
cd /d "%~dp0"
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
"%PY%" -m streamlit run app\oced.py --server.port 8502
pause
