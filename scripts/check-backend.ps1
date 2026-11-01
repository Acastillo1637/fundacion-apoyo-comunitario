$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:DJANGO_DEBUG = 'true'
$env:DATABASE_ENGINE = 'sqlite'
if (-not $env:DJANGO_SECRET_KEY) {
    $env:DJANGO_SECRET_KEY = 'development-only-never-use-in-production-7826'
}
& "$projectRoot\.venv\Scripts\python.exe" "$projectRoot\backend\manage.py" check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$projectRoot\.venv\Scripts\python.exe" "$projectRoot\backend\manage.py" makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$projectRoot\.venv\Scripts\python.exe" "$projectRoot\backend\manage.py" test accounts volunteers documents activities
exit $LASTEXITCODE
