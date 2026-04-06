# 🟡 YUNA CRM — Painel Interno de Gestão

Sistema completo de gestão para a Yuna Marketing.

---

## 🔐 Acesso
- **Usuário:** `Yunabbc`
- **Senha:** `#Yunabbc26`

---

## 🚀 Como fazer deploy no Railway (GRATUITO)

### Passo 1 — Criar conta
1. Acesse **railway.app** e crie uma conta (pode usar o Google)

### Passo 2 — Novo projeto
1. Clique em **"New Project"**
2. Escolha **"Deploy from GitHub repo"**
   - Ou escolha **"Empty Project"** → **"Deploy from local"**

### Passo 3 — Via GitHub (RECOMENDADO)
1. Crie um repositório privado no **github.com**
2. Faça upload de todos os arquivos desta pasta
3. No Railway, conecte ao repositório
4. O deploy é automático!

### Passo 4 — Configurar domínio
1. No Railway, vá em **Settings → Networking**
2. Clique em **"Generate Domain"**
3. Você receberá um link tipo: `yuna-crm.up.railway.app`

### Passo 5 — Pronto!
- Acesse o link gerado
- Faça login com usuário e senha acima
- Comece a cadastrar seus clientes! 🎉

---

## 📁 Estrutura do projeto

```
yuna_crm/
├── app.py                    # Backend Flask principal
├── requirements.txt          # Dependências Python
├── Procfile                  # Configuração Gunicorn
├── railway.json              # Configuração Railway
└── templates/
    ├── base.html             # Layout base com sidebar
    ├── login.html            # Tela de login
    ├── dashboard.html        # Dashboard principal
    ├── clients.html          # Lista de clientes
    ├── client_form.html      # Cadastro/edição de cliente
    ├── client_detail.html    # Perfil do cliente
    ├── payments.html         # Controle de cobranças
    ├── agenda.html           # Agenda de gravações
    ├── reports.html          # Lista de relatórios
    ├── report_form.html      # Novo relatório
    ├── report_view.html      # Visualização com gráficos
    └── receipt.html          # Recibo para impressão
```

---

## ✅ Funcionalidades

### 👥 Clientes
- Cadastro completo (nome, WhatsApp, Instagram, email)
- Plano, valor, dia de vencimento, forma de pagamento
- Status: Ativo / Pausado / Cancelado
- Perfil individual com histórico completo

### 💰 Cobranças
- Geração automática de cobranças mensais
- Marcar como pago com 1 clique
- Geração de próxima fatura automática ao pagar
- **Recibo em PDF** para impressão
- Alertas de cobranças em atraso

### 📅 Agenda de Gravações
- Agendar gravações nas lojas dos clientes
- Endereço, horário e observações
- Status: Agendado / Concluído / Cancelado

### 📊 Relatórios com Gráficos
**Social Media:**
- Seguidores, visitas no perfil
- Top 3 posts com melhor performance
- Metas mensais com barra de progresso

**Tráfego Pago:**
- Novos clientes WhatsApp, alcance, CTR
- Custo por resultado, valor investido
- Metas com indicadores ✓ / ✗

- Gráficos de evolução histórica mês a mês

### 🔐 Autenticação
- Login com usuário e senha criptografada
- Sessão segura

---

## 🔧 Rodar localmente (opcional)

```bash
pip install flask gunicorn
python app.py
# Acesse: http://localhost:5001
```

---

## 💡 Dicas de uso

- **Ao cadastrar um cliente**, a primeira cobrança é criada automaticamente
- **Ao marcar um pagamento como pago**, a próxima fatura já é gerada
- **Os relatórios** mostram gráficos históricos quando há 2+ meses de dados
- **O recibo** pode ser impresso ou salvo como PDF pelo navegador
