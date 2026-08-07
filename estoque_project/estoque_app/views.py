# from django.shortcuts import render, redirect
# import json

# def carregar_dados():
#     try:
#         with open("estoque_app/data.json", "r") as f:
#             return json.load(f)
#     except:
#         return {"produtos": []}

# def salvar_dados(dados):
#     with open("estoque_app/data.json", "w") as f:
#         json.dump(dados, f, indent=4)

# def dashboard(request):
#     dados = carregar_dados()
#     return render(request, "estoque_app/dashboard.html", {"produtos": dados["produtos"]})

# def listar_produtos(request):
#     dados = carregar_dados()
#     return render(request, "estoque_app/produtos.html", {"produtos": dados["produtos"]})

# def adicionar_produto(request):
#     if request.method == "POST":
#         nome = request.POST.get("nome")
#         quantidade = request.POST.get("quantidade")

#         if not nome or not quantidade:
#             return render(request, "estoque_app/adicionar.html", {"mensagem": "Preencha todos os campos."})

#         try:
#             quantidade = int(quantidade)
#         except:
#             return render(request, "estoque_app/adicionar.html", {"mensagem": "Quantidade deve ser número."})

#         dados = carregar_dados()
#         novo_id = len(dados["produtos"]) + 1
#         dados["produtos"].append({"id": novo_id, "nome": nome, "quantidade": quantidade})
#         salvar_dados(dados)

#         return render(request, "estoque_app/adicionar.html", {"mensagem": "Produto adicionado com sucesso!"})

#     return render(request, "estoque_app/adicionar.html")

# def editar_produto(request, produto_id):
#     dados = carregar_dados()
#     produto = next((p for p in dados["produtos"] if p["id"] == produto_id), None)

#     if not produto:
#         return render(request, "estoque_app/produtos.html", {"produtos": dados["produtos"], "mensagem": "Produto não encontrado."})

#     if request.method == "POST":
#         nome = request.POST.get("nome")
#         quantidade = request.POST.get("quantidade")

#         if not nome or not quantidade:
#             return render(request, "estoque_app/editar.html", {"produto": produto, "mensagem": "Preencha todos os campos."})

#         try:
#             quantidade = int(quantidade)
#         except:
#             return render(request, "estoque_app/editar.html", {"produto": produto, "mensagem": "Quantidade deve ser número."})

#         produto["nome"] = nome
#         produto["quantidade"] = quantidade
#         salvar_dados(dados)

#         return redirect("produtos")

#     return render(request, "estoque_app/editar.html", {"produto": produto})


# def remover_produto(request, produto_id):
#     dados = carregar_dados()
#     dados["produtos"] = [p for p in dados["produtos"] if p["id"] != produto_id]
#     salvar_dados(dados)
#     return redirect("produtos")

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from .models import Produto, TipoBanho, MovimentacaoEstoque
from decimal import Decimal, InvalidOperation
# from django.shortcuts import render, redirect
import json

def validar_produto(request):
    nome = (request.POST.get("nome") or "").strip()
    preco_texto = (request.POST.get("preco") or "").strip()
    estoque_texto = (request.POST.get("quantidade") or "").strip()
    peso_texto = (request.POST.get("peso") or "").strip()

    if not nome:
        return "O nome do produto é obrigatório."

    try:
        preco = Decimal(preco_texto)
    except (InvalidOperation, ValueError):
        return "Informe um preço válido."

    if preco < 0:
        return "O preço não pode ser negativo."

    try:
        estoque = int(estoque_texto)
    except ValueError:
        return "Informe uma quantidade válida."

    if estoque < 0:
        return "A quantidade em estoque não pode ser negativa."

    if peso_texto:
        try:
            peso = Decimal(peso_texto)
        except (InvalidOperation, ValueError):
            return "Informe um peso válido."

        if peso < 0:
            return "O peso não pode ser negativo."

    return None

def obter_peso_do_formulario(request):
    """Converte o peso do formulário. Campo vazio vira None."""
    peso = request.POST.get("peso")
    if peso is None or str(peso).strip() == "":
        return None
    return peso


def obter_banho_do_formulario(request):
    """
    Obtém o TipoBanho a partir do formulário.
    Prioridade: campo "novo_banho"; senão, select de banho existente.
    """
    novo_nome = (request.POST.get("novo_banho") or "").strip()

    if novo_nome:
        banho_existente = TipoBanho.objects.filter(
            nome__iexact=novo_nome
        ).first()

        if banho_existente:
            return banho_existente

        return TipoBanho.objects.create(nome=novo_nome)

    banho_id = request.POST.get("banho")

    if banho_id:
        try:
            return TipoBanho.objects.get(id=banho_id)
        except (TipoBanho.DoesNotExist, ValueError):
            return None

    return None

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

# def listar_produtos(request):
#     dados = carregar_dados()
#     return render(request, "estoque_app/produtos.html", {"produtos": dados["produtos"]})

# def adicionar_produto(request):
#     if request.method == "POST":
#         nome = request.POST.get("nome")
#         quantidade = int(request.POST.get("quantidade"))
#         preco = float(request.POST.get("preco"))
#         imagem = request.POST.get("imagem")
#         descricao = request.POST.get("descricao")

#         dados = carregar_dados()
#         novo_id = len(dados["produtos"]) + 1
#         dados["produtos"].append({
#             "id": novo_id,
#             "nome": nome,
#             "quantidade": quantidade,
#             "preco": preco,
#             "imagem": imagem,
#             "descricao": descricao
#         })
#         salvar_dados(dados)
#         return redirect("produtos")

#     return render(request, "estoque_app/adicionar.html")

# def editar_produto(request, produto_id):
#     dados = carregar_dados()
#     produto = next((p for p in dados["produtos"] if p["id"] == produto_id), None)
#     if not produto:
#         return redirect("produtos")

#     if request.method == "POST":
#         produto["nome"] = request.POST.get("nome")
#         produto["quantidade"] = int(request.POST.get("quantidade"))
#         produto["preco"] = float(request.POST.get("preco"))
#         produto["imagem"] = request.POST.get("imagem")
#         produto["descricao"] = request.POST.get("descricao")
#         salvar_dados(dados)
#         return redirect("produtos")

#     return render(request, "estoque_app/editar.html", {"produto": produto})

# def remover_produto(request, produto_id):
#     dados = carregar_dados()
#     dados["produtos"] = [p for p in dados["produtos"] if p["id"] != produto_id]
#     salvar_dados(dados)
#     return redirect("produtos")

def listar_produtos(request):
    # select_related evita consulta extra ao mostrar o nome do banho
    produtos = Produto.objects.select_related("banho").all()
    return render(request, "estoque_app/produtos.html", {"produtos": produtos})

def adicionar_produto(request):
    if request.method == "POST":
        erro = validar_produto(request)

        if erro:
            tipos_banho = TipoBanho.objects.all().order_by("nome")

            return render(
                request,
                "estoque_app/adicionar.html",
                {
                    "tipos_banho": tipos_banho,
                    "erro": erro,
                },
            )
        Produto.objects.create(
            nome=(request.POST.get("nome") or "").strip(),
            descricao=request.POST.get("descricao"),
            preco=request.POST.get("preco"),
            estoque=request.POST.get("quantidade"),
            tipo=request.POST.get("tipo"),
            categoria=request.POST.get("categoria"),
            peso=obter_peso_do_formulario(request),
            banho=obter_banho_do_formulario(request),
        )
        return redirect("produtos")

    tipos_banho = TipoBanho.objects.all().order_by("nome")
    return render(request, "estoque_app/adicionar.html", {"tipos_banho": tipos_banho})

def editar_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)

    if request.method == "POST":
        erro = validar_produto(request)

        if erro:
            tipos_banho = TipoBanho.objects.all().order_by("nome")

            return render(
                request,
                "estoque_app/editar.html",
                {
                    "produto": produto,
                    "tipos_banho": tipos_banho,
                    "erro": erro,
                },
            )
        produto.nome = (request.POST.get("nome") or "").strip()
        produto.descricao = request.POST.get("descricao")
        produto.preco = request.POST.get("preco")
        produto.estoque = request.POST.get("quantidade")
        produto.tipo = request.POST.get("tipo")
        produto.categoria = request.POST.get("categoria")
        produto.peso = obter_peso_do_formulario(request)
        produto.banho = obter_banho_do_formulario(request)
        produto.save()
        return redirect("produtos")

    tipos_banho = TipoBanho.objects.all().order_by("nome")
    return render(
        request,
        "estoque_app/editar.html",
        {"produto": produto, "tipos_banho": tipos_banho},
    )

@require_POST
def remover_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)
    produto.delete()
    return redirect("produtos")


def validar_movimentacao(request, produto):
    """Valida tipo e quantidade da movimentação. Retorna mensagem de erro ou None."""
    tipo = (request.POST.get("tipo") or "").strip()
    quantidade_texto = (request.POST.get("quantidade") or "").strip()

    tipos_validos = [MovimentacaoEstoque.TIPO_ENTRADA, MovimentacaoEstoque.TIPO_SAIDA]
    if tipo not in tipos_validos:
        return "Selecione um tipo de movimentação válido."

    try:
        quantidade = int(quantidade_texto)
    except ValueError:
        return "Informe uma quantidade válida."

    if quantidade <= 0:
        return "A quantidade deve ser maior que zero."

    if tipo == MovimentacaoEstoque.TIPO_SAIDA and quantidade > produto.estoque:
        return "Quantidade maior que o estoque disponível."

    return None


def movimentar_estoque(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)

    if request.method == "POST":
        erro = validar_movimentacao(request, produto)

        if erro:
            return render(
                request,
                "estoque_app/movimentar.html",
                {"produto": produto, "erro": erro},
            )

        tipo = request.POST.get("tipo")
        quantidade = int(request.POST.get("quantidade"))

        if tipo == MovimentacaoEstoque.TIPO_ENTRADA:
            produto.estoque = produto.estoque + quantidade
        else:
            produto.estoque = produto.estoque - quantidade

        produto.save()

        MovimentacaoEstoque.objects.create(
            produto=produto,
            tipo=tipo,
            quantidade=quantidade,
        )

        return redirect("movimentacoes")

    return render(request, "estoque_app/movimentar.html", {"produto": produto})


def listar_movimentacoes(request):
    movimentacoes = (
        MovimentacaoEstoque.objects.select_related("produto")
        .order_by("-data")
    )
    return render(
        request,
        "estoque_app/movimentacoes.html",
        {"movimentacoes": movimentacoes},
    )
