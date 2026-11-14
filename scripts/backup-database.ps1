param([switch]$SharedDevelopment, [string]$OutputDirectory, [string]$PrivateDocumentsPath)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if ($SharedDevelopment) { . (Join-Path $PSScriptRoot 'load-shared-env.ps1') }
foreach ($name in @('POSTGRES_HOST','POSTGRES_DB','POSTGRES_USER')) {
    if (-not [Environment]::GetEnvironmentVariable($name,'Process')) { throw "Falta $name en el entorno del respaldo." }
}
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $projectRoot 'backups' }
$destination = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $destination | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$backup = Join-Path $destination ("database-$stamp.dump")
$pgDump = (Get-Command pg_dump -ErrorAction Stop).Source
$names = @('PGHOST','PGPORT','PGDATABASE','PGUSER','PGPASSWORD','PGSSLMODE','PGSSLROOTCERT','PGCONNECT_TIMEOUT')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
try {
    $env:PGHOST=$env:POSTGRES_HOST; $env:PGPORT=$env:POSTGRES_PORT
    if (-not $env:PGPORT) { $env:PGPORT='5432' }
    if ($env:PGHOST.EndsWith('.pooler.supabase.com') -and $env:PGPORT -eq '6543') { $env:PGPORT='5432' }
    $env:PGDATABASE=$env:POSTGRES_DB; $env:PGUSER=$env:POSTGRES_USER; $env:PGPASSWORD=$env:POSTGRES_PASSWORD
    $env:PGSSLMODE=if($env:POSTGRES_SSLMODE){$env:POSTGRES_SSLMODE}else{'require'}
    $env:PGSSLROOTCERT=$env:POSTGRES_SSLROOTCERT; $env:PGCONNECT_TIMEOUT='10'
    & $pgDump --format=custom --schema=public --no-owner --no-acl --file $backup
    if ($LASTEXITCODE -ne 0) { throw 'Falló pg_dump. El archivo parcial no debe usarse como respaldo válido.' }
    $manifest=@{ created_at=$stamp; database_file=[IO.Path]::GetFileName($backup); sha256=(Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash; schema='public'; documents_included=$false }
    if ($PrivateDocumentsPath) {
        $documents=(Resolve-Path -LiteralPath $PrivateDocumentsPath).Path
        $archive=Join-Path $destination ("documents-$stamp.zip")
        Compress-Archive -LiteralPath $documents -DestinationPath $archive
        $manifest.documents_included=$true
        $manifest.documents_file=[IO.Path]::GetFileName($archive)
        $manifest.documents_sha256=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
    }
    $manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destination ("manifest-$stamp.json")) -Encoding UTF8
    Write-Output "Respaldo creado: $backup"
    Write-Output 'Conserva el archivo y el manifiesto en almacenamiento privado; no los subas a GitHub.'
} finally {
    foreach ($name in $names) { if ($null -eq $previous[$name] -or $previous[$name] -eq '') { Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue } else { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') } }
}
