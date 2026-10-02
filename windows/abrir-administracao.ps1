# Abre o painel do administrador no navegador padrão.
. (Join-Path $PSScriptRoot 'comum.ps1')
Add-Type -AssemblyName System.Windows.Forms

if (-not (Wait-System 120)) {
    [System.Windows.Forms.MessageBox]::Show(
        'O sistema de ponto não respondeu. Abra o Docker Desktop, espere alguns minutos e tente de novo.',
        'Sistema de Ponto') | Out-Null
    exit 1
}
Start-Process (Get-AppUrl '/login')
