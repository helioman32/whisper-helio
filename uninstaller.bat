@echo off
chcp 65001 >nul
title Désinstallation Whisper Helio v1.3

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║         DÉSINSTALLATION WHISPER HELIO v1.3                   ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.
echo  Ce script va supprimer :
echo    - Le fichier de configuration
echo    - Le fichier de log
echo    - Le cache du modèle Whisper (optionnel)
echo.
echo  L'application elle-même ne sera pas supprimée.
echo  Vous pouvez simplement supprimer le dossier manuellement.
echo.
pause

echo.
echo [1/3] Suppression du fichier de configuration...
if exist "%USERPROFILE%\whisper_helio_config.json" (
    del "%USERPROFILE%\whisper_helio_config.json"
    echo       OK - Configuration supprimée
) else (
    echo       Fichier non trouvé (déjà supprimé)
)

echo.
echo [2/3] Suppression du fichier de log...
if exist "%USERPROFILE%\whisper_helio_crash.log" (
    del "%USERPROFILE%\whisper_helio_crash.log"
    echo       OK - Log supprimé
) else (
    echo       Fichier non trouvé (déjà supprimé)
)

echo.
echo [3/3] Cache du modèle Whisper...
echo.
echo  Le cache Whisper peut prendre plusieurs Go.
echo  Voulez-vous le supprimer ? (Vous devrez re-télécharger le modèle)
echo.
set /p choix="Supprimer le cache Whisper ? (O/N) : "
if /i "%choix%"=="O" (
    if exist "%USERPROFILE%\.cache\huggingface\hub" (
        rmdir /s /q "%USERPROFILE%\.cache\huggingface\hub"
        echo       OK - Cache Whisper supprimé
    ) else (
        echo       Cache non trouvé
    )
) else (
    echo       Cache conservé
)

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║              DÉSINSTALLATION TERMINÉE                        ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.
echo  Vous pouvez maintenant supprimer le dossier Whisper Helio.
echo.
echo  Merci d'avoir utilisé Whisper Helio !
echo  https://github.com/helioman32/whisper-helio
echo.
pause
