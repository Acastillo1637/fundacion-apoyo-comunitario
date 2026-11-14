param([Parameter(Mandatory=$true)][string]$BackupFile, [switch]$ConfirmEmptyTarget)
$ErrorActionPreference = 'Stop'
if (-not $ConfirmEmptyTarget) { throw 'Usa -ConfirmEmptyTarget únicamente después de preparar una base de recuperación vacía.' }
$backup=(Resolve-Path -LiteralPath $BackupFile).Path
foreach ($name in @('RESTORE_POSTGRES_HOST','RESTORE_POSTGRES_DB','RESTORE_POSTGRES_USER')) {
    if (-not [Environment]::GetEnvironmentVariable($name,'Process')) { throw "Falta $name. El destino de restauración se configura por separado." }
}
$pgRestore=(Get-Command pg_restore -ErrorAction Stop).Source
$psql=(Get-Command psql -ErrorAction Stop).Source
$names=@('PGHOST','PGPORT','PGDATABASE','PGUSER','PGPASSWORD','PGSSLMODE','PGSSLROOTCERT','PGCONNECT_TIMEOUT')
$previous=@{}
$restoreList=$null
foreach($name in $names){$previous[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
try {
    $env:PGHOST=$env:RESTORE_POSTGRES_HOST; $env:PGDATABASE=$env:RESTORE_POSTGRES_DB; $env:PGUSER=$env:RESTORE_POSTGRES_USER
    $env:PGPORT=if($env:RESTORE_POSTGRES_PORT){$env:RESTORE_POSTGRES_PORT}else{'5432'}
    $env:PGPASSWORD=$env:RESTORE_POSTGRES_PASSWORD; $env:PGSSLMODE=if($env:RESTORE_POSTGRES_SSLMODE){$env:RESTORE_POSTGRES_SSLMODE}else{'require'}
    $env:PGSSLROOTCERT=$env:RESTORE_POSTGRES_SSLROOTCERT; $env:PGCONNECT_TIMEOUT='10'
    $tables=& $psql --no-psqlrc --tuples-only --no-align --command "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';"
    if($LASTEXITCODE -ne 0){throw 'No se pudo comprobar el destino.'}
    if([int]($tables | Select-Object -Last 1) -ne 0){throw 'El destino contiene tablas; no se sobrescribe ni borra información.'}
    # PostgreSQL crea public en una base nueva. Conservarlo evita borrarlo o
    # cambiar sus permisos; restaurar únicamente los objetos del respaldo.
    $entries=& $pgRestore --list $backup
    if($LASTEXITCODE -ne 0){throw 'No se pudo leer el índice del respaldo.'}
    $restoreList=Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString('N')+'.restore-list')
    $filteredEntries=@($entries | Where-Object { $_ -notmatch '^\d+; \d+ \d+ SCHEMA - public ' })
    [IO.File]::WriteAllLines($restoreList,[string[]]$filteredEntries,[Text.UTF8Encoding]::new($false))
    & $pgRestore --use-list $restoreList --exit-on-error --single-transaction --no-owner --no-acl --dbname $env:PGDATABASE $backup
    if($LASTEXITCODE -ne 0){throw 'La restauración falló y se revirtió la transacción.'}
    Write-Output 'Restauración completada en el destino previamente vacío. Verifica migraciones, conteos y archivos antes de cambiar la aplicación.'
} finally {
    if($restoreList -and (Test-Path -LiteralPath $restoreList)){Remove-Item -LiteralPath $restoreList}
    foreach($name in $names){if ($null -eq $previous[$name] -or $previous[$name] -eq '') { Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue } else { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }}
}
