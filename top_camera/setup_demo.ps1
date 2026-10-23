$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12, then run this script again.' }
}
& '.venv/Scripts/python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
New-Item -ItemType Directory -Force models | Out-Null
$modelPath = Join-Path $PSScriptRoot 'models/pose_landmarker_full.task'
if (-not (Test-Path -LiteralPath $modelPath)) {
    Invoke-WebRequest 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task' -OutFile $modelPath
}
Write-Output 'Setup complete. Run start_demo.bat.'
