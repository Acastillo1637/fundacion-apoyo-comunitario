param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$DjangoArguments
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:DJANGO_DEBUG = 'true'
$env:DATABASE_ENGINE = 'sqlite'
if (-not $env:DJANGO_SECRET_KEY) {
    $env:DJANGO_SECRET_KEY = 'development-only-never-use-in-production-7826'
}
& "$projectRoot\.venv\Scripts\python.exe" "$projectRoot\backend\manage.py" @DjangoArguments
exit $LASTEXITCODE
