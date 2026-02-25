@echo off
title Whisper Helio - Desinstallation
color 0C
cls

if "%1"=="" (
    cmd /k "%~f0" run
    exit /b
)

echo.
echo  ==========================================
echo      WHISPER HELIO v1.2 - Desinstallation
echo  ==========================================
echo.

set "DESKTOP=%USERPROFILE%\Desktop"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SCRIPT_DIR=%~dp0"

:: ── Fermeture du logiciel ─────────────────────────────────────────────────
echo  [1/4] Fermeture de Whisper Helio...
taskkill /f /im "Whisper Helio.exe" >nul 2>&1
echo  OK !
echo.

:: ── Suppression raccourci Bureau ─────────────────────────────────────────
echo  [2/4] Suppression du raccourci Bureau...
if exist "%DESKTOP%\Whisper Helio.lnk" (
    del "%DESKTOP%\Whisper Helio.lnk"
    echo  OK - Raccourci Bureau supprime !
) else (
    echo  (aucun raccourci trouve sur le Bureau)
)
echo.

:: ── Suppression demarrage automatique ────────────────────────────────────
echo  [3/4] Suppression du demarrage automatique...
if exist "%STARTUP%\Whisper Helio.lnk" (
    del "%STARTUP%\Whisper Helio.lnk"
    echo  OK - Demarrage automatique supprime !
) else (
    echo  (aucune entree de demarrage automatique trouvee)
)
echo.

:: ── Suppression fichiers de configuration ────────────────────────────────
echo  [4/4] Suppression des fichiers de configuration...
if exist "%USERPROFILE%\whisper_helio_config.json" (
    del "%USERPROFILE%\whisper_helio_config.json"
    echo  OK - Configuration supprimee !
)
if exist "%USERPROFILE%\whisper_helio_crash.log" (
    del "%USERPROFILE%\whisper_helio_crash.log"
    echo  OK - Fichier de log supprime !
)
echo.

:: ── Cache modeles Whisper ────────────────────────────────────────────────
echo  ==========================================
echo.
echo  Voulez-vous supprimer le cache des modeles
echo  Whisper (~3 Go) ? (O/N)
echo  (Ces fichiers seront retelecharges si vous
echo   reinstallez le logiciel)
echo.
set /p CACHE=
if /i "%CACHE%"=="O" (
    if exist "%USERPROFILE%\.cache\huggingface" (
        rmdir /s /q "%USERPROFILE%\.cache\huggingface"
        echo  OK - Cache Whisper supprime !
    ) else (
        echo  (aucun cache trouve)
    )
)
echo.

:: ── Suppression dossier logiciel ────────────────────────────────────────
echo  ==========================================
echo.
echo  Voulez-vous supprimer le dossier complet
echo  de Whisper Helio ? (O/N)
echo  ATTENTION : cette action est irreversible !
echo.
set /p FOLDER=
if /i "%FOLDER%"=="O" (
    echo.
    echo  Suppression du dossier en cours...
    cd "%USERPROFILE%"
    rmdir /s /q "%SCRIPT_DIR%"
    echo  OK - Dossier supprime !
)
echo.

echo  ==========================================
echo    Desinstallation terminee !
echo    Merci d'avoir utilise Whisper Helio.
echo  ==========================================
echo.
pause
