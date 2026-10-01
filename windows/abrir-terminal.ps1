# Abre o terminal de ponto em tela cheia, esperando o sistema ligar (útil logo após ligar o computador).
. (Join-Path $PSScriptRoot 'comum.ps1')
Add-Type -AssemblyName System.Windows.Forms

if (-not (Wait-System 300)) {
    [System.Windows.Forms.MessageBox]::Show(
        'O sistema de ponto não ligou. Abra o Docker Desktop, espere alguns minutos e abra o atalho "Ponto - Terminal" de novo.',
        'Sistema de Ponto') | Out-Null
    exit 1
}

$browsers = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
)
$browser = $browsers | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) {
    [System.Windows.Forms.MessageBox]::Show('Microsoft Edge ou Google Chrome não encontrado.', 'Sistema de Ponto') | Out-Null
    exit 1
}

# Perfil separado: a chave do terminal e a permissão da câmera ficam só nele.
$profileDir = Join-Path $env:LOCALAPPDATA 'PontoTerminal'
Start-Process $browser -ArgumentList @(
    "--app=$(Get-AppUrl '/kiosk')",
    '--start-fullscreen',
    "--user-data-dir=`"$profileDir`"",
    '--no-first-run',
    '--disable-session-crashed-bubble',
    '--autoplay-policy=no-user-gesture-required'
)
