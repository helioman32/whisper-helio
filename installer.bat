@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Installation Whisper Helio v1.4b

echo.
echo  ========================================================
echo          INSTALLATION WHISPER HELIO v1.4b
echo  ========================================================
echo.
echo  Ce script va :
echo    - Verifier et installer les pilotes CUDA - GPU NVIDIA
echo    Le raccourci bureau sera cree au premier lancement de l'application.
echo.
pause

:: ── Chemins ──────────────────────────────────────────────
set "CURRENT_DIR=%~dp0"
if "!CURRENT_DIR:~-1!"=="\" set "CURRENT_DIR=!CURRENT_DIR:~0,-1!"
set "EXE_PATH=!CURRENT_DIR!\WhisperHelio.exe"
set "ICO_PATH=!CURRENT_DIR!\whisper_helio.ico"

if not exist "!EXE_PATH!" (
    echo.
    echo  ERREUR : WhisperHelio.exe non trouve !
    echo  Chemin cherche : !EXE_PATH!
    echo.
    echo  Assurez-vous de lancer ce script depuis le dossier
    echo  qui contient WhisperHelio.exe
    echo.
    pause
    exit /b 1
)

:: ── Etape 1 : Detection GPU NVIDIA ──────────────────────
echo.
echo [1/3] Detection du GPU NVIDIA...

set "GPU_NAME="
nvidia-smi --query-gpu=name --format=csv,noheader >nul 2>&1
if !ERRORLEVEL! NEQ 0 goto :no_gpu

for /f "tokens=*" %%a in ('nvidia-smi --query-gpu=name --format=csv,noheader 2^>nul') do (
    set "GPU_NAME=%%a"
    echo       GPU detecte : %%a
)
goto :gpu_found

:no_gpu
echo       Aucun GPU NVIDIA detecte.
echo       L'application fonctionnera en mode CPU - plus lent.
echo.
goto :skip_cuda

:gpu_found

:: ── Etape 2 : Verification DLLs CUDA ────────────────────
echo.
echo [2/3] Verification des bibliotheques CUDA...

set "CUDA_FOUND=0"

:: Chercher cublas64_12.dll dans le CUDA Toolkit
if defined CUDA_PATH (
    if exist "!CUDA_PATH!\bin\cublas64_12.dll" (
        echo       CUDA trouve : !CUDA_PATH!\bin
        set "CUDA_FOUND=1"
        goto :cuda_ok
    )
)

:: Chemins CUDA Toolkit standards
for %%v in (v12.8 v12.6 v12.4 v12.2 v12.1) do (
    if exist "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\%%v\bin\cublas64_12.dll" (
        echo       CUDA trouve : CUDA Toolkit %%v
        set "CUDA_FOUND=1"
        goto :cuda_ok
    )
)

:: Chercher via torch - Python
for %%v in (Python313 Python312 Python311 Python310) do (
    if exist "!LOCALAPPDATA!\Programs\Python\%%v\Lib\site-packages\torch\lib\cublas64_12.dll" (
        echo       CUDA trouve via PyTorch : %%v
        set "CUDA_FOUND=1"
        goto :cuda_ok
    )
)

:: Chercher via nvidia pip packages
for %%v in (Python313 Python312 Python311 Python310) do (
    if exist "!LOCALAPPDATA!\Programs\Python\%%v\Lib\site-packages\nvidia\cublas\bin\cublas64_12.dll" (
        echo       CUDA trouve via nvidia-cublas : %%v
        set "CUDA_FOUND=1"
        goto :cuda_ok
    )
)

:: ── CUDA non trouve ─────────────────────────────────────
if "!CUDA_FOUND!"=="1" goto :cuda_ok

echo.
echo  ========================================================
echo       CUDA NON INSTALLE - Installation necessaire
echo  ========================================================
echo.
echo  Votre GPU !GPU_NAME! est detecte mais les bibliotheques
echo  CUDA ne sont pas installees. Sans elles, la transcription
echo  sera 20x plus lente : CPU au lieu de GPU.
echo.
echo  Voulez-vous installer CUDA automatiquement ?
echo.
set /p "INSTALL_CUDA=  Installer CUDA ? [O/N] : "
if /i "!INSTALL_CUDA!"=="O" goto :do_install_cuda
if /i "!INSTALL_CUDA!"=="Y" goto :do_install_cuda
echo.
echo  Installation CUDA ignoree. Mode CPU active.
goto :skip_cuda

:do_install_cuda
echo.
echo  Installation de CUDA en cours...
echo.

:: ── Methode 1 : winget ──────────────────────────────────
echo  Tentative via Windows Package Manager - winget...
where winget >nul 2>&1
if !ERRORLEVEL! NEQ 0 goto :try_pip

echo  winget detecte - installation du CUDA Toolkit...
echo.
winget install --id Nvidia.CUDA --accept-package-agreements --accept-source-agreements 2>nul
if !ERRORLEVEL! EQU 0 (
    echo.
    echo  CUDA Toolkit installe avec succes via winget !
    echo  IMPORTANT : Redemarrez votre PC pour finaliser.
    echo.
    set "CUDA_FOUND=1"
    goto :skip_cuda
)
echo  winget : installation echouee, tentative methode 2...
echo.

:try_pip
:: ── Methode 2 : pip install nvidia-cublas ────────────────
echo  Recherche de Python pour installer les DLL CUDA...
where python >nul 2>&1
if !ERRORLEVEL! NEQ 0 goto :try_curl

echo  Python detecte - installation des bibliotheques CUDA via pip...
echo  Telechargement d'environ 200 Mo
echo.
python -m pip install --upgrade nvidia-cublas-cu12 nvidia-cuda-runtime-cu12 2>nul
if !ERRORLEVEL! EQU 0 (
    echo.
    echo  Bibliotheques CUDA installees via pip !
    echo.
    set "CUDA_FOUND=1"
    goto :skip_cuda
)
echo  pip : installation echouee, tentative methode 3...
echo.

:try_curl
:: ── Methode 3 : Telechargement direct CUDA Toolkit ──────
echo  Telechargement du CUDA Toolkit depuis NVIDIA...
echo.
set "CUDA_INSTALLER=!TEMP!\cuda_installer.exe"
set "CUDA_URL=https://developer.download.nvidia.com/compute/cuda/12.6.3/local_installers/cuda_12.6.3_561.17_windows.exe"

where curl >nul 2>&1
if !ERRORLEVEL! NEQ 0 goto :try_browser

echo  Telechargement en cours - environ 3 Go, patientez...
echo  URL: !CUDA_URL!
echo.
curl -L -o "!CUDA_INSTALLER!" "!CUDA_URL!" --progress-bar
if exist "!CUDA_INSTALLER!" (
    echo.
    echo  Telechargement termine ! Lancement de l'installateur NVIDIA...
    echo  Suivez les instructions de l'installateur NVIDIA.
    echo.
    start /wait "" "!CUDA_INSTALLER!"
    echo.
    echo  Si l'installation s'est bien passee, redemarrez votre PC.
    del "!CUDA_INSTALLER!" >nul 2>&1
    set "CUDA_FOUND=1"
    goto :skip_cuda
)

:try_browser
:: ── Methode 4 : Ouvrir le navigateur ────────────────────
echo.
echo  ========================================================
echo       INSTALLATION AUTOMATIQUE IMPOSSIBLE
echo  ========================================================
echo.
echo  Installez manuellement le CUDA Toolkit :
echo.
echo    1. Le navigateur va s'ouvrir sur la page NVIDIA
echo    2. Selectionnez : Windows - x86_64 - 11 - exe local
echo    3. Telechargez et installez
echo    4. Redemarrez votre PC
echo    5. Relancez Whisper Helio
echo.
echo  Ouverture du navigateur...
start https://developer.nvidia.com/cuda-12-6-0-download-archive
echo.
echo  Appuyez sur une touche apres avoir installe CUDA...
pause >nul

goto :skip_cuda

:cuda_ok
echo       Le GPU sera utilise pour la transcription rapide.

:skip_cuda

:: ── Raccourci bureau ─────────────────────────────────────
:: Le raccourci est cree automatiquement par l'application au premier lancement.
:: Pas besoin de le creer ici — evite les doublons sur le bureau.

echo.
echo  ========================================================
echo              INSTALLATION TERMINEE !
echo  ========================================================
echo.
echo  Vous pouvez maintenant lancer Whisper Helio depuis le bureau.
echo.
echo  PREMIER LANCEMENT : Le modele Whisper sera telecharge - environ 1.5 Go
echo     Cela peut prendre plusieurs minutes selon votre connexion.
echo.
if "!CUDA_FOUND!"=="1" (
    echo  MODE : GPU - transcription rapide, moins de 1 seconde
    echo.
    echo  IMPORTANT : Si vous venez d'installer CUDA, redemarrez
    echo  votre PC avant de lancer Whisper Helio.
) else (
    echo  MODE : CPU - installez CUDA Toolkit 12 pour activer le GPU
    echo  La transcription sera plus lente sans GPU.
)
echo.
echo  RACCOURCIS :
echo    F9 : Maintenir pour dicter, relacher pour transcrire
echo    Bouton vert : Mode reunion - enregistrement continu
echo.
echo  Lancement de Whisper Helio...
echo  Le raccourci bureau sera cree automatiquement au premier lancement.
echo.
echo  NOTE : Si votre antivirus bloque l'application, autorisez-la
echo  puis relancez depuis le raccourci sur le bureau.
echo.
start "" "!EXE_PATH!"
timeout /t 3 /nobreak >nul
endlocal
