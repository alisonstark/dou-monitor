# Fluxo de Aprendizado Contínuo (Human-in-the-Loop)

## Visão Geral

O sistema implementa um **loop de aprendizado heurístico** onde revisões manuais alimentam whitelists que melhoram automaticamente a extração de dados.

```
┌─────────────────────────────────────────────────────────────────┐
│                    CICLO DE APRENDIZADO                          │
└─────────────────────────────────────────────────────────────────┘

1. EXTRAÇÃO AUTOMÁTICA (extractor.py)
   │
   ├─ Regex + Heurística
   ├─ Valida contra whitelists (bancas, cargos)
   ├─ Busca fallback via whitelists se nada encontrado
   │
   └─→ Salva em data/summaries/dou-<id>.json

2. REVISÃO MANUAL (Dashboard Web)
   │
   ├─ Usuário edita campos incorretos/incompletos
   ├─ Sistema cria backup em data/backups/
   ├─ Adiciona metadado _review ao JSON
   │
   └─→ Salva exemplo em data/reviewed_examples/

3. ATUALIZAÇÃO DE WHITELISTS (CLI)
   │
   ├─ Script: python src/processing/update_whitelist.py --threshold 3 --apply
   ├─ Analisa data/reviewed_examples/
   ├─ Conta frequências de cargos/bancas corrigidas
   │
   └─→ Adiciona novos itens a data/cargos_whitelist.json, data/bancas_whitelist.json

4. PRÓXIMA EXTRAÇÃO (Melhoria Automática)
   │
   └─ extractor.py agora usa whitelists expandidas
      ├─ Maior taxa de acerto em validação/normalização
      └─ Maior cobertura em busca fallback
```

---

## 1. Revisão Manual no Dashboard

### Interface de Edição

**Seções revisáveis:**
- ✅ **Concursos Abertos**: Editais de abertura (keywords: "abertura", "inicio", "iniciado")
- ✅ **Outros Editais**: Todos os outros editais/concursos (convocação, homologação, retificação, etc.)

**Campos editáveis:**
- `orgao` (Órgão)
- `edital_numero` (Número do Edital)
- `cargo` (Cargo)
- `banca` (Banca organizadora)
- `vagas_total` (Total de vagas)
- `taxa_inscricao` (Taxa de inscrição)
- `data_prova` (Data da prova)

### Como Revisar

1. No dashboard, clique no botão **✏️** ao lado do edital
2. Edite os campos no formulário inline
3. Clique em **"Salvar Revisão"**

**O que acontece nos bastidores:**
```python
# src/web/dashboard_service.py :: apply_manual_review()
1. Cria backup: data/backups/<filename>.YYYYMMDDTHHMMSSZ.bak
2. Atualiza data/summaries/<filename>.json com valores corrigidos
3. Adiciona metadado _review:
   {
     "last_reviewed": "20260306T123456Z",
     "reviewer": "dashboard-manual-review",
     "source": "dashboard"
   }
4. Exporta exemplo: data/reviewed_examples/<filename>.YYYYMMDDTHHMMSSZ.json
   {
     "summary_file": "dou-123456.json",
     "pdf_file": "editais/...",
     "timestamp": "...",
     "reviewer": "...",
     "changes": [
       {"field": "metadata.cargo", "old": "...", "new": "PROFESSOR"}
     ]
   }
```

---

## 2. Atualização de Whitelists (CLI)

### Comando

```bash
# Dry-run: mostra sugestões sem aplicar
python src/processing/update_whitelist.py --threshold 3

# Aplicar: adiciona automaticamente a whitelists
python src/processing/update_whitelist.py --threshold 3 --apply
```

### Lógica de Threshold

- `--threshold 3` (padrão): Adiciona termos que aparecem **≥3 vezes** em revisões manuais
- Evita ruído de correções pontuais (typos, casos raros)
- Garante que apenas padrões consistentes sejam aprendidos

### Exemplo de Output

```
Candidates for metadata.banca whitelist (name, count):
  - IDECAN: 5
  - INSTITUTO AOCP: 4
  - FUNDEP: 3
  Added Idecan to metadata.banca whitelist
  Added Instituto Aocp to metadata.banca whitelist
  Added Fundep to metadata.banca whitelist
Whitelist updated at data/bancas_whitelist.json

Candidates for metadata.cargo whitelist (name, count):
  - PROFESSOR: 8
  - TÉCNICO ADMINISTRATIVO: 4
  Added Professor to metadata.cargo whitelist
  Added Técnico Administrativo to metadata.cargo whitelist
Whitelist updated at data/cargos_whitelist.json
```

---

## 3. Como Whitelists Melhoram a Extração

### Cargo (metadata.cargo)

**Função 1: Validação/Normalização**
```python
# src/extraction/extractor.py :: extract_basic_metadata()
cargo_val = "professor de matematica - ampla concorrencia"
cargos_whitelist = ["PROFESSOR", "ANALISTA", ...]

# Se cargo extraído contém termo da whitelist, normaliza
if "PROFESSOR" in cargo_val.upper():
    cargo_val = "Professor"  # Forma canônica
```

**Função 2: Busca Fallback**
```python
# Se regex NÃO encontrou cargo, busca no texto por termos whitelistados
if not cargo_val:
    for whitelisted_cargo in cargos_whitelist:
        if whitelisted_cargo.upper() in text.upper()[:3000]:
            cargo_val = whitelisted_cargo.title()
            break
```

### Banca (metadata.banca)

**Função: Matching Direto**
```python
# src/extraction/extractor.py :: extract_banca_struct()
bancas_whitelist = _load_bancas_whitelist()  # ["CEBRASPE", "FGV", ...]

for banca in bancas_whitelist:
    if banca.upper() in text.upper():
        return {"nome": banca, "tipo": "externa", "confianca_extracao": 0.98}
```

**Impacto:**
- ✅ Maior precisão: "FUNDACAO GETULIO VARGAS" → "FGV"
- ✅ Maior recall: Detecta bancas menos conhecidas adicionadas via revisão
- ✅ Sem falsos positivos: Threshold garante apenas termos validados

---

## 4. Métricas de Sucesso (Planejadas)

### Baseline Atual (Pré-IA)
Para medir **se** e **quanto** o loop de aprendizado melhora a extração, calcule:

```python
# Para cada campo (cargo, banca, edital_numero, etc):
precisão = corretos / (corretos + falsos_positivos)
recall = corretos / (corretos + falsos_negativos)
F1-score = 2 * (precisão * recall) / (precisão + recall)
```

**Meta de coleta antes de IA:**
- 📊 **50-100 revisões manuais** acumuladas em `data/reviewed_examples/`
- 📈 Baseline quantitativa: precisão/recall por campo
- 🎯 Identificar padrões de erro: onde heurística falha mais

### Quando Considerar IA

**Critérios (baseado em saas_strategy_personal.md):**
1. ✅ Baseline quantitativa estabelecida
2. ✅ ≥50 revisões manuais como ground truth
3. ✅ Padrões de erro identificados (ex: ruído textual em campos extraídos)
4. ⚠️ Heurística + whitelists atingiram limite (~40-50% precision)

**Abordagem híbrida recomendada:**
```
Heurística (regex/whitelist) → IA (limpeza/normalização) → Output final
         ↑                                                      ↓
         └──────────── Sistema de revisão (ground truth) ──────┘
```

**Não substitua heurística por IA end-to-end** — use IA apenas para pós-processamento incremental.

---

## 5. Checklist Operacional

### Rotina Semanal (Manutenção do Loop)

- [ ] Revisar manualmente 5-10 editais com baixa confiança
- [ ] Rodar `update_whitelist.py --threshold 3 --apply` semanalmente
- [ ] Monitorar evolução de `data/reviewed_examples/` (meta: 50-100)
- [ ] Exportar métricas de precisão/recall mensalmente

### Sinais de que Whitelists Estão Funcionando

✅ **Bom:**
- Campos anteriormente `null` passam a ser preenchidos automaticamente
- Normalização consistente (ex: "FUNDAO GETULIO VARGAS" → "FGV")
- Redução de revisões manuais necessárias ao longo do tempo

❌ **Problema:**
- Whitelist cresce descontroladamente (>200 itens) → aumentar threshold
- Falsos positivos aparecem → revisar critérios de matching
- Nenhuma melhoria perceptível após 30 revisões → heurística precisa de refatoração

---

## 6. Limitações do Sistema Atual

### Design Intencional (Heurística, não IA)
- ✅ **Explicável**: Toda extração é auditável (regex + whitelist)
- ✅ **Barato**: Sem custos de API LLM
- ✅ **Previsível**: Sem "alucinações" ou variabilidade de modelo

### Trade-offs
- ⚠️ **Ruído textual**: Campos capturam texto contextual não-limpo
  - Exemplo: `cargo = "PROFESSOR -\nSALVADOR/BA e LILIANE..."`
- ⚠️ **Cobertura limitada**: Depende de padrões regex pré-programados
- ⚠️ **Manual**: Requer revisão humana para alimentar whitelists

**Solução futura (Fase 3):** IA híbrida para limpeza de campos extraídos (não extração end-to-end).

---

## 7. Referências de Código

| Componente | Arquivo | Função Principal |
|------------|---------|------------------|
| Extração automática | `src/extraction/extractor.py` | `extract_basic_metadata()`, `extract_banca_struct()` |
| Revisão manual (Dashboard) | `src/web/dashboard_service.py` | `apply_manual_review()` |
| Atualização de whitelists | `src/processing/update_whitelist.py` | `find_candidates()`, `update_whitelist()` |
| Loading de whitelists | `src/extraction/extractor.py` | `_load_cargos_whitelist()`, `_load_bancas_whitelist()` |

---

## 8. Próximos Passos

1. **Imediato (esta sessão):**
   - ✅ Expansão do dashboard para revisão de "Outros Editais" (concluído)
   - ✅ Validação de que reviewed_examples/ é alimentado corretamente

2. **Próximos 30 dias:**
   - 📊 Coletar 50-100 revisões manuais (meta: 2-3 por dia)
   - 🔄 Rodar `update_whitelist.py --apply` semanalmente
   - 📈 Medir baseline: precision/recall por campo

3. **60-90 dias:**
   - 🤖 Avaliar introdução de IA híbrida para limpeza de campos
   - 🧪 A/B testing: heurística pura vs heurística+IA
   - 📊 Comparar métricas pré e pós-IA

---

**Última atualização:** 2026-03-06  
**Autor:** Sistema de documentação automático
