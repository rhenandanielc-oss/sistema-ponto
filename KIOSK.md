# KIOSK.md

# Terminal de ponto (kiosk)

> **Status:** tela do terminal implementada na Fase 5 (`/kiosk`). Este documento descreve como preparar o
> equipamento. Instalação do servidor (HTTPS, backup): `DEPLOY.md`. Notebook único com Windows (servidor e
> terminal no mesmo aparelho): `INSTALACAO-WINDOWS.md`, que já cria os atalhos e a abertura automática.

---

## 1. Como o terminal funciona

1. O funcionário se posiciona em frente à câmera.
2. O navegador detecta o rosto só para enquadramento (MediaPipe, local) e, quando o rosto está bom,
   envia **um** quadro ao servidor. Também há o botão **Identificar** (útil se a detecção automática falhar).
3. O servidor reconhece o funcionário (YuNet + SFace, local) e devolve o nome e as batidas permitidas.
4. O funcionário toca em **Entrada**, **Saída para almoço**, **Retorno do almoço** ou **Saída**
   (só a próxima batida válida fica habilitada) ou em **Ver meu banco de horas**.
5. O servidor registra a batida com o **horário oficial do servidor** e o terminal mostra a confirmação por 2,5 s; um toque
   nela libera o terminal na hora para o próximo colega.
6. Depois de alguns segundos o terminal volta ao início sozinho.

Nenhuma foto é guardada: o quadro existe só durante a requisição.

---

## 2. Requisitos do equipamento

* Computador ou tablet com câmera frontal (720p ou melhor) e tela sensível ao toque (recomendado).
* Navegador Chromium/Google Chrome atualizado.
* Rede com acesso ao servidor do sistema.
* **HTTPS obrigatório:** navegadores só liberam a câmera em páginas HTTPS (ou `localhost`). Se o servidor usa
  certificado interno (`TLS_MODE=internal`), instale antes o certificado raiz no terminal (`DEPLOY.md` §3.1).
* Local bem iluminado, sem luz forte atrás do funcionário, e visível (reduz tentativas de fraude com fotos).

---

## 3. Cadastro do terminal no sistema

1. No painel: **Administração → Terminais → Cadastrar terminal** (ex.: "Recepção").
2. Copie a **chave** exibida — ela aparece uma única vez.
3. No equipamento, abra `https://<servidor>/kiosk`, cole a chave e toque em **Ativar terminal**.
   A chave fica guardada só no navegador daquele equipamento.
4. Se a chave vazar ou o equipamento for perdido: **Administração → Terminais → Desativar** (ou **Nova chave**).
   O terminal volta para a tela de configuração.

---

## 4. Modo quiosque (tela cheia, inicialização automática)

### Linux / Raspberry Pi (Chromium)

Crie o arquivo `~/.config/autostart/ponto-kiosk.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Ponto
Exec=chromium --kiosk --noerrdialogs --disable-session-crashed-bubble --disable-infobars --autoplay-policy=no-user-gesture-required https://SEU-SERVIDOR/kiosk
```

### Windows (Google Chrome)

Atalho na pasta de inicialização (`shell:startup`) com o destino:

```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk --noerrdialogs --disable-session-crashed-bubble https://SEU-SERVIDOR/kiosk
```

### Permissão da câmera sem pergunta

Para o navegador não pedir permissão a cada reinício, libere a câmera só para o endereço do sistema:

* Chrome (política `VideoCaptureAllowedUrls`): `["https://SEU-SERVIDOR"]`.
* Ou, na primeira execução, permita a câmera e marque "lembrar".

### Prevenção de acesso indevido

* Use uma conta de sistema operacional dedicada, sem privilégios de administrador, com login automático.
* No modo `--kiosk` não há barra de endereço nem abas; desative atalhos de teclado se o equipamento tiver teclado
  físico, ou use um tablet.
* Bloqueie a BIOS/configurações com senha e desative a inicialização por USB.
* O terminal não tem acesso às telas administrativas: o token dele só funciona em `/api/v1/kiosk/*`.

---

## 5. Queda de conexão e reinício

* Erro de rede: o terminal mostra "Sem conexão. Tentando novamente…" e volta ao início após alguns segundos;
  a batida **não** é registrada offline (o horário oficial é sempre o do servidor).
* Reinício do equipamento: o navegador abre de novo em `/kiosk` (inicialização automática) e reaproveita a chave
  guardada.
* Câmera desconectada/negada: mensagem na tela; reconecte a câmera e recarregue a página.
* Se o terminal for desativado no painel, ele volta para a tela de configuração.

---

## 6. Problemas comuns

| Mensagem no terminal | O que fazer |
|---|---|
| "Câmera indisponível…" | Verifique o cabo/permissão; confirme que o endereço é HTTPS. |
| "Aproxime-se da câmera" | Funcionário longe demais; ajuste a altura da câmera. |
| "Iluminação inadequada" | Melhore a luz do ambiente; evite contraluz. |
| "Não reconhecido" | Recadastre o rosto do funcionário (3 fotos com pequenas variações). |
| "Cadastro inativo" | Funcionário desativado no painel. |
| "Registro já efetuado" | A batida já existe; confira no Histórico. |
