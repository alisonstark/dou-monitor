# 📥 Configurar Navegador para Escolher Onde Salvar Downloads

Por padrão, os navegadores salvam arquivos diretamente na pasta `Downloads`. O DOU Monitor agora inclui feedback visual de download (toast notifications), mas para **escolher o diretório** onde salvar cada PDF, você precisa configurar seu navegador.

## 🌐 Google Chrome / Microsoft Edge

1. Clique no menu **⋮** (três pontos) → **Configurações**
2. Vá em **Downloads** (ou pesquise "downloads" na barra de busca)
3. **Ative** a opção: **"Perguntar onde salvar cada arquivo antes de baixar"**

![Chrome Downloads Settings](https://i.imgur.com/example.png)

**Caminho direto:**
- Chrome: `chrome://settings/downloads`
- Edge: `edge://settings/downloads`

## 🦊 Mozilla Firefox

1. Clique no menu **☰** (três linhas) → **Configurações**
2. Vá em **Geral** → seção **Downloads**
3. Selecione: **"Sempre perguntar onde salvar os arquivos"**

**Caminho direto:**
- `about:preferences#general` → Rolagem até Downloads

## 🍎 Safari (macOS)

1. Menu **Safari** → **Preferências** (ou `Cmd + ,`)
2. Aba **Geral**
3. Em **Local do download de arquivos**, selecione: **"Perguntar para cada download"**

---

## ✨ Experiência no DOU Monitor

### Antes (padrão)
- 📥 Clique no botão → PDF vai direto para `Downloads/`
- ❌ Sem feedback visual
- ❌ Sem opção de escolher local

### Agora (com melhorias)
- 📥 Clique no botão → Ícone muda para ⏳
- 🎯 **Navegador pergunta onde salvar** (se configurado)
- ✅ Toast notification: "PDF baixado com sucesso: dou-123456.pdf"
- ⏱️ Feedback em tempo real durante geração do PDF (Playwright)

---

## 🔧 Solução de Problemas

### "O navegador não está perguntando onde salvar"
1. Verifique se a configuração está ativada
2. Recarregue a página do dashboard (`Ctrl + R`)
3. Teste com outro arquivo

### "Toast não aparece após download"
- Normal se o download demorar mais de 5 segundos (PDFs grandes)
- Toast aparecerá de qualquer forma após timeout

### "Ícone de download fica travado em ⏳"
- Recarregue a página
- Verifique logs do navegador (F12 → Console)
- Pode indicar erro na geração do PDF (verifique logs do Flask)

---

## 📊 Comportamento por Navegador

| Navegador | Pergunta Local | Download Attribute | Toast Support |
|-----------|----------------|-------------------|---------------|
| Chrome 100+ | ✅ (configurável) | ✅ | ✅ |
| Edge 100+ | ✅ (configurável) | ✅ | ✅ |
| Firefox 100+ | ✅ (configurável) | ✅ | ✅ |
| Safari 15+ | ✅ (configurável) | ⚠️ (parcial) | ✅ |

---

## 💡 Dica Pro

Se você sempre salva PDFs do DOU Monitor no mesmo lugar, configure:
1. **Atalho no Windows Explorer**: `Win + E` → Arraste a pasta para acesso rápido
2. **Favoritos no diálogo de salvar**: Clique com botão direito → Adicionar aos favoritos
3. **Macro de teclado** (AutoHotkey/PowerToys): Criar atalho para pasta específica

---

Desenvolvido com ❤️ para melhorar sua experiência de monitoramento de concursos! 🎯
