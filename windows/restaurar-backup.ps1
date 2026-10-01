# Restaura um backup do banco. SUBSTITUI todos os dados atuais pelos do backup escolhido.
. (Join-Path $PSScriptRoot 'comum.ps1')

if (-not (Test-DockerRunning)) { Stop-WithError 'Abra o Docker Desktop e rode de novo.' }
$backupDir = (Read-EnvFile)['BACKUP_DIR']
if (-not $backupDir -or -not (Test-Path $backupDir)) { Stop-WithError "Pasta de backups não encontrada: $backupDir" }

$files = @(Get-ChildItem $backupDir -Filter 'ponto-*.dump' | Sort-Object LastWriteTime -Descending | Select-Object -First 15)
if ($files.Count -eq 0) { Stop-WithError "Nenhum backup em $backupDir" }
Write-Host 'Backups mais recentes:' -ForegroundColor Cyan
for ($i = 0; $i -lt $files.Count; $i++) {
    Write-Host ("  {0,2}) {1}   ({2:dd/MM/yyyy HH:mm})" -f ($i + 1), $files[$i].Name, $files[$i].LastWriteTime)
}
$choice = Read-Host 'Número do backup a restaurar'
if (-not ($choice -as [int]) -or [int]$choice -lt 1 -or [int]$choice -gt $files.Count) { Stop-WithError 'Opção inválida.' }
$file = $files[[int]$choice - 1].Name

Write-Host "ATENÇÃO: todos os dados atuais serão substituídos pelo backup $file." -ForegroundColor Yellow
if ((Read-Host 'Digite RESTAURAR para continuar') -cne 'RESTAURAR') { Stop-WithError 'Cancelado.' }

docker @ComposeArgs stop backend scheduler
# Sem aspas duplas no comando: o PowerShell 5.1 as remove ao chamar programas externos.
docker @ComposeArgs exec -T backup sh -c 'pg_restore --clean --if-exists --no-owner --exit-on-error -h db -U $POSTGRES_USER -d $POSTGRES_DB /backups/$1' sh $file
$ok = $LASTEXITCODE -eq 0
docker @ComposeArgs start backend scheduler
if (-not $ok) { Stop-WithError 'A restauração falhou. Os dados podem estar incompletos: tente outro backup.' }
Write-Host 'Backup restaurado. Confira o sistema e a Auditoria.' -ForegroundColor Green
Read-Host 'Pressione Enter para fechar'
