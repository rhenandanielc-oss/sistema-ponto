# Instala (ou atualiza) o Sistema de Ponto neste computador: servidor e terminal ao mesmo tempo.
# Use pelo arquivo instalar.cmd (duplo clique). Guia: INSTALACAO-WINDOWS.md
. (Join-Path $PSScriptRoot 'comum.ps1')

Write-Host '=== Sistema de Ponto - instalação ===' -ForegroundColor Cyan

# 1. Docker Desktop
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Stop-WithError 'Docker Desktop não encontrado. Instale-o (INSTALACAO-WINDOWS.md, passo 1), reinicie o computador e rode de novo.'
}
if (-not (Test-DockerRunning)) {
    Stop-WithError 'O Docker Desktop está instalado, mas não está aberto. Abra o Docker Desktop, espere ficar "Engine running" e rode de novo.'
}
$ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
if ($ramGb -lt 8) {
    Write-Host "Aviso: este computador tem $ramGb GB de memória; o recomendado são 8 GB. Pode ficar lento." -ForegroundColor Yellow
}

# 2. Configuração (.env) com senhas e chaves geradas aqui. Nunca é sobrescrita.
$envPath = Join-Path $Root '.env'
if (Test-Path $envPath) {
    Write-Host 'Configuração (.env) já existe: mantida. As senhas e a chave da biometria não mudam.'
} else {
    function New-RandomBase64([int]$Bytes) {
        $buffer = New-Object byte[] $Bytes
        [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
        return [Convert]::ToBase64String($buffer)
    }
    $dbPassword = (New-RandomBase64 24) -replace '[+/=]', ''
    $jwtSecret = (New-RandomBase64 48) -replace '[+/=]', ''
    $biometricKey = New-RandomBase64 32

    $backupBase = if ($env:OneDrive) { $env:OneDrive } else { [Environment]::GetFolderPath('MyDocuments') }
    $backupDir = Join-Path $backupBase 'Ponto-Backups'
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

    $port = '80'
    if (Get-NetTCPConnection -LocalPort 80 -State Listen -ErrorAction SilentlyContinue) {
        $port = '8080'
        Write-Host 'A porta 80 já está em uso por outro programa; o sistema usará a porta 8080.' -ForegroundColor Yellow
    }

    $content = @(
        '# Gerado por windows\instalar.ps1. NÃO apague e NÃO compartilhe este arquivo.',
        '# Guarde uma cópia em local seguro (pendrive guardado ou cofre de senhas), separada dos backups.',
        "POSTGRES_PASSWORD=$dbPassword",
        "JWT_SECRET=$jwtSecret",
        "BIOMETRIC_KEY=$biometricKey",
        'BIOMETRIC_KEY_ID=k1',
        'APP_TIMEZONE=America/Sao_Paulo',
        "PORT=$port",
        "BACKUP_DIR='$($backupDir -replace '\\', '/')'",
        'BACKUP_KEEP_DAYS=60'
    ) -join "`n"
    [IO.File]::WriteAllText($envPath, $content + "`n", (New-Object Text.UTF8Encoding $false))

    Write-Host ''
    Write-Host 'Configuração criada.' -ForegroundColor Green
    Write-Host "Backups automáticos em: $backupDir"
    if ($env:OneDrive) { Write-Host '(pasta do OneDrive: os backups também ficam guardados na nuvem)' }
    Write-Host ''
    Write-Host '=== IMPORTANTE: guarde a chave da biometria ===' -ForegroundColor Yellow
    Write-Host "  $biometricKey" -ForegroundColor Yellow
    Write-Host 'Sem ela, se o computador estragar, os rostos precisam ser cadastrados de novo.'
    Write-Host 'Anote em papel guardado ou num cofre de senhas. Ela também está no arquivo .env desta pasta.'
    Read-Host 'Depois de guardar a chave, pressione Enter para continuar'
}

# 3. Montar e ligar (a primeira vez demora de 10 a 20 minutos)
Write-Host ''
Write-Host 'Montando e ligando o sistema (a primeira vez demora de 10 a 20 minutos)...' -ForegroundColor Cyan
docker @ComposeArgs up -d --build
if ($LASTEXITCODE -ne 0) { Stop-WithError 'Falha ao montar o sistema. Confira a internet e rode de novo.' }
if (-not (Wait-System 300)) {
    Stop-WithError "O sistema não respondeu. Veja os detalhes com: docker compose -f docker-compose.local.yml logs backend"
}
Write-Host 'Sistema ligado.' -ForegroundColor Green

# 4. Primeiro administrador
# Sem aspas duplas no comando: o PowerShell 5.1 as remove ao chamar programas externos.
$admins = docker @ComposeArgs exec -T db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -tAc ''select count(*) from admins'''
if ("$admins".Trim() -eq '0') {
    Write-Host ''
    Write-Host 'Criar o administrador (único acesso com senha):' -ForegroundColor Cyan
    $email = Read-Host 'E-mail do administrador'
    $name = Read-Host 'Nome do administrador'
    Write-Host 'Digite a senha (mínimo 10 caracteres; ela não aparece na tela):'
    docker @ComposeArgs exec backend python -m app.cli create-admin --email $email --name $name
    if ($LASTEXITCODE -ne 0) { Write-Host 'Administrador não criado. Rode o instalar.cmd de novo para tentar outra vez.' -ForegroundColor Red }
}

# 5. Atalhos
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
$terminal = $shell.CreateShortcut((Join-Path $desktop 'Ponto - Terminal.lnk'))
$terminal.TargetPath = 'powershell.exe'
$terminal.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$(Join-Path $PSScriptRoot 'abrir-terminal.ps1')`""
$terminal.WorkingDirectory = $Root
$terminal.IconLocation = 'shell32.dll,265'
$terminal.Save()
# Mesmo mecanismo do atalho do terminal; nome sem acentos para não depender da codificação do Windows.
$admin = $shell.CreateShortcut((Join-Path $desktop 'Ponto - Administrador.lnk'))
$admin.TargetPath = 'powershell.exe'
$admin.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$(Join-Path $PSScriptRoot 'abrir-administracao.ps1')`""
$admin.WorkingDirectory = $Root
$admin.IconLocation = 'shell32.dll,47'
$admin.Save()
if (-not (Test-Path (Join-Path $desktop 'Ponto - Administrador.lnk'))) {
    Write-Host "Não foi possível criar o atalho do administrador. Abra $(Get-AppUrl '/login') no navegador." -ForegroundColor Yellow
}
Write-Host 'Atalhos criados na Área de Trabalho: "Ponto - Terminal" e "Ponto - Administrador".' -ForegroundColor Green

$startup = Join-Path ([Environment]::GetFolderPath('Startup')) 'Ponto - Terminal.lnk'
$answer = Read-Host 'Abrir o terminal de ponto automaticamente ao ligar o computador? (S/N)'
if ($answer -match '^[sS]') {
    Copy-Item (Join-Path $desktop 'Ponto - Terminal.lnk') $startup -Force
    Write-Host 'Pronto: o terminal abrirá sozinho ao entrar no Windows.'
} elseif (Test-Path $startup) {
    Remove-Item $startup
}

Write-Host ''
Write-Host '=== Instalação concluída ===' -ForegroundColor Green
Write-Host "Administração: $(Get-AppUrl '/login')"
Write-Host 'Próximos passos: INSTALACAO-WINDOWS.md, passo 5 (cadastrar o terminal e os funcionários).'
Read-Host 'Pressione Enter para fechar'
