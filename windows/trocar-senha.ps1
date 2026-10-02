# Troca a senha de um administrador (senha esquecida ou digitada errado na instalação).
# Também desfaz o bloqueio de 15 minutos após 5 tentativas erradas.
. (Join-Path $PSScriptRoot 'comum.ps1')

if (-not (Test-DockerRunning)) { Stop-WithError 'Abra o Docker Desktop, espere "Engine running" e rode de novo.' }
if (-not (Wait-System 120)) { Stop-WithError 'O sistema não respondeu. Espere alguns minutos e rode de novo.' }

Write-Host '=== Trocar a senha do administrador ===' -ForegroundColor Cyan
Write-Host 'Administradores cadastrados:'
docker @ComposeArgs exec -T backend python -m app.cli list-admins
Write-Host ''
$email = Read-Host 'E-mail do administrador (copie da lista acima)'

for ($attempt = 1; $attempt -le 3; $attempt++) {
    Write-Host ''
    Write-Host 'Digite a nova senha (mínimo 10 caracteres). Ela NÃO aparece enquanto você digita;'
    Write-Host 'digite com calma e aperte Enter. Depois digite a mesma senha de novo.'
    docker @ComposeArgs exec backend python -m app.cli reset-password --email $email
    if ($LASTEXITCODE -eq 0) {
        Write-Host ''
        Write-Host 'Senha alterada. Entre no painel com a nova senha.' -ForegroundColor Green
        Read-Host 'Pressione Enter para fechar'
        exit 0
    }
    Write-Host 'Não deu certo (veja a mensagem acima). Vamos tentar de novo.' -ForegroundColor Yellow
}
Stop-WithError 'A senha não foi alterada.'
