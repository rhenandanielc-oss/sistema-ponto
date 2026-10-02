# Troca a senha de um administrador (senha esquecida ou digitada errado na instalação).
# Também desfaz o bloqueio de 15 minutos após 5 tentativas erradas.
. (Join-Path $PSScriptRoot 'comum.ps1')

if (-not (Test-DockerRunning)) { Stop-WithError 'Abra o Docker Desktop, espere "Engine running" e rode de novo.' }

# Garante que o sistema em execução é a versão desta pasta (ex.: depois de extrair um ZIP novo,
# o comando de troca de senha só existe após remontar). Sem mudanças, termina em segundos.
Write-Host 'Conferindo se o sistema está atualizado (pode levar alguns minutos)...' -ForegroundColor Cyan
docker @ComposeArgs up -d --build
if ($LASTEXITCODE -ne 0) { Stop-WithError 'Falha ao atualizar o sistema. Rode o instalar.cmd e depois este de novo.' }
if (-not (Wait-System 300)) { Stop-WithError 'O sistema não respondeu. Espere alguns minutos e rode de novo.' }

Write-Host '=== Trocar a senha do administrador ===' -ForegroundColor Cyan
Write-Host 'Administradores cadastrados:'
docker @ComposeArgs exec -T backend python -m app.cli list-admins
Write-Host ''
$email = Read-Host 'E-mail do administrador (copie da lista acima)'

for ($attempt = 1; $attempt -le 3; $attempt++) {
    Write-Host ''
    $password = Read-NewPassword
    Invoke-CliWithPassword $password @('reset-password', '--email', $email)
    if ($LASTEXITCODE -eq 0) {
        Write-Host ''
        Write-Host 'Senha alterada. Entre no painel com a nova senha.' -ForegroundColor Green
        Read-Host 'Pressione Enter para fechar'
        exit 0
    }
    Write-Host 'Não deu certo (veja a mensagem acima). Confira o e-mail e tente de novo.' -ForegroundColor Yellow
    $email = Read-Host 'E-mail do administrador'
}
Stop-WithError 'A senha não foi alterada.'
