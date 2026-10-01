# MASTER-PROMPT.md

# Sistema de Ponto Eletrônico com Reconhecimento Facial

## 1. Objetivo

Construir um sistema web profissional de controle eletrônico de ponto com reconhecimento facial, cálculo de jornada e banco de horas.

O sistema deverá ser desenvolvido de forma incremental, segura, testável e preparada para produção.

O repositório é a fonte de verdade do projeto.

O Claude Code deve sempre trabalhar sobre o estado atual do código e da documentação existentes no repositório.

---

# 2. Regra principal de execução

Antes de executar qualquer alteração:

1. Ler este arquivo (`MASTER-PROMPT.md`).
2. Ler `PROJECT-STATE.md`.
3. Ler apenas os documentos e arquivos relevantes para a etapa atual.
4. Identificar a próxima fase pendente.
5. Implementar somente o necessário para essa fase.
6. Executar testes e validações.
7. Corrigir problemas encontrados.
8. Atualizar `PROJECT-STATE.md`.
9. Não avançar automaticamente para fases futuras sem necessidade.
10. Não apagar funcionalidades existentes sem justificativa técnica.
11. Não alterar regras de negócio sem documentar a decisão.

O projeto deve evoluir de forma incremental.

---

# 3. Princípios obrigatórios

## 3.1 Código

* Código organizado e legível.
* Separação clara entre frontend, backend e infraestrutura.
* Responsabilidades bem definidas.
* Evitar duplicação.
* Evitar lógica de negócio espalhada pelo frontend.
* Regras críticas devem ficar no backend.
* Utilizar validações no backend.
* Utilizar transações quando necessário.
* Tratar erros de forma consistente.
* Criar testes para funcionalidades importantes.

## 3.2 Segurança

Nunca:

* colocar senhas reais no Git;
* colocar tokens reais no Git;
* colocar chaves privadas no Git;
* colocar credenciais reais de banco no Git;
* armazenar dados biométricos reais no repositório;
* expor segredos no frontend.

Utilizar `.env` local e `.env.example` sem valores secretos.

Implementar autenticação e autorização adequadas.

Todas as rotas administrativas devem ser protegidas.

---

# 4. Stack desejada

## Frontend

* React
* TypeScript
* Vite
* Tailwind CSS
* React Router
* React Query

## Backend

Utilizar uma arquitetura REST.

A tecnologia escolhida para o backend deve ser documentada em `ARCHITECTURE.md`.

## Banco

* PostgreSQL

## Infraestrutura

* Docker
* Docker Compose

## Controle de versão

* Git
* GitHub

---

# 5. Documentação obrigatória

O projeto deverá possuir, quando aplicável:

* `ARCHITECTURE.md`
* `DATABASE.md`
* `API.md`
* `SECURITY.md`
* `BUSINESS-RULES.md`
* `BIOMETRICS.md`
* `TEST-PLAN.md`
* `PROJECT-STATE.md`

Não criar documentação fictícia apenas para preencher arquivos.

A documentação deve refletir o sistema realmente implementado.

---

# 6. Arquitetura

O sistema deverá possuir pelo menos:

### Funcionários

* cadastro;
* edição;
* ativação;
* desativação;
* pesquisa;
* histórico.

### Jornadas

* jornada;
* carga horária;
* dias da semana;
* horários;
* intervalo;
* associação ao funcionário;
* diferentes tipos de jornada.

### Registros de ponto

Tipos:

* `ENTRY`
* `LUNCH_EXIT`
* `LUNCH_RETURN`
* `EXIT`

Cada registro deverá possuir informações suficientes para auditoria.

### Usuários

* login;
* logout;
* autenticação;
* autorização;
* perfis;
* permissões.

### Auditoria

Registrar ações relevantes.

### Feriados

Permitir tratamento de feriados nas regras de jornada.

---

# 7. Regras dos registros de ponto

O horário oficial deverá ser determinado pelo servidor.

O frontend nunca deve ser considerado fonte confiável para o horário oficial.

O backend deverá validar:

* sequência dos registros;
* registros duplicados;
* funcionário ativo;
* existência do funcionário;
* jornada aplicável;
* data e horário;
* origem/dispositivo quando aplicável.

Deve existir auditoria das operações relevantes.

---

# 8. Motor de cálculo de jornada

O cálculo deverá ser realizado exclusivamente no backend.

O motor deverá considerar:

* horas planejadas;
* horas trabalhadas;
* atrasos;
* faltas;
* intervalos;
* saída antecipada;
* horas extras;
* saldo diário;
* saldo acumulado;
* banco de horas;
* feriados;
* finais de semana;
* diferentes jornadas;
* registros incompletos;
* jornadas noturnas quando aplicável.

O intervalo das consultas deverá ser inclusivo.

Exemplo:

`01/09/2026 até 30/09/2026`

deve considerar tanto o dia 01 quanto o dia 30.

---

# 9. Casos de teste obrigatórios

Criar testes para pelo menos:

* jornada normal;
* intervalo normal;
* atraso;
* saída antecipada;
* hora extra;
* falta;
* registro duplicado;
* registros incompletos;
* jornada diferente;
* final de semana;
* feriado;
* jornada que atravessa a meia-noite;
* período de consulta;
* banco de horas;
* funcionário inativo;
* tentativa de registro inválido.

Os exemplos utilizados nos testes devem ser documentados quando necessário.

---

# 10. API

A API deverá possuir endpoints para:

* autenticação;
* funcionários;
* jornadas;
* registros;
* histórico;
* cálculos;
* banco de horas;
* usuários;
* permissões;
* auditoria;
* feriados.

A API deve possuir:

* validação;
* paginação;
* filtros;
* ordenação;
* tratamento de erros;
* autenticação;
* autorização;
* documentação OpenAPI quando aplicável.

---

# 11. Frontend

Criar interface em português.

Rotas esperadas:

* `/login`
* `/kiosk`
* `/historico`
* `/banco-de-horas`
* `/funcionarios`
* `/jornadas`
* `/admin`

A interface deve funcionar em:

* desktop;
* tablet;
* terminal de ponto/kiosk.

A interface de registro deve ser simples e rápida.

---

# 12. Kiosk

O fluxo principal deverá ser:

1. Ativar câmera.
2. Detectar rosto.
3. Identificar funcionário.
4. Exibir nome.
5. Exibir opções:

   * Entrada
   * Saída para almoço
   * Retorno do almoço
   * Saída
6. Confirmar operação.
7. Enviar registro ao backend.
8. Backend registrar horário oficial.
9. Mostrar confirmação.
10. Reiniciar o fluxo.

Tratar:

* câmera indisponível;
* nenhuma face;
* múltiplas faces;
* face não reconhecida;
* baixa qualidade;
* funcionário inativo;
* erro de rede;
* registro duplicado.

Imagens temporárias devem ser minimizadas.

---

# 13. Reconhecimento facial

Antes de escolher a tecnologia definitiva, avaliar:

* precisão;
* privacidade;
* LGPD;
* custo;
* desempenho;
* processamento local;
* dependência de internet;
* segurança;
* manutenção;
* escalabilidade;
* compatibilidade com navegador.

Comparar alternativas possíveis, como:

* Face API;
* TensorFlow.js;
* MediaPipe;
* processamento local;
* serviço backend;
* APIs externas.

A solução escolhida deve ser documentada em `BIOMETRICS.md`.

Biometria é dado sensível.

Evitar armazenar imagens faciais desnecessariamente.

Definir:

* armazenamento;
* proteção;
* criptografia;
* retenção;
* exclusão;
* acesso;
* auditoria.

Não implementar uma solução biométrica apenas porque é tecnicamente fácil. A escolha deve considerar segurança e privacidade.

---

# 14. Histórico

Criar página de histórico contendo:

* data;
* funcionário;
* tipo de registro;
* horário;
* origem;
* dispositivo quando aplicável.

Filtros:

* funcionário;
* hoje;
* semana;
* mês;
* período personalizado.

Possibilitar paginação e visualização detalhada.

Registros não devem ser alterados diretamente sem autorização e auditoria.

---

# 15. Banco de horas

Criar página de banco de horas.

Permitir:

* funcionário;
* período;
* horas trabalhadas;
* horas planejadas;
* horas extras;
* saldo;
* detalhamento diário.

Os cálculos devem vir do backend.

---

# 16. Auditoria final

Antes da produção revisar:

* banco;
* API;
* frontend;
* autenticação;
* autorização;
* cálculos;
* biometria;
* câmera;
* timezone;
* auditoria;
* segurança;
* performance;
* concorrência;
* integridade;
* recuperação de falhas.

Executar todos os testes.

Corrigir bugs encontrados.

Adicionar testes quando houver lacunas.

Não considerar o projeto concluído apenas porque compila.

---

# 17. Produção

Preparar:

* Dockerfiles;
* configuração de produção;
* Docker Compose quando apropriado;
* variáveis de ambiente;
* `.env.example`;
* health checks;
* logs;
* migrações;
* backup;
* documentação de deploy.

Nunca armazenar secrets no Git.

---

# 18. Terminal dedicado

O kiosk deverá considerar:

* tela cheia;
* inicialização automática;
* acesso à câmera;
* HTTPS;
* permissões;
* reconexão;
* recuperação após queda de conexão;
* comportamento após reinicialização;
* prevenção de acesso indevido às configurações.

Documentar o procedimento.

---

# 19. Regra de consistência

Sempre que uma alteração afetar:

* banco;
* API;
* regra de negócio;
* segurança;
* biometria;
* arquitetura;

atualizar a documentação correspondente.

Nunca deixar documentação contradizer o código.

---

# 20. Git

Criar commits por etapa significativa.

Exemplo:

`feat: implement employee management`

`feat: implement time records`

`feat: implement workday calculation`

`feat: implement kiosk`

`test: add workday calculation tests`

`fix: prevent duplicate time records`

Não realizar commits contendo secrets.

---

# 21. PROJECT-STATE.md

Ao final de cada fase:

1. Atualizar o status.
2. Marcar o que foi concluído.
3. Registrar arquivos importantes.
4. Registrar testes executados.
5. Registrar problemas encontrados.
6. Registrar decisões técnicas.
7. Indicar a próxima fase.

O arquivo deve permitir que outra sessão do Claude Code continue o projeto sem precisar receber novamente todos os prompts.

---

# 22. Comportamento esperado do Claude Code

Quando iniciado no repositório:

* leia `MASTER-PROMPT.md`;
* leia `PROJECT-STATE.md`;
* analise o estado atual;
* identifique a próxima tarefa;
* implemente;
* teste;
* corrija;
* documente;
* atualize `PROJECT-STATE.md`.

Não reimplemente funcionalidades já concluídas.

Não invente funcionalidades sem necessidade.

Não pule etapas críticas.

Se encontrar uma decisão arquitetural importante, registre-a antes de prosseguir.

Se houver conflito entre código, documentação e estado:

1. analisar o código;
2. identificar a causa;
3. corrigir a inconsistência;
4. atualizar documentação/estado;
5. registrar a decisão.

---

# 23. Fases

## Fase 0 — Arquitetura

Criar:

* `ARCHITECTURE.md`
* `DATABASE.md`
* `API.md`
* `SECURITY.md`
* `BUSINESS-RULES.md`
* `BIOMETRICS.md`
* `TEST-PLAN.md`

Ainda não implementar a aplicação completa.

---

## Fase 1 — Backend base

Implementar:

* banco;
* migrations;
* modelos;
* autenticação;
* autorização;
* usuários;
* funcionários;
* jornadas.

Criar testes.

---

## Fase 2 — Registros e cálculo

Implementar:

* registros de ponto;
* validação de sequência;
* prevenção de duplicidade;
* cálculo de jornada;
* banco de horas;
* feriados.

Criar testes extensivos.

---

## Fase 3 — API completa

Implementar e documentar:

* endpoints;
* filtros;
* paginação;
* ordenação;
* erros;
* OpenAPI;
* integração.

---

## Fase 4 — Frontend

Implementar:

* login;
* funcionários;
* jornadas;
* histórico;
* banco de horas;
* administração.

---

## Fase 5 — Biometria e Kiosk

Implementar:

* câmera;
* reconhecimento facial;
* identificação;
* registro;
* tratamento de erros;
* modo kiosk.

---

## Fase 6 — Auditoria e produção

Executar:

* auditoria;
* testes;
* segurança;
* performance;
* Docker;
* deploy;
* backup;
* documentação.

---

# 24. Critério de conclusão

O projeto somente será considerado concluído quando:

* backend estiver funcionando;
* frontend estiver funcionando;
* banco estiver versionado por migrations;
* autenticação funcionar;
* autorização funcionar;
* registros funcionarem;
* cálculos estiverem testados;
* banco de horas funcionar;
* histórico funcionar;
* kiosk funcionar;
* biometria estiver documentada e implementada conforme decisão;
* auditoria existir;
* testes estiverem passando;
* documentação estiver atualizada;
* produção estiver documentada;
* `PROJECT-STATE.md` estiver atualizado.

# FIM
