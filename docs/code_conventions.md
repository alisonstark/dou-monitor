# Convenções de Código

Este projeto adota padronização gradual para reduzir inconsistências entre português e inglês.

## Regra geral

- Código interno (módulos, funções, variáveis, rotas novas): inglês.
- Interface ao usuário (labels, mensagens, textos de tela): português.
- Documentação técnica pode ser bilíngue, mas nomes de símbolos de código devem seguir inglês.

## Compatibilidade

- Ao renomear símbolo/rota existente, manter alias temporário para evitar quebra.
- Remover alias em etapa futura somente após migração completa.

## Exemplos

- Preferir `notices_api` em vez de `concursos_api`.
- Preferir `categorize_notices` em vez de `categorize_concursos`.
- Manter textos como `"Usuário ou senha inválidos"` em português.

## Plano incremental

1. `src/web/`:
	Status: em andamento.
	Entregue: `notices_api` e `categorize_notices` com aliases legados.
	Pendente: revisar nomes internos remanescentes e remover aliases ao final da migração.
2. `src/extraction/`:
	Status: pendente.
	Objetivo: padronizar nomes de funções/variáveis para inglês, mantendo compatibilidade transitória.
3. `src/processing/` e `src/cli/`:
	Status: pendente.
	Objetivo: alinhar comandos/flags/nomes internos sem quebrar fluxos existentes.
4. Encerramento:
	Status: pendente.
	Objetivo: remover aliases temporários, atualizar testes/documentação e consolidar padrão final.
