# Convenções de Revisão Manual

## Quando Revisar Editais no Dashboard

### Editais de Abertura (Concursos)
✅ **Revise normalmente todos os campos:**
- Órgão, Edital, Cargo, Banca
- Vagas, Taxa, Cronograma

---

### Outros Editais (Convocação, Homologação, Retificação, etc.)

⚠️ **Atenção:** Nem todos os campos se aplicam a editais que não são de abertura de concurso.

#### 🔴 **Regra de Ouro: Se não aplicável, DEIXE VAZIO**

**✅ Correto:**
- Campo Banca: `[deixe em branco ou não edite]`
- Campo Cargo: `[deixe em branco ou não edite]`
- Campo Vagas: `[deixe em branco ou não edite]`

**❌ Incorreto (não use):**
- Campo Banca: `N/A`
- Campo Cargo: `-`
- Campo Vagas: `Não aplicável`

---

## Por que Não Usar "N/A" ou "Não Aplicável"?

### Problema com Valores Sentinela

Se você colocar "N/A" em campos não-aplicáveis:

```
1. Você revisa 5 editais de convocação
2. Coloca "N/A" no campo Banca em todos
3. Sistema de whitelist vê: "N/A" apareceu 5 vezes
4. ❌ Sistema adiciona "N/A" a data/bancas_whitelist.json
5. ❌ Próxima extração: sistema busca literal "N/A" no PDF
6. ❌ Falsos positivos ou poluição de dados
```

### Solução Implementada

O sistema **filtra automaticamente** valores sentinela ao atualizar whitelists:

**Valores ignorados (nunca adicionados a whitelists):**
- `N/A`, `NA`, `N.A.`, `N.A`
- `Não aplicável`, `Não se aplica`
- `-`, `–`, `—` (dashes isolados)
- `Sem informação`, `Não informado`
- `Vazio`, `Nulo`, `NULL`
- Valores muito curtos (≤1 caractere)
- Apenas pontuação/símbolos

**Código:** [src/processing/update_whitelist.py](src/processing/update_whitelist.py#L11-L36)

---

## Estratégia de Revisão por Tipo de Edital

### Edital de Abertura de Concurso
**Campos aplicáveis:** Todos

**Exemplo:**
```
Órgão: Universidade Federal de Minas Gerais
Edital: 01/2026
Cargo: Professor
Banca: CEBRASPE
Vagas: 10
Taxa: R$ 180,00
Prova: 2026-04-15
```

---

### Edital de Convocação
**Campos aplicáveis:** Órgão, Edital, Cargo (se mencionar cargo específico)

**Exemplo:**
```
Órgão: Prefeitura de São Paulo
Edital: 05/2026
Cargo: Analista Administrativo (se mencionar)
Banca: [vazio - não aplicável]
Vagas: [vazio - não aplicável]
Taxa: [vazio - não aplicável]
Prova: [vazio - não aplicável]
```

**Orientação:** Só preencha o campo Cargo se o edital mencionar explicitamente o cargo dos convocados. Caso contrário, deixe vazio.

---

### Edital de Homologação de Resultado
**Campos aplicáveis:** Órgão, Edital, Cargo (se mencionar)

**Exemplo:**
```
Órgão: Tribunal de Justiça do Rio
Edital: 03/2026
Cargo: Técnico Judiciário (se mencionar)
Banca: [vazio - homologação não tem banca]
```

**Orientação:** Homologações são resultados finais publicados. Raramente precisam de revisão de campos técnicos.

---

### Edital de Retificação
**Campos aplicáveis:** Depende do que está sendo retificado

**Exemplo:**
```
Órgão: Ministério da Educação
Edital: 02/2026 (retificação)
Cargo: [vazio - a menos que retificação altere lista de cargos]
```

**Orientação:** Retificações geralmente só corrigem erros do edital original. Se não mencionar dados novos, deixe campos técnicos vazios.

---

## Fluxo de Decisão Rápido

```
┌─────────────────────────────────────────────────┐
│  Campo está preenchido incorretamente?          │
│  ├─ SIM: Corrija para valor correto           │
│  └─ NÃO: Vá para próximo passo                 │
└─────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│  Campo é aplicável a este tipo de edital?       │
│  ├─ SIM: Preencha com valor real               │
│  └─ NÃO: Deixe vazio/em branco                  │
└─────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│  NUNCA use: N/A, -, Não aplicável, etc.        │
└─────────────────────────────────────────────────┘
```

---

## Exemplos Práticos

### ✅ Exemplo 1: Editais Mistos

**Situação:** Edital menciona "concurso para Professor" mas você não encontra a banca no texto.

**Ação:**
```
Cargo: Professor  (✅ está explícito)
Banca: [vazio]    (✅ não encontrado - deixe vazio)
```

**Resultado:** Sistema continua buscando por bancas conhecidas em futuras extrações. Whitelist não é poluída.

---

### ❌ Exemplo 2: Uso Incorreto de Sentinelas

**Situação:** Edital de convocação sem menção a banca.

**Ação incorreta:**
```
Banca: N/A  (❌ não faça isso!)
```

**Problema:** Se 10 pessoas fizerem isso, "N/A" vira termo válido na whitelist.

**Ação correta:**
```
Banca: [deixe vazio ou não edite o campo]
```

---

## Perguntas Frequentes

### 1. "E se eu não tiver certeza se um campo é aplicável?"

**Resposta:** **Deixe vazio**. É melhor não preencher do que preencher com valor sentinela. O sistema de aprendizado funciona melhor com campos vazios do que com "N/A".

---

### 2. "Posso apagar o conteúdo de um campo que veio preenchido incorretamente?"

**Resposta:** **Sim**, absolutamente. Se a extração automática preencheu algo errado e o campo não deveria ter valor, apague para deixar vazio.

**Exemplo:**
```
Extração automática preencheu:
Banca: "Comissão Examinadora da Universidade..."

Se isso não for uma banca externa, apague para:
Banca: [vazio]
```

---

### 3. "Todos os meus 'Outros Editais' estão com campos vazios. Devo revisá-los?"

**Resposta:** **Só se houver erros visíveis**. Se o sistema não extraiu nada e realmente não há nada para extrair (edital de convocação simples), deixe como está. **Não force revisões só por completude**.

**Quando revisar:**
- ✅ Órgão está incorreto/incompleto
- ✅ Edital tem número mas não foi extraído
- ✅ Cargo é mencionado mas não foi capturado

**Quando NÃO revisar:**
- ❌ Campos vazios em editais onde realmente não há essa informação
- ❌ Tentativa de "completar todos os campos" com N/A

---

## Impacto no Sistema de Aprendizado

### Dados Válidos (Bom para Aprendizado)
```json
{
  "changes": [
    {"field": "metadata.cargo", "old": null, "new": "Professor"},
    {"field": "metadata.banca", "old": null, "new": "CEBRASPE"}
  ]
}
```
**Resultado:** "Professor" e "CEBRASPE" adicionados a whitelists (se threshold ≥3).

---

### Dados com Sentinela (Ignorados Automaticamente)
```json
{
  "changes": [
    {"field": "metadata.banca", "old": null, "new": "N/A"}
  ]
}
```
**Resultado:** "N/A" é **filtrado** e **não** adicionado a bancas_whitelist.json.

---

### Melhor Prática: Não Criar Change Desnecessário
```json
{
  "changes": []  // Nenhuma alteração se campos não aplicáveis
}
```
**Resultado:** Revisão não gera exemplo de treinamento (correto, pois não há correção).

---

## Checklist de Revisão

Antes de salvar uma revisão, pergunte-se:

- [ ] Corrigi algum erro real da extração automática?
- [ ] Todos os valores preenchidos são informações reais do edital?
- [ ] Deixei vazios campos não-aplicáveis (sem usar N/A)?
- [ ] Não forcei "completude" artificial de dados?

Se **sim** para todos, sua revisão está ótima! 🎯

---

## Referências

- [Fluxo Completo de Aprendizado Contínuo](continuous_learning_workflow.md)
- [Código de Filtragem de Sentinelas](../src/processing/update_whitelist.py#L11-L36)
- [Lógica de Revisão Manual](../src/web/dashboard_service.py#L540-L670)

---

**Última atualização:** 2026-03-07  
**Convenção estabelecida por:** Sistema de boas práticas de ML/Data Quality
