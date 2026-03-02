@echo off
chcp 65001 >nul
title Installation Whisper Helio v1.4b

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║         INSTALLATION WHISPER HELIO v1.4b                     ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.
echo  Ce script va créer un raccourci sur votre bureau.
echo.
pause

echo.
echo [1/1] Création du raccourci sur le bureau...

:: Obtenir le chemin du dossier actuel (où se trouve l'exe)
set "CURRENT_DIR=%~dp0"
:: Enlever le \ final si présent
if "%CURRENT_DIR:~-1%"=="\" set "CURRENT_DIR=%CURRENT_DIR:~0,-1%"
set "EXE_PATH=%CURRENT_DIR%\WhisperHelio.exe"
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\Whisper Helio.lnk"

:: Vérifier que l'exe existe
if not exist "%EXE_PATH%" (
    echo.
    echo  ERREUR : WhisperHelio.exe non trouvé !
    echo  Chemin cherché : %EXE_PATH%
    echo.
    echo  Assurez-vous de lancer ce script depuis le dossier
    echo  qui contient WhisperHelio.exe
    echo.
    pause
    exit /b 1
)

:: Supprimer l'ancien raccourci s'il existe
if exist "%SHORTCUT_PATH%" del "%SHORTCUT_PATH%"

:: Créer le raccourci avec PowerShell (avec WorkingDirectory correct)
powershell -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
    $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); ^
    $s.TargetPath = '%EXE_PATH%'; ^
    $s.WorkingDirectory = '%CURRENT_DIR%'; ^
    $s.Description = 'Whisper Helio v1.4b - Dictée vocale offline'; ^
    $s.Save(); ^
    Write-Host 'Raccourci créé avec succès'"

if exist "%SHORTCUT_PATH%" (
    echo.
    echo       ✓ Raccourci créé sur le bureau !
    echo.
    echo       Cible : %EXE_PATH%
    echo       Démarrer dans : %CURRENT_DIR%
) else (
    echo.
    echo       ✗ ERREUR - Impossible de créer le raccourci
    echo.
    echo       Créez-le manuellement :
    echo       1. Clic droit sur WhisperHelio.exe
    echo       2. "Envoyer vers" puis "Bureau (créer un raccourci)"
)

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║              INSTALLATION TERMINÉE !                         ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.
echo  Vous pouvez maintenant lancer Whisper Helio depuis le bureau.
echo.
echo  ⚠ PREMIER LANCEMENT : Le modèle Whisper sera téléchargé (~3 GB)
echo     Cela peut prendre plusieurs minutes selon votre connexion.
echo     Une fenêtre de chargement s'affichera.
echo.
echo  RACCOURCIS :
echo    F9 : Maintenir pour dicter, relâcher pour transcrire
echo    Bouton vert : Mode réunion (enregistrement continu)
echo.
pause
