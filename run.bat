@echo off
cd /d "%~dp0"

echo ==============================
echo Terraria Color Catalog
echo ==============================
echo.

if not exist .venv (
    echo Creation de l'environnement virtuel...
    python -m venv .venv
)

call .venv\Scripts\activate

echo Installation des dependances...
pip install -r requirements.txt

echo.
echo Lancement du site...
echo Ouvre cette adresse dans ton navigateur :
echo http://127.0.0.1:5000
echo.

python app.py

pause