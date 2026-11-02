$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$sharedConfig = Join-Path $projectRoot '.env.shared'
if (-not (Test-Path -LiteralPath $sharedConfig)) {
    throw 'Falta .env.shared. Copia config/shared-database.env.example a .env.shared y completa la conexion privada.'
}
$allowedNames = @('POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_SSLMODE', 'DJANGO_SECRET_KEY')
$configuration = @{}
foreach ($line in Get-Content -LiteralPath $sharedConfig -Encoding UTF8) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
    $parts = $trimmed.Split('=', 2)
    if ($parts.Length -ne 2 -or $parts[0].Trim() -notin $allowedNames) {
        throw 'El archivo .env.shared contiene una linea no reconocida. Usa la plantilla sin agregar comandos.'
    }
    $value = $parts[1].Trim()
    if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    $configuration[$parts[0].Trim()] = $value
}
foreach ($name in @('POSTGRES_HOST', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'DJANGO_SECRET_KEY')) {
    if (-not $configuration[$name]) { throw "Falta completar $name en .env.shared." }
}
if ($configuration['DJANGO_SECRET_KEY'].Length -lt 50) { throw 'Usa una clave DJANGO_SECRET_KEY privada de al menos 50 caracteres.' }
if (-not $configuration['POSTGRES_PORT']) { $configuration['POSTGRES_PORT'] = '6543' }
if ($configuration['POSTGRES_PORT'] -notin @('5432', '6543')) { throw 'Usa el puerto 5432 (Session pooler) o 6543 (Transaction pooler).' }
if (-not $configuration['POSTGRES_SSLMODE']) { $configuration['POSTGRES_SSLMODE'] = 'require' }
if ($configuration['POSTGRES_SSLMODE'] -notin @('require', 'verify-ca', 'verify-full')) { throw 'La base compartida debe usar una conexion SSL.' }
foreach ($name in $configuration.Keys) { [Environment]::SetEnvironmentVariable($name, $configuration[$name], 'Process') }
$env:DATABASE_ENGINE = 'postgresql'
$env:DJANGO_DEBUG = 'true'
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1'
$env:DJANGO_CSRF_TRUSTED_ORIGINS = 'http://127.0.0.1:5173,http://localhost:5173'
$env:PUBLIC_APP_URL = 'http://127.0.0.1:5173'
$env:EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
