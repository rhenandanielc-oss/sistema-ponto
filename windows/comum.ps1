# Funções compartilhadas pelos scripts do Windows.
# 'Continue': no Windows PowerShell 5.1, 'Stop' transforma mensagens normais do docker (stderr) em erro.
# Falhas de comandos externos são conferidas por $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$ComposeArgs = @('compose', '-f', 'docker-compose.local.yml')

function Stop-WithError([string]$Message) {
    Write-Host ''
    Write-Host $Message -ForegroundColor Red
    Read-Host 'Pressione Enter para fechar'
    exit 1
}

function Read-EnvFile {
    $values = @{}
    if (Test-Path (Join-Path $Root '.env')) {
        foreach ($line in Get-Content (Join-Path $Root '.env') -Encoding UTF8) {
            if ($line -match '^\s*([A-Z_]+)=(.*)$') {
                $values[$Matches[1]] = $Matches[2].Trim("'")
            }
        }
    }
    return $values
}

function Get-AppPort {
    $port = (Read-EnvFile)['PORT']
    if ($port) { return $port }
    return '80'
}

function Get-AppUrl([string]$Path) {
    $port = Get-AppPort
    if ($port -eq '80') { return "http://localhost$Path" }
    return "http://localhost:$port$Path"
}

function Test-DockerRunning {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
    $null = docker info 2>&1
    return $LASTEXITCODE -eq 0
}

function Wait-System([int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 (Get-AppUrl '/api/v1/health/ready')
            if ($response.StatusCode -eq 200) { return $true }
        } catch { }
        Start-Sleep -Seconds 5
    }
    return $false
}
