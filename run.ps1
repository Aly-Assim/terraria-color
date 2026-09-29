# Convenience launcher; install requirements once using the README instructions.
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $pythonPath = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (!(Test-Path -LiteralPath $pythonPath)) {
        throw 'Create .venv and install requirements.txt first; see README.md.'
    }
    & $pythonPath app.py
    if ($LASTEXITCODE -ne 0) { throw "Python exited with code $LASTEXITCODE" }
}
finally {
    Pop-Location
}
