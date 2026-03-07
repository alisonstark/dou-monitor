# Teste de Aprendizado: Antes vs. Após Filtros de Sentinela

## Cenário: 10 Revisões de Editais de Convocação

### ❌ ANTES (Sem Filtros)

**Revisões feitas pelo usuário:**
```
Edital 1 (Convocação): Banca = "N/A"
Edital 2 (Convocação): Banca = "Não aplicável"
Edital 3 (Convocação): Banca = "-"
Edital 4 (Abertura): Banca = "CEBRASPE"
Edital 5 (Abertura): Banca = "FGV"
Edital 6 (Convocação): Banca = "N/A"
Edital 7 (Convocação): Banca = "NA"
Edital 8 (Abertura): Banca = "CEBRASPE"
Edital 9 (Abertura): Banca = "IDECAN"
Edital 10 (Convocação): Banca = "-"
```

**Resultado do update_whitelist.py (threshold=3):**
```python
Counter: {
    "N/A": 3,           # ❌ Valor sentinela
    "CEBRASPE": 2,      # ✓ Valor real (mas não atinge threshold)
    "-": 2,             # ❌ Valor sentinela
    "FGV": 1,
    "IDECAN": 1,
    "NÃO APLICÁVEL": 1,
    "NA": 1
}

Adicionado a bancas_whitelist.json:
- N/A  ❌ Problema!
```

**Consequência:**
```python
# Próxima extração
texto = "Banca realizadora: N/A conforme edital..."
if "N/A" in bancas_whitelist:  # ❌ Match incorreto!
    return {"banca": "N/A"}
```

---

### ✅ APÓS (Com Filtros Implementados)

**Revisões feitas pelo usuário (mesmas):**
```
Edital 1 (Convocação): Banca = "N/A"
Edital 2 (Convocação): Banca = "Não aplicável"
Edital 3 (Convocação): Banca = "-"
Edital 4 (Abertura): Banca = "CEBRASPE"
Edital 5 (Abertura): Banca = "FGV"
Edital 6 (Convocação): Banca = "N/A"
Edital 7 (Convocação): Banca = "NA"
Edital 8 (Abertura): Banca = "CEBRASPE"
Edital 9 (Abertura): Banca = "IDECAN"
Edital 10 (Convocação): Banca = "-"
```

**Resultado do update_whitelist.py (threshold=3, com _is_valid_value()):**
```python
# Antes do Counter, filtra valores:
_is_valid_value("N/A")          → False (SENTINEL_VALUES)
_is_valid_value("Não aplicável") → False (SENTINEL_VALUES)
_is_valid_value("-")             → False (SENTINEL_VALUES)
_is_valid_value("CEBRASPE")      → True  ✓
_is_valid_value("FGV")           → True  ✓
_is_valid_value("IDECAN")        → True  ✓

Counter apenas com valores válidos: {
    "CEBRASPE": 2,  # ✓ Valor real
    "FGV": 1,       # ✓ Valor real
    "IDECAN": 1     # ✓ Valor real
}

Adicionado a bancas_whitelist.json:
- (Nenhum, pois nenhum valor atingiu threshold=3)
```

**Benefício:**
- ✅ Valores sentinela ignorados automaticamente
- ✅ Whitelist permanece limpa
- ✅ Usuário pode usar N/A temporariamente sem prejudicar sistema

---

## Mais 10 Revisões (Continuação)

**Novas revisões:**
```
Edital 11-13: Banca = "CEBRASPE"
Edital 14-15: Banca = "FGV"
Edital 16: Banca = "N/A"
Edital 17: Banca = "IDECAN"
Edital 18-19: Banca = "-"
Edital 20: Banca = "QUADRIX"
```

**Resultado acumulado (20 revisões):**
```python
Counter válidos: {
    "CEBRASPE": 5,  # ✓ Atinge threshold=3
    "FGV": 3,       # ✓ Atinge threshold=3
    "IDECAN": 2,
    "QUADRIX": 1
}

Adicionado a bancas_whitelist.json:
- CEBRASPE  ✓
- FGV       ✓
```

**Impacto na próxima extração:**
```python
# Sistema agora conhece CEBRASPE e FGV via whitelist
texto = "Organizadora: Fundação Getulio Vargas"

for banca in bancas_whitelist:  # ["CEBRASPE", "FGV", ...]
    if "FGV" in texto or "FUNDAÇÃO GETULIO VARGAS" in texto:
        return {
            "banca": "FGV",  # ✓ Normalizado!
            "confianca": 0.98
        }
```

---

## Comparação de Qualidade

| Métrica | Sem Filtros | Com Filtros |
|---------|-------------|-------------|
| Valores sentinela na whitelist | 3+ | 0 ✓ |
| Falsos positivos | Alto | Baixo ✓ |
| Necessidade de limpeza manual | Sim | Não ✓ |
| Segurança de usar N/A | ❌ Prejudica | ✓ Ignorado |
| Qualidade da whitelist | 40% | 100% ✓ |

---

## Conclusão

**Antes da implementação:**
- ⚠️ Usuário precisava evitar absolutamente N/A, -, etc.
- ⚠️ Um erro humano poluía whitelist permanentemente
- ⚠️ Necessidade de limpeza manual periódica

**Após implementação:**
- ✅ Usuário pode usar N/A temporariamente (será ignorado)
- ✅ Sistema protegido contra poluição de dados
- ✅ Whitelist cresce apenas com valores reais
- ✅ Convenção de "deixar vazio" é preferível, mas N/A não quebra nada

**Melhor de ambos os mundos:**
- Preferência: deixar campos vazios quando não aplicável
- Tolerância: se usar N/A acidentalmente, sistema filtra automaticamente
