$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:DJANGO_DEBUG = 'true'
$env:DATABASE_ENGINE = 'sqlite'
if (-not $env:DJANGO_SECRET_KEY) {
    # Solo desarrollo: nunca reutilizar esta clave en un servidor público.
    $env:DJANGO_SECRET_KEY = 'development-only-never-use-in-production-7826'
}
& "$projectRoot\.venv\Scripts\python.exe" "$projectRoot\backend\manage.py" migrate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$projectRoot\.venv\Scripts\python.exe" "$projectRoot\backend\manage.py" setup_roles
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$projectRoot\.venv\Scripts\python.exe" "$projectRoot\backend\manage.py" runserver 127.0.0.1:8000
