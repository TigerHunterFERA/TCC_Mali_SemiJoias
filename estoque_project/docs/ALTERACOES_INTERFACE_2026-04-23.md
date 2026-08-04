# Mali Semijoias — Documentação das Alterações (Interface)

**Data:** 23/04/2026  
**Projeto:** `c:\Users\Mali\Downloads\TCC_MALI_SEMIJOIAS\estoque_project`  

## Objetivo

Deixar a interface do sistema (Dashboard / Produtos / Adicionar / Editar / Login) mais fiel ao layout do Figma Maker, **mantendo o back-end conectado ao MySQL** e sem alterar a estrutura do banco.

## Resumo do que foi alterado

- **Correções funcionais (sem quebrar DB)**
  - Ajuste do `dashboard()` para buscar dados do MySQL e evitar travar a tela em caso de erro.
  - Correção do template renderizado no `editar_produto()` (antes apontava para um arquivo inexistente).
  - Remoção de rota duplicada em `urls.py`.
  - Ajuste de variáveis no template `editar.html` para usar `produto.estoque` (compatível com o model/DB).

- **Aprimoramento da interface**
  - `dashboard.html` reestruturado para layout com sidebar + cards + atalhos (“Produtos / Pedidos / Chatbot”).
  - `produtos.html` refeito para remover CSS inline grande e padronizar no `style.css`.
  - `style.css` ajustado para corrigir alinhamento geral (sidebar + páginas com conteúdo) e melhorar login/cards.
  - Pequeno ajuste em `adicionar.html` para manter o menu consistente.

## Como as alterações foram feitas (passo a passo)

1. **Localização da estrutura do projeto**
   - Confirmado que o Django roda em `estoque_project` (pasta raiz do projeto Django).
   - Localizados os arquivos principais com a estrutura:
     - `estoque_app/views.py`
     - `estoque_app/urls.py`
     - `estoque_app/templates/estoque_app/*.html`
     - `estoque_app/static/estoque_app/style.css`

2. **Garantia de conexão com o banco**
   - O arquivo `estoque_project/settings.py` já estava configurado com MySQL e porta `3307`.
   - O `dashboard()` foi atualizado para usar `Produto.objects.all()` com `try/except`.

3. **Aplicação do layout com conceitos básicos**
   - Uso de **`for`** no dashboard (somatória do valor em estoque e contagem de itens com estoque baixo).
   - Uso de **`if`** no template do produtos (confirm de exclusão no front).
   - Uso de **`try/except`** para evitar quebra da tela quando houver erro de DB/dados.

4. **Verificação**
   - Rodado: `python manage.py check` (sem erros).
   - Servidor iniciado em `127.0.0.1:8000`.

---

## Arquivo 1 — `views.py`

**Path:** `c:\Users\Mali\Downloads\TCC_MALI_SEMIJOIAS\estoque_project\estoque_app\views.py`

### Alterações realizadas

- **`dashboard()`**: passou a consultar `Produto` via ORM (MySQL) e calcular:
  - `total_produtos`
  - `valor_total` (com `for`)
  - `estoque_baixo` (com `if`)
  - fallback com `try/except` exibindo `erro_db` no template
- **`editar_produto()`**: corrigido `render()` para `editar.html` (antes estava `Reditar.html`)

### Código atual (completo)

```python
# from django.shortcuts import render, redirect
# import json
#
# def carregar_dados():
#     try:
#         with open("estoque_app/data.json", "r") as f:
#             return json.load(f)
#     except:
#         return {"produtos": []}
#
# def salvar_dados(dados):
#     with open("estoque_app/data.json", "w") as f:
#         json.dump(dados, f, indent=4)
#
# def dashboard(request):
#     dados = carregar_dados()
#     return render(request, "estoque_app/dashboard.html", {"produtos": dados["produtos"]})
#
# def listar_produtos(request):
#     dados = carregar_dados()
#     return render(request, "estoque_app/produtos.html", {"produtos": dados["produtos"]})
#
# def adicionar_produto(request):
#     if request.method == "POST":
#         nome = request.POST.get("nome")
#         quantidade = request.POST.get("quantidade")
#
#         if not nome or not quantidade:
#             return render(request, "estoque_app/adicionar.html", {"mensagem": "Preencha todos os campos."})
#
#         try:
#             quantidade = int(quantidade)
#         except:
#             return render(request, "estoque_app/adicionar.html", {"mensagem": "Quantidade deve ser número."})
#
#         dados = carregar_dados()
#         novo_id = len(dados["produtos"]) + 1
#         dados["produtos"].append({"id": novo_id, "nome": nome, "quantidade": quantidade})
#         salvar_dados(dados)
#
#         return render(request, "estoque_app/adicionar.html", {"mensagem": "Produto adicionado com sucesso!"})
#
#     return render(request, "estoque_app/adicionar.html")
#
# def editar_produto(request, produto_id):
#     dados = carregar_dados()
#     produto = next((p for p in dados["produtos"] if p["id"] == produto_id), None)
#
#     if not produto:
#         return render(request, "estoque_app/produtos.html", {"produtos": dados["produtos"], "mensagem": "Produto não encontrado."})
#
#     if request.method == "POST":
#         nome = request.POST.get("nome")
#         quantidade = request.POST.get("quantidade")
#
#         if not nome or not quantidade:
#             return render(request, "estoque_app/editar.html", {"produto": produto, "mensagem": "Preencha todos os campos."})
#
#         try:
#             quantidade = int(quantidade)
#         except:
#             return render(request, "estoque_app/editar.html", {"produto": produto, "mensagem": "Quantidade deve ser número."})
#
#         produto["nome"] = nome
#         produto["quantidade"] = quantidade
#         salvar_dados(dados)
#
#         return redirect("produtos")
#
#     return render(request, "estoque_app/editar.html", {"produto": produto})
#
#
# def remover_produto(request, produto_id):
#     dados = carregar_dados()
#     dados["produtos"] = [p for p in dados["produtos"] if p["id"] != produto_id]
#     salvar_dados(dados)
#     return redirect("produtos")

from django.shortcuts import render, redirect, get_object_or_404
from .models import Produto
# from django.shortcuts import render, redirect
import json

def login(request):
    if request.method == "POST":
        usuario = request.POST.get("usuario")
        senha = request.POST.get("senha")

        # Aqui você pode validar usuário/senha futuramente
        if usuario and senha:
            # Se login for válido, redireciona para o dashboard
            return redirect("dashboard")
        else:
            return render(request, "estoque_app/login.html", {"mensagem": "Usuário ou senha inválidos."})

    # Se for GET, apenas renderiza a tela de login
    return render(request, "estoque_app/login.html")

def dashboard(request):
    try:
        produtos = Produto.objects.all()

        total_produtos = produtos.count()

        valor_total = 0
        estoque_baixo = 0
        for p in produtos:
            try:
                valor_total += float(p.preco) * int(p.estoque)
            except Exception:
                pass

            try:
                if int(p.estoque) > 0 and int(p.estoque) <= 5:
                    estoque_baixo += 1
            except Exception:
                pass

        return render(
            request,
            "estoque_app/dashboard.html",
            {
                "total_produtos": total_produtos,
                "pedidos_hoje": 0,
                "receita_total": 0,
                "estoque_baixo": estoque_baixo,
                "valor_total": round(valor_total, 2),
            },
        )
    except Exception as e:
        return render(request, "estoque_app/dashboard.html", {"erro_db": str(e)})

def listar_produtos(request):
    produtos = Produto.objects.all()   # Busca direto no banco
    return render(request, "estoque_app/produtos.html", {"produtos": produtos})

def adicionar_produto(request):
    if request.method == "POST":
        Produto.objects.create(
            nome=request.POST.get("nome"),
            descricao=request.POST.get("descricao"),
            preco=request.POST.get("preco"),
            estoque=request.POST.get("quantidade"),
            tipo=request.POST.get("tipo"),
            categoria=request.POST.get("categoria")
        )
        return redirect("produtos")

    return render(request, "estoque_app/adicionar.html")

def editar_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)

    if request.method == "POST":
        produto.nome = request.POST.get("nome")
        produto.descricao = request.POST.get("descricao")
        produto.preco = request.POST.get("preco")
        produto.estoque = request.POST.get("quantidade")
        produto.tipo = request.POST.get("tipo")
        produto.categoria = request.POST.get("categoria")
        produto.save()
        return redirect("produtos")

    return render(request, "estoque_app/editar.html", {"produto": produto})

def remover_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)
    produto.delete()
    return redirect("produtos")
```

---

## Arquivo 2 — `urls.py`

**Path:** `c:\Users\Mali\Downloads\TCC_MALI_SEMIJOIAS\estoque_project\estoque_app\urls.py`

### Alterações realizadas

- Remoção de rota duplicada de `produtos/` (havia duas entradas com o mesmo path).

### Código atual (completo)

```python
from django.urls import path
from . import views

urlpatterns = [
    path("", views.login, name="login"), 
    path("login/", views.login, name="login"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("produtos/", views.listar_produtos, name="produtos"), 
    path("adicionar/", views.adicionar_produto, name="adicionar"),
    path("editar/<int:produto_id>/", views.editar_produto, name="editar"),
    path("remover/<int:produto_id>/", views.remover_produto, name="remover"),
]
```

---

## Arquivo 3 — `dashboard.html`

**Path:** `c:\Users\Mali\Downloads\TCC_MALI_SEMIJOIAS\estoque_project\estoque_app\templates\estoque_app\dashboard.html`

### Alterações realizadas

- Layout com sidebar fixa e área principal.
- Cards de métricas e atalhos rápidos (estrutura semelhante ao Figma Maker).
- Exibição de mensagem de erro (`erro_db`) caso falhe o banco.

### Código atual (completo)

```html
<!-- Conteúdos antigos comentados foram mantidos como histórico -->
{% load static %}
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Mali Semijoias - Dashboard</title>
    <link rel="stylesheet" href="{% static 'estoque_app/style.css' %}">
</head>
<body>
    <nav class="sidebar">
        <h2>MALI</h2>
        <a href="{% url 'dashboard' %}">📊 Dashboard</a>
        <a href="{% url 'produtos' %}">💍 Estoque</a>
        <a href="#">⚙️ Configurações</a>
    </nav>

    <main class="main-content">
        <header class="page-header">
            <h1>Bem-vindo à Mali Semijoias</h1>
            {% if erro_db %}
                <p class="erro">Erro ao conectar no banco: {{ erro_db }}</p>
            {% endif %}
        </header>

        <section class="dashboard-grid">
            <div class="metric-card">
                <div class="metric-icon">📦</div>
                <div>
                    <div class="metric-label">Total de Produtos</div>
                    <div class="metric-value">{{ total_produtos|default:0 }}</div>
                </div>
            </div>

            <div class="metric-card">
                <div class="metric-icon">🗓️</div>
                <div>
                    <div class="metric-label">Pedidos Hoje</div>
                    <div class="metric-value">{{ pedidos_hoje|default:0 }}</div>
                </div>
            </div>

            <div class="metric-card">
                <div class="metric-icon">💰</div>
                <div>
                    <div class="metric-label">Receita Total</div>
                    <div class="metric-value">R$ {{ receita_total|default:0 }}</div>
                </div>
            </div>

            <div class="metric-card">
                <div class="metric-icon">⚠️</div>
                <div>
                    <div class="metric-label">Estoque Baixo</div>
                    <div class="metric-value">{{ estoque_baixo|default:0 }}</div>
                </div>
            </div>
        </section>

        <section class="quick-actions">
            <a href="{% url 'produtos' %}" class="action-card">
                <div class="action-icon">📦</div>
                <div>
                    <div class="action-title">Produtos</div>
                    <div class="action-subtitle">Gerenciar catálogo</div>
                </div>
            </a>

            <a href="#" class="action-card">
                <div class="action-icon">🧾</div>
                <div>
                    <div class="action-title">Pedidos</div>
                    <div class="action-subtitle">Ver vendas realizadas</div>
                </div>
            </a>

            <a href="#" class="action-card">
                <div class="action-icon">💬</div>
                <div>
                    <div class="action-title">Chatbot</div>
                    <div class="action-subtitle">Interface de vendas</div>
                </div>
            </a>
        </section>
    </main>
</body>
</html>
```

---

## Arquivo 4 — `produtos.html`

**Path:** `c:\Users\Mali\Downloads\TCC_MALI_SEMIJOIAS\estoque_project\estoque_app\templates\estoque_app\produtos.html`

### Alterações realizadas

- Remoção do CSS inline grande e padronização via `style.css`.
- Sidebar igual ao Dashboard.
- Tabela organizada e ações de editar/remover.

### Código atual (completo)

```html
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Mali Semijoias - Estoque</title>
    {% load static %}
    <link rel="stylesheet" href="{% static 'estoque_app/style.css' %}">
</head>
<body>

    <nav class="sidebar">
        <h2>MALI</h2>
        <a href="{% url 'dashboard' %}">📊 Dashboard</a>
        <a href="{% url 'produtos' %}">💍 Estoque</a>
        <a href="#">⚙️ Configurações</a>
    </nav>

    <main class="main-content">
        <header class="page-header" style="display:flex; align-items:center; justify-content:space-between; gap: 16px;">
            <div>
                <h1>Gerenciar Produtos</h1>
                <p style="margin-top:6px; color:#6f6f6f;">Controle de inventário</p>
            </div>
            <a href="{% url 'adicionar' %}" class="btn-mali">+ Novo Produto</a>
        </header>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Produto</th>
                        <th>Categoria</th>
                        <th>Preço</th>
                        <th>Estoque</th>
                        <th style="text-align:right;">Ações</th>
                    </tr>
                </thead>
                <tbody>
                    {% for produto in produtos %}
                    <tr>
                        <td style="font-weight: 700;">{{ produto.nome }}</td>
                        <td>{{ produto.categoria }}</td>
                        <td>R$ {{ produto.preco }}</td>
                        <td>{{ produto.estoque }}</td>
                        <td style="text-align:right;">
                            <a href="{% url 'editar' produto.id %}" class="btn-mali" style="text-decoration:none; padding:8px 12px;">✏️</a>
                            <a href="{% url 'remover' produto.id %}" class="btn-mali" style="text-decoration:none; padding:8px 12px; background:#ff5e9e; margin-left:10px;" onclick="return confirm('Deseja excluir este item?')">🗑️</a>
                        </td>
                    </tr>
                    {% empty %}
                    <tr>
                        <td colspan="5" style="text-align:center; padding:30px;">Nenhum produto cadastrado no momento.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>

</body>
</html>
```

---

## Arquivo 5 — `adicionar.html`

**Path:** `c:\Users\Mali\Downloads\TCC_MALI_SEMIJOIAS\estoque_project\estoque_app\templates\estoque_app\adicionar.html`

### Alterações realizadas

- Menu consistente (incluído “Configurações”).
- Mantida estrutura simples para formulário.

### Código atual (completo)

```html
{% load static %}
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Adicionar Produto</title>
    <link rel="stylesheet" href="{% static 'estoque_app/style.css' %}">
</head>
<body>
    <!-- Sidebar fixa -->
    <nav class="sidebar">
        <h2>MALI</h2>
        <a href="{% url 'dashboard' %}">📊 Dashboard</a>
        <a href="{% url 'produtos' %}">💍 Estoque</a>
        <a href="#">⚙️ Configurações</a>
    </nav>

    <!-- Área principal -->
    <main class="main-content">
        <header>
            <h1>Adicionar Novo Produto</h1>
        </header>

        <!-- Card estilizado -->
        <div class="card">
            <form method="POST" class="form-container">
                {% csrf_token %}
                <label>Nome do Produto</label>
                <input type="text" name="nome" required>
                <br>

                <label>Tipo do Produto</label>
                <input type="text" name="tipo" placeholder="Ex: anel, colar...">
                <br>

                <label>Categoria</label>
                <input type="text" name="categoria">
                <br>

                <label>Banho</label>
                <select name="banho">
                    <option>Ouro</option>
                    <option>Prata</option>
                </select>
                <br>

                <label>Peso (g)</label>
                <input type="number" name="peso" value="0">
                <br>

                <label>Preço (R$)</label>
                <input type="number" step="0.01" name="preco" value="0">
                <br>

                <label>Estoque</label>
                <input type="number" name="quantidade" value="0">
                <br>

                <label>URL da Imagem</label>
                <input type="url" name="imagem" placeholder="https://...">
                <br>

                <label>Descrição</label>
                <textarea name="descricao"></textarea>
                <br>

                <button type="submit" class="btn-mali">Adicionar Produto</button>
                <a href="{% url 'produtos' %}" class="btn-mali" style="background:#ccc; color:#333;">Cancelar</a>
            </form>
        </div>
    </main>
</body>
</html>
```

---

## Arquivo 6 — `editar.html`

**Path:** `c:\Users\Mali\Downloads\TCC_MALI_SEMIJOIAS\estoque_project\estoque_app\templates\estoque_app\editar.html`

### Alterações realizadas

- Correção do campo “Estoque” para `{{ produto.estoque }}`.

### Código atual (completo)

```html
{% load static %}
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Editar Produto</title>
    <link rel="stylesheet" href="{% static 'estoque_app/style.css' %}">
</head>
<body>
    <!-- Sidebar fixa -->
    <nav class="sidebar">
        <h2>MALI</h2>
        <a href="{% url 'dashboard' %}">📊 Dashboard</a>
        <a href="{% url 'produtos' %}">💍 Estoque</a>
    </nav>

    <!-- Área principal -->
    <main class="main-content">
        <header>
            <h1>Editar Produto</h1>
        </header>

        <!-- Card estilizado -->
        <div class="card">
            <form method="POST" class="form-container">
                {% csrf_token %}

                <label>Nome do Produto</label>
                <input type="text" name="nome" value="{{ produto.nome }}" required><br>

                <label>Tipo do Produto</label>
                <input type="text" name="tipo" value="{{ produto.tipo }}" placeholder="Ex: anel, colar..."><br>

                <label>Categoria</label>
                <input type="text" name="categoria" value="{{ produto.categoria }}"><br>

                <label>Banho</label>
                <select name="banho">
                    <option {% if produto.banho == "Ouro" %}selected{% endif %}>Ouro</option>
                    <option {% if produto.banho == "Prata" %}selected{% endif %}>Prata</option>
                </select><br>

                <label>Peso (g)</label>
                <input type="number" name="peso" value="{{ produto.peso|default:0 }}"><br>

                <label>Preço (R$)</label>
                <input type="number" step="0.01" name="preco" value="{{ produto.preco }}" required><br>

                <label>Estoque</label>
                <input type="number" name="quantidade" value="{{ produto.estoque }}" required><br>

                <label>URL da Imagem</label>
                <input type="url" name="imagem" value="{{ produto.imagem }}" placeholder="https://..."><br>
                <label>Descrição</label>
                <textarea name="descricao">{{ produto.descricao }}</textarea><br>

                <button type="submit" class="btn-mali">Salvar Alterações</button>
                <a href="{% url 'produtos' %}" class="btn-mali" style="background:#ccc; color:#333;">Cancelar</a>
            </form>

            {% if mensagem %}
                <p class="erro">{{ mensagem }}</p>
            {% endif %}
        </div>
    </main>
</body>
</html>
```

---

## Arquivo 7 — `style.css`

**Path:** `c:\Users\Mali\Downloads\TCC_MALI_SEMIJOIAS\estoque_project\estoque_app\static\estoque_app\style.css`

### Alterações realizadas (principais)

- O `body` deixou de centralizar tudo, para permitir sidebar + conteúdo.
- Criadas classes do dashboard (`metric-card`, `quick-actions`, `action-card`).
- Ajustado o login (`.login-page`, `.login-box`).
- Padronização de bordas, sombras e tipografia para se aproximar do Figma Maker.

### Código atual (completo)

```css
/* (Arquivo completo abaixo) */
/* body {
    font-family: Arial, sans-serif;
    background-color: #f4f6f9;
    margin: 0;
    padding: 0;
}

.sidebar {
    width: 200px;
    background: #007bff;
    color: white;
    position: fixed;
    height: 100%;
    padding: 20px;
}

.sidebar ul {
    list-style: none;
    padding: 0;
}

.sidebar ul li {
    margin: 15px 0;
}

.sidebar ul li a {
    color: white;
    text-decoration: none;
}

.main-content {
    margin-left: 220px;
    padding: 20px;
}

.form-container {
    margin: 50px auto;
    width: 400px;
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 0 10px #ccc;
} */
/* 
... (blocos antigos comentados preservados no arquivo real) ...
*/

/* Reset básico para garantir que tudo fique igual em qualquer navegador */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'Inter', 'Segoe UI', Roboto, sans-serif;
}

::root {
    --primaria-gradiente: linear-gradient(135deg, #FF4D6D 0%, #FF9966 100%);
    --cor-fundo: #FDF2F4;
    --cor-texto: #333;
    --branco: #ffffff;
    --borda-raio: 12px;
}

/* Estilo geral inspirado no Figma Maker */
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #ff9a9e 0%, #fad0c4 99%, #fad0c4 100%);
    margin: 0;
    padding: 0;
    display: flex;
    justify-content: flex-start;
    align-items: stretch;
    min-height: 100vh;
}

.login-page {
    justify-content: center;
    align-items: center;
    padding: 20px;
}

.erro {
    color: #fa5252;
    margin-top: 10px;
    font-size: 0.9rem;
}

.sidebar {
    width: 260px;
    background: var(--primaria-gradiente);
    padding: 30px 20px;
    display: flex;
    flex-direction: column;
    color: var(--branco);
    position: fixed;
    height: 100%;
}

.sidebar h2 {
    font-size: 1.5rem;
    margin-bottom: 40px;
    text-align: center;
    font-weight: 800;
    letter-spacing: 1px;
}

.sidebar a {
    color: var(--branco);
    text-decoration: none;
    padding: 12px 15px;
    margin-bottom: 10px;
    border-radius: 8px;
    transition: 0.3s;
    display: flex;
    align-items: center;
    font-weight: 500;
}

.sidebar a:hover {
    background: rgba(255, 255, 255, 0.2);
}

/* Área principal de conteúdo */
.main-content {
    margin-left: 260px;
    flex: 1;
    padding: 40px;
}

header {
    margin-bottom: 30px;
}

.page-header {
    margin-bottom: 30px;
}

h1 {
    font-size: 2rem;
    color: #FF4D6D;
}

/* Cards do Dashboard */
.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
}

.metric-card {
    background: var(--branco);
    border-radius: var(--borda-raio);
    box-shadow: 0 10px 20px rgba(0,0,0,0.05);
    padding: 22px;
    display: flex;
    gap: 14px;
    align-items: center;
    border-left: 5px solid rgba(255, 77, 109, 0.6);
}

.metric-icon {
    width: 46px;
    height: 46px;
    border-radius: 14px;
    display: grid;
    place-items: center;
    background: rgba(255, 77, 109, 0.08);
    font-size: 1.2rem;
}

.metric-label {
    font-size: 0.9rem;
    color: #6f6f6f;
}

.metric-value {
    font-size: 2rem;
    font-weight: bold;
    color: #333;
}

.card {
    background: var(--branco);
    padding: 25px;
    border-radius: var(--borda-raio);
    box-shadow: 0 10px 20px rgba(0,0,0,0.05);
    border-left: 5px solid #FF4D6D;
}

/* Tabela */
.table-container {
    background: var(--branco);
    padding: 20px;
    border-radius: var(--borda-raio);
    margin-top: 30px;
    box-shadow: 0 10px 20px rgba(0,0,0,0.05);
}

table {
    width: 100%;
    border-collapse: collapse;
}

th {
    text-align: left;
    padding: 15px;
    border-bottom: 2px solid #eee;
    color: #666;
}

td {
    padding: 15px;
    border-bottom: 1px solid #eee;
}

/* Atalhos */
.quick-actions {
    margin-top: 26px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 18px;
}

.action-card {
    background: var(--branco);
    border-radius: var(--borda-raio);
    box-shadow: 0 10px 20px rgba(0,0,0,0.05);
    padding: 18px;
    text-decoration: none;
    color: inherit;
    display: flex;
    gap: 14px;
    align-items: center;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.action-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 14px 30px rgba(0,0,0,0.08);
}

.action-icon {
    width: 48px;
    height: 48px;
    border-radius: 16px;
    display: grid;
    place-items: center;
    background: rgba(255, 153, 102, 0.12);
    font-size: 1.25rem;
}

.action-title {
    font-weight: 700;
}

.action-subtitle {
    margin-top: 2px;
    font-size: 0.9rem;
    color: #6f6f6f;
}

/* Botões */
.btn-mali {
    background-color: #ff7eb3;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    cursor: pointer;
    font-weight: bold;
    text-decoration: none;
}

.btn-mali:hover {
    background-color: #ff5e9e;
}

/* Login */
.login-box {
    background: rgba(255, 255, 255, 0.92);
    border-radius: 22px;
    padding: 34px;
    width: 100%;
    max-width: 420px;
    box-shadow: 0 15px 35px rgba(0,0,0,0.15);
}

.login-box h2 {
    text-align: center;
    margin-bottom: 18px;
    color: #FF4D6D;
    font-size: 1.6rem;
}

.login-box input {
    width: 100%;
    padding: 12px 14px;
    border-radius: 10px;
    border: 1px solid #e8e8e8;
    background: #fff;
    outline: none;
    margin-top: 12px;
}

.login-box button {
    width: 100%;
    margin-top: 18px;
    padding: 12px 14px;
    border-radius: 12px;
    border: none;
    background: var(--primaria-gradiente);
    color: #fff;
    font-weight: 800;
    cursor: pointer;
}

.login-box button:hover {
    filter: brightness(0.96);
}
```

