$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'load-shared-env.ps1')
# Las migraciones se aplican por una sola persona, no automaticamente desde ambos equipos.
& "$projectRoot\.venv\Scripts\python.exe" "$projectRoot\backend\manage.py" runserver 127.0.0.1:8000
exit $LASTEXITCODE
