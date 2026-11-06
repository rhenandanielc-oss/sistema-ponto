# INSTALACAO-WINDOWS.md

# Instalação em um notebook com Windows (servidor e terminal no mesmo aparelho)

Para um estabelecimento pequeno, com uma unidade e poucos funcionários: o notebook com câmera guarda o
sistema **e** é o terminal de ponto. Sem custo de servidor, sem domínio e sem certificado.

* Endereço do sistema: `http://localhost` (só funciona no próprio notebook; ninguém da rede Wi-Fi acessa).
* O notebook **não precisa ficar ligado 24 horas**: pode ser desligado ao fechar (§6).
* Para usar vários aparelhos ou acessar de fora, veja `DEPLOY.md`.

> Testado em 2026-10-01 em ambiente Linux equivalente: subida do sistema, backup em pasta com espaços no nome,
> login, terminal com câmera, aviso de relógio e restauração. Os scripts foram verificados com PowerShell 7;
> a primeira instalação num Windows real deve ser acompanhada (§9).

---

## 1. Requisitos

* Windows 10 (versão 22H2) ou Windows 11, 64 bits.
* **8 GB de memória** recomendados (com 4 GB funciona, mas fica lento).
* 20 GB livres no disco.
* Internet **durante a instalação** (para baixar os componentes). Depois, o ponto funciona sem internet.
* Notebook ligado na tomada durante o expediente.

## 2. Instalar o Docker Desktop (uma vez)

O Docker Desktop é o programa que roda o sistema. É gratuito para pequenas empresas.

1. Baixe em <https://www.docker.com/products/docker-desktop/> → **Download for Windows**.
2. Instale com as opções padrão (mantenha marcado **"Use WSL 2"**). Reinicie o computador quando pedir.
   Se aparecer um aviso pedindo para atualizar o WSL, aceite.
3. Abra o **Docker Desktop**, aceite os termos e pule o login ("Skip"). Espere aparecer **"Engine running"**.
4. Em **Settings (engrenagem) → General**, marque **"Start Docker Desktop when you sign in to your computer"** e
   clique em **Apply**. Assim o sistema liga sozinho ao entrar no Windows.

Se o Docker reclamar de "virtualization", a virtualização está desligada no notebook: procure o modelo do notebook
+ "ativar virtualização" (é uma opção na BIOS) ou peça ajuda a um técnico.

## 3. Baixar o sistema

1. No GitHub, abra o repositório `sistema-ponto`, escolha o branch (hoje `claude/oi-xu1bph`; depois de juntado,
   `main`) e clique em **Code → Download ZIP**.
2. Extraia o ZIP e renomeie a pasta extraída para **`C:\Ponto`** (caminho curto, sem espaços).

## 4. Instalar

1. Abra a pasta `C:\Ponto\windows` e dê **duplo clique em `instalar.cmd`**.
   Se o Windows mostrar "O Windows protegeu o computador", clique em **Mais informações → Executar assim mesmo**.
2. O instalador:
   * gera sozinho as senhas internas e a **chave da biometria** e as grava no arquivo `C:\Ponto\.env`;
   * mostra a **chave da biometria**: **anote e guarde** em papel guardado ou num cofre de senhas (§7);
   * monta e liga o sistema — **a primeira vez demora de 10 a 20 minutos**;
   * pede **e-mail, nome e senha do administrador** (a senha tem no mínimo 10 caracteres e aparece como `*****`);
   * cria dois atalhos na Área de Trabalho: **"Ponto - Terminal"** e **"Ponto - Administrador"**;
   * pergunta se o terminal deve abrir sozinho ao ligar o computador (responda **S**).
3. Os backups automáticos vão para a pasta **`OneDrive\Ponto-Backups`** (ou `Documentos\Ponto-Backups` se não
   houver OneDrive). Com o OneDrive conectado, eles ficam guardados também na nuvem, sem custo extra.

Se a porta 80 estiver ocupada por outro programa, o sistema usa a 8080 (`http://localhost:8080`); os atalhos já
apontam para o endereço certo.

## 5. Primeira configuração

1. Abra **"Ponto - Administrador"** e entre com o e-mail e a senha do administrador.
2. **Administração → Terminais**: nome "Notebook" → **Cadastrar terminal**. Copie a **chave** que aparece (ela só aparece
   uma vez).
3. Abra **"Ponto - Terminal"**, cole a chave e toque em **Ativar terminal**. Na primeira vez, o navegador pergunta
   sobre a câmera: clique em **Permitir**.
4. Para sair do terminal (tela cheia): **Alt + F4**.
5. **Antes de cadastrar os funcionários:** em **Administração → Configurações**, preencha **"Início do uso do
   sistema"** com o dia em que o ponto começa a valer e clique em **Salvar configurações**. Sem isso, quem foi
   admitido antes aparece com falta em todos os dias desde a admissão.
   Depois, **Funcionários → Novo funcionário**: nome, dias de trabalho, horário fixo, tempo de almoço e dia do
   pagamento (para o ciclo do dia 1 ao fim do mês, use **31**).
6. Na ficha de cada funcionário: **Registrar consentimento** (com o termo assinado) e **Cadastrar rosto**.
   **Feche o terminal antes (Alt + F4)**: a câmera só pode ser usada por uma janela de cada vez.
7. Abra de novo o "Ponto - Terminal" e faça uma batida de teste com cada funcionário.
8. Se os funcionários consomem itens (ex.: refrigerante): cadastre-os com preço em **Administração → Consumo**.
   Para lançar, abra a ficha do funcionário → **Consumo** → escolha o item e a quantidade → **Lançar consumo**.
   O total do ciclo aparece em **Pagamento**, na coluna "Consumo (descontar)".

## 6. Uso no dia a dia

**Ao abrir:** ligue o notebook e entre no Windows. Em 1 a 3 minutos o terminal abre sozinho em tela cheia.

**Ao fechar:** depois da **última saída do dia**, desligue normalmente (**Iniciar → Desligar**).

* Batidas só podem ser feitas com o notebook ligado. Se alguém bater com ele desligado (ou esquecer), o
  administrador lança a batida em **Histórico → Incluir batida esquecida**, com o motivo.
* Prefira **Desligar** a "Suspender": depois de suspenso, o relógio do sistema pode ficar atrasado. Se isso
  acontecer, o terminal mostra um **aviso amarelo de relógio**; reinicie o notebook para corrigir.
* Durante o expediente, deixe o notebook na tomada e sem suspensão automática: **Configurações → Sistema → Energia
  (e bateria) → Tela e suspensão** → "Quando conectado, suspender após: **Nunca**".
* Evite reinícios do Windows Update no meio do expediente: **Configurações → Windows Update → Opções avançadas →
  Horário ativo**, cobrindo o horário de funcionamento.

**Dados guardados:** o sistema guarda todo o histórico. Para 3 a 4 funcionários isso ocupa poucos megabytes por ano,
então não é preciso apagar nada. Guarde pelo menos **5 anos** (prazo para questionamentos trabalhistas).

## 7. Backup e o que guardar fora do notebook

| O quê | Onde fica | O que fazer |
|---|---|---|
| Backups do banco | `OneDrive\Ponto-Backups`: um ao ligar e um a cada 4 h, guardados por 60 dias | Confira de vez em quando se há arquivos recentes |
| Arquivo `C:\Ponto\.env` (senhas e chave da biometria) | No notebook | Guarde uma cópia num **pendrive guardado** ou cofre de senhas, **separado** dos backups |
| Chave da biometria | Dentro do `.env` | Anotada à parte (o instalador mostrou) |

Sem o `.env`, um notebook novo não consegue abrir os backups do jeito certo, e os rostos precisam ser cadastrados
de novo.

## 8. Situações comuns

| Situação | O que fazer |
|---|---|
| Restaurar um backup (dados apagados por engano, notebook com problema) | Duplo clique em `C:\Ponto\windows\restaurar-backup.cmd`, escolha o backup e digite `RESTAURAR` |
| Notebook novo | Passos 2 e 3; copie o `.env` guardado para `C:\Ponto`; se o usuário do Windows mudou, corrija a linha `BACKUP_DIR` no `.env` (Bloco de Notas); copie os backups para essa pasta; rode `instalar.cmd`; depois `restaurar-backup.cmd` |
| Atualizar o sistema | Baixe o ZIP novo e extraia **por cima** da pasta do sistema (o `.env` é mantido) e rode `instalar.cmd`. Se extrair numa **pasta nova**, o instalador reaproveita sozinho o `.env` da instalação anterior (ou uma cópia salva na Área de Trabalho) e acerta a senha do banco; sem nenhum `.env` antigo, os dados continuam, mas os rostos precisam ser cadastrados de novo |
| Atalho "Ponto - Administrador" não aparece na Área de Trabalho | Duplo clique em `C:\Ponto\windows\abrir-administracao.cmd`, ou digite `localhost/login` no navegador (se não abrir, `localhost:8080/login`). Rodar o `instalar.cmd` de novo recria os atalhos sem apagar nada |
| Terminal mostra "O sistema de ponto não ligou" | Abra o Docker Desktop, espere "Engine running" e abra o atalho "Ponto - Terminal" |
| "Câmera indisponível" | Feche outros programas que usam a câmera (Teams, Câmera, janela de cadastro de rosto) |
| Aviso amarelo de relógio | Reinicie o notebook (ou no ícone da baleia do Docker: **Restart**) |
| Funcionário "não reconhecido" com frequência | Cadastre mais fotos do rosto dele (até 5), com boa luz |
| Esqueceu a senha do administrador, digitou errado na instalação ou a conta ficou bloqueada | Duplo clique em `C:\Ponto\windows\trocar-senha.cmd`: mostra os e-mails cadastrados, pede o e-mail e a nova senha duas vezes (aparece como `*****`) e desbloqueia a conta |

## 9. Primeira instalação acompanhada

Os scripts do Windows não puderam ser executados num Windows real durante o desenvolvimento. Na primeira
instalação, se alguma etapa mostrar erro, copie a mensagem (ou tire uma foto da tela) e envie para ajuste.

## 10. Celular ou tablet na parede como terminal (opcional)

O notebook continua sendo o servidor; o celular só mostra o terminal. **O notebook precisa estar ligado** enquanto
o celular for usado. A câmera do navegador só funciona em endereço `https`, por isso usamos o **Tailscale**
(gratuito até 3 usuários e 100 aparelhos), que cria um endereço `https://….ts.net` válido e só acessível pelos
aparelhos da sua conta.

**No notebook (uma vez):**

1. Baixe e instale o Tailscale em <https://tailscale.com/download/windows>. Entre com uma conta Google (ou outra).
2. No navegador, abra <https://login.tailscale.com/admin/dns>: em **MagicDNS**, clique em **Enable**; em
   **HTTPS Certificates**, clique em **Enable HTTPS**.
3. Abra o **PowerShell** e rode (troque `8090` pela porta que aparece no atalho "Ponto - Terminal"):
   `& "C:\Program Files\Tailscale\tailscale.exe" serve --bg 8090`
   Se aparecer um link pedindo para habilitar o "Serve", abra-o, confirme e rode o comando de novo.
   O comando mostra o endereço, por exemplo `https://notebook.tail1234.ts.net`. Ele continua valendo depois de
   desligar e ligar o notebook.

**No celular:**

1. Instale o app **Tailscale** (Play Store) e entre com a **mesma conta**. Ative a conexão.
   Em **Configurações do Android → Rede e Internet → VPN → Tailscale (engrenagem)**, ligue **"VPN sempre ativa"**.
2. No Chrome, abra `https://notebook.tail1234.ts.net/login` (o seu endereço), entre como administrador e, em
   **Administração → Terminais**, cadastre o terminal "Celular" e copie a chave.
3. Abra `https://notebook.tail1234.ts.net/kiosk`, cole a chave, **Ativar terminal** e **Permitir** a câmera.
4. No menu do Chrome (⋮) → **Adicionar à tela inicial**, para abrir o terminal com um toque.

**Deixar o celular só com o ponto:**

* **Fixar app:** Configurações → Segurança → Mais configurações de segurança → **Fixar app** (ligar). Com o terminal
  aberto, abra os apps recentes, toque no ícone do Chrome → **Fixar**. Para soltar: segure Voltar + Visão geral.
* **Tela sempre ligada no carregador:** Configurações → Sobre o telefone → toque 7 vezes em **Número da versão**;
  depois Sistema → Opções do desenvolvedor → **Permanecer ativo**.
* **Proteger a bateria** (ficará sempre na tomada): Configurações → Bateria → **Proteção da bateria / carregamento
  otimizado** (limita a carga em 80%).
* Desligue a rotação automática (fica em pé) e as notificações de outros apps.
* Fixe na parede na altura do rosto, com luz de frente (não contra a janela) e o carregador ligado.

Batidas feitas pelo celular e pelo notebook vão para o mesmo lugar; dá para usar os dois.
