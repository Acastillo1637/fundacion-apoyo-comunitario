param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$DjangoArguments
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'load-shared-env.ps1')
if (-not $DjangoArguments) { throw 'Indica un comando, por ejemplo: check, migrate o showmigrations.' }
if ($DjangoArguments[0] -in @('test', 'flush', 'reset_db')) {
    throw 'No ejecutes pruebas ni vaciados sobre la base compartida. Usa check-backend.ps1 para las pruebas aisladas.'
}
& "$projectRoot\.venv\Scripts\python.exe" "$projectRoot\backend\manage.py" @DjangoArguments
exit $LASTEXITCODE
