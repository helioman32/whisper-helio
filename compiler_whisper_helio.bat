@echo off
title Compilation Whisper Helio v1.4b

echo.
echo ---------------------------------------------------------------
echo   COMPILATION WHISPER HELIO v1.4b - Nuitka standalone
echo ---------------------------------------------------------------
echo.

if not exist "dictee.pyw" (
    echo [ERREUR] dictee.pyw introuvable dans ce dossier.
    echo          Lancez ce .bat depuis le dossier du projet.
    pause
    exit /b 1
)

if not exist "whisper_helio.ico" (
    echo [AVERT]  whisper_helio.ico introuvable.
    echo.
)

echo [1/3] Installation Nuitka...
pip install --upgrade nuitka --quiet
if %errorlevel% neq 0 (
    echo [ERREUR] Impossible d installer Nuitka.
    pause
    exit /b 1
)
echo       OK
echo.

echo [2/3] Compilation en cours (3 a 10 minutes)...
echo.

python -m nuitka ^
  --standalone ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=whisper_helio.ico ^
  --output-filename=WhisperHelio.exe ^
  --output-dir=dist ^
  --jobs=%NUMBER_OF_PROCESSORS% ^
  --enable-plugin=tk-inter ^
  --windows-company-name="Whisper Helio" ^
  --windows-product-name="Whisper Helio" ^
  --windows-file-version=1.4.0.0 ^
  --windows-product-version=1.4.0.0 ^
  --windows-file-description="Whisper Helio - Dictee vocale offline" ^
  --include-package=faster_whisper ^
  --include-package=sounddevice ^
  --include-package=keyboard ^
  --include-package=pyperclip ^
  --include-package=pyautogui ^
  --include-package=numpy ^
  --include-package=ctranslate2 ^
  --include-package=huggingface_hub ^
  --noinclude-default-mode=nofollow ^
  --nofollow-import-to=torch ^
  --nofollow-import-to=matplotlib ^
  --nofollow-import-to=scipy ^
  --nofollow-import-to=PIL ^
  --nofollow-import-to=unittest ^
  --nofollow-import-to=pytest ^
  --nofollow-import-to=setuptools ^
  --nofollow-import-to=distutils ^
  --nofollow-import-to=IPython ^
  --nofollow-import-to=jupyter ^
  --nofollow-import-to=notebook ^
  --nofollow-import-to=pandas ^
  --nofollow-import-to=lib2to3 ^
  --assume-yes-for-downloads ^
  dictee.pyw

if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] Compilation echouee.
    pause
    exit /b 1
)

echo.
echo [3/3] Copie des fichiers...
if exist "whisper_helio.ico" (
    copy /y "whisper_helio.ico" "dist\WhisperHelio.dist\" >nul
    echo       whisper_helio.ico copie.
)

echo.
echo ---------------------------------------------------------------
echo   COMPILATION TERMINEE avec succes !
echo   Executable : dist\WhisperHelio.dist\WhisperHelio.exe
echo   Distribuez le dossier WhisperHelio.dist\ complet.
echo ---------------------------------------------------------------
echo.
pause
