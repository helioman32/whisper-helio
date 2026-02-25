@echo off
title Whisper Helio - Installation
color 0A
cls

if "%1"=="" (
    cmd /k "%~f0" run
    exit /b
)

echo.
echo  ==========================================
echo      WHISPER HELIO v1.2 - Installation
echo  ==========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%SCRIPT_DIR%Whisper Helio.exe"
set "ICON_PATH=%SCRIPT_DIR%whisper_helio.ico"
set "DESKTOP=%USERPROFILE%\Desktop"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

:: ── Verification ─────────────────────────────────────────────────────────
echo  [1/3] Verification des fichiers...
if not exist "%EXE_PATH%" (
    echo.
    echo  ERREUR : "Whisper Helio.exe" est introuvable !
    echo  Extrayez tous les fichiers du ZIP dans le meme dossier.
    echo.
    pause
    exit /b 1
)
if not exist "%SCRIPT_DIR%_internal" (
    echo.
    echo  ERREUR : Le dossier "_internal" est introuvable !
    echo  Extrayez TOUS les fichiers du ZIP, ne rien supprimer.
    echo.
    pause
    exit /b 1
)
echo  OK - Fichiers trouves !
echo.

:: ── Raccourci Bureau ──────────────────────────────────────────────────────
echo  [2/3] Creation du raccourci sur le Bureau...
powershell -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\Whisper Helio.lnk'); $s.TargetPath = '%EXE_PATH%'; $s.IconLocation = '%ICON_PATH%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Whisper Helio - Dictee vocale'; $s.Save()"

if exist "%DESKTOP%\Whisper Helio.lnk" (
    echo  OK - Raccourci cree sur le Bureau !
) else (
    echo  ECHEC - Le raccourci Bureau n'a pas pu etre cree.
)
echo.

:: ── Demarrage automatique ────────────────────────────────────────────────
echo  [3/3] Configuration du demarrage automatique...
powershell -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP%\Whisper Helio.lnk'); $s.TargetPath = '%EXE_PATH%'; $s.IconLocation = '%ICON_PATH%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Whisper Helio - Dictee vocale'; $s.Save()"

if exist "%STARTUP%\Whisper Helio.lnk" (
    echo  OK - Demarrage automatique configure !
) else (
    echo  ECHEC - Le demarrage automatique n'a pas pu etre configure.
)
echo.

:: ── Resume ────────────────────────────────────────────────────────────────
echo  ==========================================
echo    Installation terminee avec succes !
echo  ==========================================
echo.
echo  - Raccourci cree sur votre Bureau
echo  - Whisper Helio demarrera automatiquement avec Windows
echo.
echo  IMPORTANT : Au premier lancement, le modele Whisper sera
echo  telecharge automatiquement (~3 Go). Connexion internet
echo  requise uniquement pour ce premier telechargement.
echo.
echo  Voulez-vous lancer Whisper Helio maintenant ? (O/N)
set /p LAUNCH=
if /i "%LAUNCH%"=="O" (
    echo.
    echo  Lancement de Whisper Helio...
    start "" "%EXE_PATH%"
)
echo.
pause
