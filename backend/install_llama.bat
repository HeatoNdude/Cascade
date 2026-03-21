@echo off
REM ============================================
REM  Install llama-cpp-python with CUDA 12.4
REM  Run this from: D:\Projects\cascade\cascade\backend
REM ============================================

echo Locating Visual Studio Build Tools...
for /f "usebackq tokens=*" %%i in (`"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -property installationPath`) do (
  set VS_PATH=%%i
)

if not defined VS_PATH (
    echo ERROR: Visual Studio not found!
    exit /b 1
)

echo Visual Studio found at: %VS_PATH%
echo Setting up MSVC environment...
call "%VS_PATH%\VC\Auxiliary\Build\vcvarsall.bat" x64

echo Setting CUDA environment variables...
set CUDACXX=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin\nvcc.exe
set CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4
set CUDAToolkit_ROOT=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4
set CMAKE_CUDA_COMPILER=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin\nvcc.exe
set PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin;%PATH%
set CMAKE_ARGS=-DGGML_CUDA=on
set FORCE_CMAKE=1

echo Verifying nvcc...
nvcc --version
if errorlevel 1 (
    echo ERROR: nvcc not found. Check CUDA Toolkit installation.
    exit /b 1
)

echo Installing llama-cpp-python with CUDA support...
echo This will take 15-30 minutes to compile.

.venv\Scripts\python.exe -m pip install llama-cpp-python --force-reinstall --no-cache-dir

echo Verifying installation...
.venv\Scripts\python.exe -c "from llama_cpp import Llama; print('llama-cpp-python CUDA OK')"

echo Done!
