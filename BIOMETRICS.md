# BIOMETRICS.md

# Reconhecimento Facial — Avaliação e Decisão

> **Status:** decisão de arquitetura tomada na Fase 0 (revisada em 2026-10-01). Implementação na Fase 5.
> Biometria é **dado pessoal sensível** (LGPD art. 5º, II). Toda escolha abaixo prioriza privacidade e segurança
> sobre facilidade de implementação.

---

## 1. Requisitos

* Identificação **1:N** no kiosk: o funcionário não digita nada e **não tem senha** — o rosto é a única forma de
  identificação. Depois de reconhecido, ele só escolhe o tipo de batida ou consulta o próprio banco de horas.
* Funcionar no navegador do terminal (câmera via `getUserMedia`, HTTPS).
* Processamento **local na infraestrutura da empresa**, sem enviar rostos a terceiros.
* Não armazenar imagens faciais.
* Escala esperada: até algumas centenas de funcionários por instalação.
* Tratar: câmera indisponível, nenhuma face, múltiplas faces, face não reconhecida, baixa qualidade.

---

## 2. Alternativas avaliadas

| Opção | Precisão | Privacidade / LGPD | Custo | Internet | Segurança (confiança no resultado) | Manutenção | Licença |
|---|---|---|---|---|---|---|---|
| **face-api.js** (no navegador) | Média (modelos de 2018–2019) | Boa (local) | Zero | Não | **Fraca:** o navegador decide quem é a pessoa; um kiosk adulterado pode enviar qualquer identificação | **Projeto sem manutenção desde 2020** | MIT |
| **TensorFlow.js** (modelo próprio no navegador) | Depende do modelo; não há modelo oficial de reconhecimento | Boa | Zero | Não | Fraca (mesmo problema) | Alta: exigiria portar/treinar modelo | Apache 2.0 |
| **MediaPipe** (Face Detector / Face Landmarker) | Excelente para **detecção**; **não faz reconhecimento** (não gera embedding de identidade) | Boa | Zero | Não | — | Mantido pelo Google | Apache 2.0 |
| **Serviço backend com modelo ONNX local** (detecção YuNet + reconhecimento SFace via OpenCV/onnxruntime) | Boa (SFace: ~99,4% em LFW, segundo os autores) | **Boa:** imagem trafega só na rede da empresa via HTTPS e é descartada da memória após o uso | Zero | Não (rede local) | **Forte:** decisão de identidade no servidor, com modelo e limiar controlados | Média (modelos estáveis, OpenCV mantido) | YuNet: MIT; SFace: Apache 2.0 — **confirmar na Fase 5** |
| Backend com **InsightFace / ArcFace** | Excelente | Boa | Zero | Não | Forte | Média | **Modelos pré-treinados com licença não comercial** — inviável para uso comercial sem licença |
| **APIs externas** (AWS Rekognition, Azure Face) | Excelente, com antifraude | **Fraca:** rostos enviados a terceiros; transferência internacional; Azure restringe acesso a identificação | Por chamada | **Sim** (ponto para se a internet cair) | Forte | Baixa | Comercial |

---

## 3. Decisão

**Arquitetura híbrida, com a decisão de identidade sempre no servidor:**

1. **Navegador (kiosk) — MediaPipe Face Detector**, apenas para **experiência do usuário**:
   detectar se há 0, 1 ou várias faces, verificar enquadramento/tamanho/iluminação e só então capturar um frame.
   O resultado do navegador **não é confiável** para identificação — serve para evitar envios inúteis.
2. **Kiosk envia ao backend** um único frame JPEG (recortado ao redor do rosto, ~640 px, qualidade 85),
   via HTTPS, autenticado com o token do dispositivo.
3. **Backend**:
   * revalida a detecção (YuNet) — rejeita 0 ou >1 face e baixa qualidade (tamanho mínimo da face, nitidez, brilho);
   * extrai o embedding (SFace, 128 dimensões);
   * compara com os templates **ativos** de funcionários **ativos** (similaridade de cosseno);
   * aceita se `melhor ≥ limiar` **e** `melhor − segundo melhor ≥ margem` (evita confusão entre pessoas parecidas);
   * descarta a imagem da memória; nada é gravado em disco.
4. Resposta ao kiosk: nome do funcionário, tipos de batida permitidos e um **token de identificação**
   (validade 60 s), ou erro tipado.
5. O funcionário toca no tipo de batida **ou** em "Ver meu banco de horas". O kiosk envia a ação junto com o
   token de identificação. O kiosk nunca informa qual funcionário é — o servidor usa o vinculado ao token, de modo que
   não é possível registrar ponto ou ver dados de alguém que não foi reconhecido pelo servidor.

### 3.1 Fluxo na tela do kiosk

```
[Câmera ativa — "Olhe para a câmera"]
        │ rosto detectado (navegador) → frame enviado → servidor reconhece
        ▼
[Olá, Maria Souza]
  ( Entrada )  ( Saída para almoço )  ( Retorno do almoço )  ( Saída )   ← só os permitidos ficam habilitados
  ( Ver meu banco de horas )                                  ( Cancelar )
        │
        ├─ batida → [Entrada registrada às 08:02 ✔] → volta ao início após 5 s
        └─ banco  → [Saldo, horas extras e faltantes do mês, detalhe diário] → fecha em 30 s ou em "Sair"
```

Sem toque em 15 s na tela "Olá", o fluxo volta ao início e o token é descartado.

**Motivos:** processamento local (sem terceiros e sem depender da internet), decisão de identidade em ambiente
controlado, licenças permissivas, custo zero e desempenho suficiente em CPU para a escala esperada
(1:N com centenas de vetores de 128 dimensões é trivial).

**Limiar e margem** começam com os valores de referência do modelo (cosseno ≈ 0,363 para SFace) e serão
**calibrados na Fase 5** com testes controlados; ficam em `settings`.

---

## 4. Cadastro (enrollment)

* Feito pelo **administrador**, presencialmente com o funcionário, na tela de cadastro do funcionário
  (câmera do computador do administrador ou do próprio kiosk).
* **Pré-requisito: consentimento registrado** (termo versionado, data, quem registrou) — `biometric_consents`.
* Captura de 3 a 5 frames de boa qualidade; cada um gera um embedding; armazena-se cada embedding como template
  (ou a média normalizada — decidido na calibração).
* Nenhuma imagem é armazenada; as imagens de cadastro existem só em memória durante a requisição.

* Por decisão do responsável (2026-10-01), **não há forma alternativa de identificação** (sem PIN/senha para
  funcionários). Funcionário sem rosto cadastrado não consegue bater ponto no kiosk; nesses casos o administrador
  registra por ajuste.

---

## 5. Armazenamento e proteção

| Aspecto | Definição |
|---|---|
| O que é armazenado | Apenas embeddings (vetores numéricos) — **nunca imagens** |
| Onde | Tabela `biometric_templates` no PostgreSQL (ver `DATABASE.md`) |
| Criptografia | AES-256-GCM por template, nonce aleatório; chave `BIOMETRIC_KEY` fora do banco (variável de ambiente / secret do Docker); `key_id` permite rotação |
| Em memória | Templates decifrados ficam em cache em memória do processo, invalidado em cadastro/exclusão/desativação |
| Em trânsito | HTTPS entre kiosk e backend |
| Logs | Nunca contêm imagem, embedding ou score associado a nome fora da auditoria |
| Backups | Contêm templates cifrados; a chave **não** vai no mesmo backup |
| Versão do modelo | Cada template guarda `model_version`; trocar o modelo exige recadastro |

---

## 6. Retenção e exclusão

* Templates são mantidos **enquanto o funcionário estiver ativo e o consentimento vigente**.
* **Exclusão imediata** (lógica, deixa de ser usado no matching) quando: consentimento revogado,
  funcionário desativado/desligado, ou pedido do titular.
* **Expurgo físico** dos templates excluídos em até 30 dias (tarefa agendada, Fase 6), e não podem ser restaurados.
* A auditoria registra os eventos (cadastro, exclusão), **sem** o template.

---

## 7. Acesso

* Nenhum endpoint devolve templates ou embeddings.
* Apenas o serviço de biometria lê `biometric_templates`.
* Cadastro e exclusão somente pelo administrador, auditados.

---

## 8. Limitações conhecidas e riscos

| Risco | Situação | Mitigação |
|---|---|---|
| **Ataque de apresentação** (foto ou vídeo na frente da câmera) | O SFace não tem detecção de vivacidade | Kiosk em local visível/supervisionado; auditoria com dispositivo e horário; avaliar modelo anti-spoofing com licença compatível na Fase 5 (ex.: modelos de "face anti-spoofing" do OpenCV Zoo/Silent-Face — **licenças a verificar**). Não declarar o sistema "à prova de fraude". |
| Falso positivo (identificar a pessoa errada) | Possível com limiar baixo | Limiar + margem; tela de confirmação com nome antes de registrar |
| Viés demográfico do modelo | Possível | Calibrar com o grupo real de funcionários; acompanhar taxa de não-reconhecimento |
| Iluminação/câmera ruim | Provável em terminal | Verificação de qualidade no navegador e no servidor; orientação na instalação do kiosk |

---

## 9. Tratamento de erros no kiosk

| Situação | Detectado em | Mensagem ao usuário (pt-BR) |
|---|---|---|
| Câmera indisponível / permissão negada | Navegador | "Câmera indisponível. Chame o responsável." |
| Nenhuma face | Navegador (UX) e servidor | "Posicione o rosto na moldura." |
| Múltiplas faces | Navegador e servidor | "Apenas uma pessoa por vez." |
| Baixa qualidade | Navegador e servidor | "Aproxime-se e melhore a iluminação." |
| Face não reconhecida | Servidor | "Não reconhecido. Tente novamente ou procure o RH." |
| Funcionário inativo | Servidor (inativos nem entram no matching; se o token expirar entre etapas, o registro é rejeitado) | "Cadastro inativo. Procure o RH." |
| Erro de rede | Navegador | "Sem conexão. Tentando novamente…" |
| Registro duplicado | Servidor | "Registro já efetuado." |
