@echo off
cd /d %~dp0
echo Creating conda env "autotestdesign" ...
conda env create -f environment.yml
if errorlevel 1 (
  echo If env exists, run: conda env update -f environment.yml --prune
  exit /b 1
)
echo.
echo Done. Activate with:
echo   conda activate autotestdesign
echo Then copy .env.example to .env and run streamlit / pytest as in README.
