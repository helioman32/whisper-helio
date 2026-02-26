@echo off
title Whisper Helio - Installation
color 0A
cls

echo.
echo  ==========================================
echo      WHISPER HELIO - Installation
echo      Version GPU (NVIDIA CUDA)
echo  ==========================================
echo.

:: Verification Python
echo  [1/6] Verification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERREUR : Python n'est pas installe !
    echo  Telechargez Python sur https://www.python.org/downloads/
    echo  IMPORTANT : Cochez "Add Python to PATH" lors de l'installation !
    echo.
    pause
    exit
)
python --version
echo  OK !
echo.

:: Mise a jour pip
echo  [2/6] Mise a jour de pip...
python -m pip install --upgrade pip --quiet
echo  OK !
echo.

:: Installation dependances principales
echo  [3/6] Installation des dependances...
python -m pip install faster-whisper --quiet
python -m pip install sounddevice --quiet
python -m pip install numpy --quiet
python -m pip install pyperclip --quiet
python -m pip install pyautogui --quiet
python -m pip install soundfile --quiet
python -m pip install pynput --quiet
python -m pip install keyboard --quiet
echo  OK !
echo.

:: Detection GPU NVIDIA
echo  [4/6] Detection de votre materiel...
python -c "import torch; print('  GPU detecte : ' + torch.cuda.get_device_name(0)) if torch.cuda.is_available() else print('  Aucun GPU NVIDIA detecte - utilisation CPU')" 2>nul
if errorlevel 1 (
    echo  Installation de PyTorch avec support CUDA...
    python -m pip install torch --quiet
    python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --quiet
)
echo  OK !
echo.

:: Creation du raccourci
echo  [5/6] Creation du raccourci sur le Bureau...
set SCRIPT_DIR=%~dp0
set DESKTOP=%USERPROFILE%\Desktop
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\Whisper Helio.lnk'); $s.TargetPath = 'pythonw'; $s.Arguments = '%SCRIPT_DIR%dictee.pyw'; $s.IconLocation = '%SCRIPT_DIR%whisper_helio.ico'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Save()" 2>nul
echo  OK !
echo.

:: Demarrage automatique Windows
echo  [6/6] Configuration du demarrage automatique...
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP%\Whisper Helio.lnk'); $s.TargetPath = 'pythonw'; $s.Arguments = '%SCRIPT_DIR%dictee.pyw'; $s.IconLocation = '%SCRIPT_DIR%whisper_helio.ico'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Save()" 2>nul
echo  OK !
echo.

echo  ==========================================
echo    Installation terminee avec succes !
echo  ==========================================
echo.
echo  Un raccourci "Whisper Helio" a ete cree sur votre Bureau.
echo  Le logiciel se lancera automatiquement au demarrage de Windows.
echo.
echo  IMPORTANT : Au premier lancement, le modele Whisper sera
echo  telecharge automatiquement (~3 Go). Une connexion internet
echo  est necessaire uniquement pour ce premier telechargement.
echo.
echo  Voulez-vous lancer Whisper Helio maintenant ? (O/N)
set /p LAUNCH=
if /i "%LAUNCH%"=="O" (
    start "" pythonw "%SCRIPT_DIR%dictee.pyw"
)
echo.
pause
