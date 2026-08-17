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
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, IntegrityError
from django.conf import settings
from .models import Produto, TipoBanho, MovimentacaoEstoque, Pedido, ItemPedido, Usuario
from decimal import Decimal, InvalidOperation
# from django.shortcuts import render, redirect
import json
import requests

#def validar_produto(request):
#    nome = (request.POST.get("nome") or "").strip()
#    preco_texto = (request.POST.get("preco") or "").strip()
#    estoque_texto = (request.POST.get("quantidade") or "").strip()
#    peso_texto = (request.POST.get("peso") or "").strip()
#
#    if not nome:
#        return "O nome do produto é obrigatório."
#
#    try:
#        preco = Decimal(preco_texto)
#   except (InvalidOperation, ValueError):
#
#    if preco < 0:
#        return "O preço não pode ser negativo."
#
#    try:
#        estoque = int(estoque_texto)
#    except ValueError:
#        return "Informe uma quantidade válida."
#
#        return "A quantidade em estoque não pode ser negativa."
#
#    if peso_texto:
#        try:
#        except (InvalidOperation, ValueError):
#            return "Informe um peso válido."
#
#        if peso < 0:
#            return "O peso não pode ser negativo."
#
#    return None

def validar_produto(request, validar_estoque=True):
    nome = (request.POST.get("nome") or "").strip()
    preco_texto = (request.POST.get("preco") or "").strip()
    peso_texto = (request.POST.get("peso") or "").strip()

    if not nome:
        return "O nome do produto é obrigatório."

    try:
        preco = Decimal(preco_texto)
    except (InvalidOperation, ValueError):
        return "Informe um preço válido."

    if preco < 0:
        return "O preço não pode ser negativo."

    if validar_estoque:
        estoque_texto = (request.POST.get("quantidade") or "").strip()

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
            # Login válido: vai para a Página Inicial (não para o dashboard)
            return redirect("pagina_inicial")
        else:
            return render(request, "estoque_app/login.html", {"mensagem": "Usuário ou senha inválidos."})

    # Se for GET, apenas renderiza a tela de login
    return render(request, "estoque_app/login.html")


def pagina_inicial(request):
    """Tela de entrada após o login, com atalhos para os módulos."""
    return render(request, "estoque_app/pagina_inicial.html")


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
        erro = validar_produto(request, validar_estoque=False)

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

    if produto.movimentacoes.exists():
        produtos = Produto.objects.select_related("banho").all()

        return render(
            request,
            "estoque_app/produtos.html",
            {
                "produtos": produtos,
                "erro": "Não é possível excluir este produto porque ele possui movimentações de estoque.",
            },
        )

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


def listar_pedidos(request):
    """Lista os pedidos existentes."""
    pedidos = (
        Pedido.objects.select_related("usuario")
        .order_by("-data_pedido")
    )
    return render(request, "estoque_app/pedidos.html", {"pedidos": pedidos})


def criar_pedido(request):
    """Cria um pedido escolhendo apenas o cliente (status padrão do model)."""
    clientes = Usuario.objects.filter(tipo="cliente").order_by("nome")

    if request.method == "POST":
        usuario_id = request.POST.get("usuario")

        try:
            cliente = Usuario.objects.get(id=usuario_id, tipo="cliente")
        except (Usuario.DoesNotExist, ValueError, TypeError):
            return render(
                request,
                "estoque_app/novo_pedido.html",
                {
                    "clientes": clientes,
                    "erro": "Selecione um cliente válido.",
                },
            )

        pedido = Pedido.objects.create(usuario=cliente)
        return redirect("detalhe_pedido", pedido_id=pedido.id)

    return render(
        request,
        "estoque_app/novo_pedido.html",
        {"clientes": clientes},
    )


def montar_contexto_detalhe_pedido(pedido, erro=None):
    """Monta o contexto da tela de detalhe (itens, subtotais e total)."""
    itens_banco = (
        ItemPedido.objects.filter(pedido=pedido)
        .select_related("produto")
    )

    # Calcula subtotal por item e total do pedido de forma simples
    itens = []
    total = Decimal("0")

    for item in itens_banco:
        subtotal = item.quantidade * item.preco_unitario
        total = total + subtotal
        itens.append(
            {
                "produto": item.produto,
                "quantidade": item.quantidade,
                "preco_unitario": item.preco_unitario,
                "subtotal": subtotal,
            }
        )

    contexto = {
        "pedido": pedido,
        "itens": itens,
        "total": total,
    }

    if erro:
        contexto["erro"] = erro

    return contexto


def detalhe_pedido(request, pedido_id):
    """Mostra os dados de um pedido e seus itens."""
    pedido = get_object_or_404(
        Pedido.objects.select_related("usuario"),
        id=pedido_id,
    )

    return render(
        request,
        "estoque_app/detalhe_pedido.html",
        montar_contexto_detalhe_pedido(pedido),
    )


@require_POST
def finalizar_pedido(request, pedido_id):
    """
    Finaliza o pedido: pendente -> aguardando_pagamento.
    Não altera estoque nem cria movimentação.
    """
    pedido = get_object_or_404(
        Pedido.objects.select_related("usuario"),
        id=pedido_id,
    )

    if pedido.status != "pendente":
        return render(
            request,
            "estoque_app/detalhe_pedido.html",
            montar_contexto_detalhe_pedido(
                pedido,
                "Este pedido não pode mais ser finalizado.",
            ),
        )

    possui_itens = ItemPedido.objects.filter(pedido=pedido).exists()
    if not possui_itens:
        return render(
            request,
            "estoque_app/detalhe_pedido.html",
            montar_contexto_detalhe_pedido(
                pedido,
                "Não é possível finalizar um pedido sem itens.",
            ),
        )

    pedido.status = "aguardando_pagamento"
    pedido.save()

    return redirect("detalhe_pedido", pedido_id=pedido.id)


@require_POST
def confirmar_pagamento(request, pedido_id):
    """
    Confirma o pagamento: aguardando_pagamento -> pago.
    Valida estoque de todos os itens, baixa o estoque e registra saídas.
    Tudo ou nada (transaction.atomic).
    """
    pedido = get_object_or_404(
        Pedido.objects.select_related("usuario"),
        id=pedido_id,
    )

    if pedido.status != "aguardando_pagamento":
        return render(
            request,
            "estoque_app/detalhe_pedido.html",
            montar_contexto_detalhe_pedido(
                pedido,
                "Este pedido não está aguardando pagamento.",
            ),
        )

    itens = list(
        ItemPedido.objects.filter(pedido=pedido).select_related("produto")
    )

    if not itens:
        return render(
            request,
            "estoque_app/detalhe_pedido.html",
            montar_contexto_detalhe_pedido(
                pedido,
                "Não é possível confirmar pagamento de um pedido sem itens.",
            ),
        )

    # Agrupa a quantidade total necessária por produto
    # (mesmo produto em vários itens do pedido → uma única baixa)
    necessidade_por_produto = {}
    for item in itens:
        produto = item.produto
        if produto.id not in necessidade_por_produto:
            necessidade_por_produto[produto.id] = {
                "produto": produto,
                "quantidade": 0,
            }
        necessidade_por_produto[produto.id]["quantidade"] += item.quantidade

    # Etapa 1: validar estoque de TODOS os produtos (sem alterar nada)
    for dados in necessidade_por_produto.values():
        produto = dados["produto"]
        quantidade_total = dados["quantidade"]

        if quantidade_total > produto.estoque:
            return render(
                request,
                "estoque_app/detalhe_pedido.html",
                montar_contexto_detalhe_pedido(
                    pedido,
                    f"Estoque insuficiente para o produto {produto.nome}.",
                ),
            )

    # Etapa 2: aplicar alterações somente se a validação passou
    with transaction.atomic():
        # Baixa o estoque UMA vez por produto, usando a soma total
        for dados in necessidade_por_produto.values():
            produto = dados["produto"]
            produto.estoque = produto.estoque - dados["quantidade"]
            produto.save()

        # Mantém uma movimentação de saída por ItemPedido
        for item in itens:
            MovimentacaoEstoque.objects.create(
                produto=item.produto,
                tipo=MovimentacaoEstoque.TIPO_SAIDA,
                quantidade=item.quantidade,
            )

        pedido.status = "pago"
        pedido.save()

    return redirect("detalhe_pedido", pedido_id=pedido.id)


@require_POST
def cancelar_pedido(request, pedido_id):
    """
    Cancela pedido pendente ou aguardando pagamento.
    Não altera estoque nem cria movimentação (baixa só ocorre no pagamento).
    """
    pedido = get_object_or_404(
        Pedido.objects.select_related("usuario"),
        id=pedido_id,
    )

    if pedido.status == "pago":
        return render(
            request,
            "estoque_app/detalhe_pedido.html",
            montar_contexto_detalhe_pedido(
                pedido,
                "Pedido pago não pode ser cancelado por esta operação.",
            ),
        )

    if pedido.status == "cancelado":
        return render(
            request,
            "estoque_app/detalhe_pedido.html",
            montar_contexto_detalhe_pedido(
                pedido,
                "Este pedido já está cancelado.",
            ),
        )

    if pedido.status not in ("pendente", "aguardando_pagamento"):
        return render(
            request,
            "estoque_app/detalhe_pedido.html",
            montar_contexto_detalhe_pedido(
                pedido,
                "Este pedido não pode ser cancelado.",
            ),
        )

    pedido.status = "cancelado"
    pedido.save()

    return redirect("detalhe_pedido", pedido_id=pedido.id)


def adicionar_item_pedido(request, pedido_id):
    """Adiciona um item ao pedido (um por vez). Não altera o estoque do produto."""
    pedido = get_object_or_404(
        Pedido.objects.select_related("usuario"),
        id=pedido_id,
    )

    # Só pedidos pendentes podem receber itens (proteção no servidor)
    if pedido.status != "pendente":
        return render(
            request,
            "estoque_app/detalhe_pedido.html",
            montar_contexto_detalhe_pedido(
                pedido,
                "Só é possível adicionar itens a pedidos com status pendente.",
            ),
        )

    produtos = Produto.objects.all().order_by("nome")

    if request.method == "POST":
        produto_id = request.POST.get("produto")
        quantidade_texto = (request.POST.get("quantidade") or "").strip()

        try:
            produto = Produto.objects.get(id=produto_id)
        except (Produto.DoesNotExist, ValueError, TypeError):
            return render(
                request,
                "estoque_app/adicionar_item_pedido.html",
                {
                    "pedido": pedido,
                    "produtos": produtos,
                    "erro": "Selecione um produto válido.",
                },
            )

        try:
            quantidade = int(quantidade_texto)
        except ValueError:
            return render(
                request,
                "estoque_app/adicionar_item_pedido.html",
                {
                    "pedido": pedido,
                    "produtos": produtos,
                    "erro": "Informe uma quantidade válida.",
                },
            )

        if quantidade <= 0:
            return render(
                request,
                "estoque_app/adicionar_item_pedido.html",
                {
                    "pedido": pedido,
                    "produtos": produtos,
                    "erro": "A quantidade deve ser maior que zero.",
                },
            )

        if quantidade > produto.estoque:
            return render(
                request,
                "estoque_app/adicionar_item_pedido.html",
                {
                    "pedido": pedido,
                    "produtos": produtos,
                    "erro": "Quantidade maior que o estoque disponível.",
                },
            )

        # Congela o preço do produto no momento do pedido
        ItemPedido.objects.create(
            pedido=pedido,
            produto=produto,
            quantidade=quantidade,
            preco_unitario=produto.preco,
        )

        return redirect("detalhe_pedido", pedido_id=pedido.id)

    return render(
        request,
        "estoque_app/adicionar_item_pedido.html",
        {
            "pedido": pedido,
            "produtos": produtos,
        },
    )


def formatar_telefone_para_exibicao(telefone):
    """
    Formata telefone só para a tela (banco continua com dígitos).
    Padrões: 10/11 dígitos nacionais ou 12/13 com DDI 55.
    Se não casar, devolve os dígitos como estão.
    """
    if not telefone:
        return ""

    digitos = "".join(c for c in str(telefone) if c.isdigit())
    if not digitos:
        return ""

    tamanho = len(digitos)

    if tamanho == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"

    if tamanho == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"

    if tamanho == 13 and digitos.startswith("55"):
        return f"+55 ({digitos[2:4]}) {digitos[4:9]}-{digitos[9:]}"

    if tamanho == 12 and digitos.startswith("55"):
        return f"+55 ({digitos[2:4]}) {digitos[4:8]}-{digitos[8:]}"

    return digitos


def validar_telefone_cliente(request):
    """
    Valida o telefone do cliente.
    Vazio é permitido (salva como None).
    Se preenchido, normaliza para só dígitos e valida o tamanho
    (10/11 sem DDI, ou 12/13 com DDI 55). Não acrescenta 55 automaticamente.
    Retorna (telefone, mensagem_de_erro).
    """
    telefone = (request.POST.get("telefone") or "").strip()

    if not telefone:
        return None, None

    # Remove espaços, parênteses, hífen, + e demais não-dígitos; guarda só números.
    telefone = "".join(c for c in telefone if c.isdigit())

    mensagem_invalido = (
        "Informe um telefone válido, como (18) 99809-2610 ou +55 (18) 99123-4567."
    )

    if not telefone:
        return None, mensagem_invalido

    tamanho = len(telefone)
    valido_sem_ddi = tamanho in (10, 11)
    valido_com_ddi = tamanho in (12, 13) and telefone.startswith("55")

    if not (valido_sem_ddi or valido_com_ddi):
        return telefone, mensagem_invalido

    return telefone, None


def listar_clientes(request):
    """Lista usuários do tipo cliente (nome, e-mail e telefone)."""
    clientes = Usuario.objects.filter(tipo="cliente").order_by("nome")

    # Atributo só para a tela; o valor no banco permanece só com dígitos.
    for cliente in clientes:
        cliente.telefone_exibicao = formatar_telefone_para_exibicao(cliente.telefone)

    return render(request, "estoque_app/clientes.html", {"clientes": clientes})


def editar_telefone_cliente(request, cliente_id):
    """Permite editar apenas o telefone de um cliente existente."""
    cliente = get_object_or_404(Usuario, id=cliente_id, tipo="cliente")

    if request.method == "POST":
        telefone, erro = validar_telefone_cliente(request)

        if erro:
            return render(
                request,
                "estoque_app/editar_telefone_cliente.html",
                {
                    "cliente": cliente,
                    "telefone": request.POST.get("telefone", ""),
                    "erro": erro,
                },
            )

        cliente.telefone = telefone

        try:
            cliente.save()
        except IntegrityError:
            return render(
                request,
                "estoque_app/editar_telefone_cliente.html",
                {
                    "cliente": cliente,
                    "telefone": request.POST.get("telefone", ""),
                    "erro": "Este telefone já está cadastrado para outro cliente.",
                },
            )

        return redirect("clientes")

    return render(
        request,
        "estoque_app/editar_telefone_cliente.html",
        {
            "cliente": cliente,
            "telefone": formatar_telefone_para_exibicao(cliente.telefone),
        },
    )


def enviar_mensagem_waha(numero, mensagem):
    """
    Envia uma mensagem de texto pelo WAHA.
    Retorna (True, texto) em sucesso ou (False, texto) em erro.
    Não adiciona DDI 55 automaticamente.
    """
    digitos = "".join(c for c in str(numero) if c.isdigit())

    if not digitos:
        return False, "Informe um número válido."

    if not mensagem or not str(mensagem).strip():
        return False, "Informe a mensagem."

    chat_id = f"{digitos}@c.us"
    url = settings.WAHA_API_URL.rstrip("/") + "/api/sendText"

    cabecalhos = {
        "Content-Type": "application/json",
        "X-Api-Key": settings.WAHA_API_KEY,
    }
    corpo = {
        "session": settings.WAHA_SESSION,
        "chatId": chat_id,
        "text": str(mensagem).strip(),
    }

    try:
        resposta = requests.post(
            url,
            json=corpo,
            headers=cabecalhos,
            timeout=15,
        )
    except requests.exceptions.RequestException:
        return False, "Não foi possível conectar ao WAHA."

    if resposta.status_code in (200, 201):
        return True, "Mensagem enviada com sucesso pelo WAHA."

    if resposta.status_code == 401:
        return False, "Não autorizado pelo WAHA. Verifique a API Key."

    return False, f"O WAHA retornou o status {resposta.status_code}."


def teste_waha(request):
    """Tela simples para provar o envio Django → WAHA → WhatsApp."""
    contexto = {
        "numero": "",
        "mensagem": "Teste Mali Semijoias - Aula 14",
    }

    if request.method != "POST":
        return render(request, "estoque_app/teste_waha.html", contexto)

    numero = (request.POST.get("numero") or "").strip()
    mensagem = (request.POST.get("mensagem") or "").strip()
    contexto["numero"] = numero
    contexto["mensagem"] = mensagem

    if not numero:
        contexto["erro"] = "Informe o número de destino."
        return render(request, "estoque_app/teste_waha.html", contexto)

    if not mensagem:
        contexto["erro"] = "Informe a mensagem."
        return render(request, "estoque_app/teste_waha.html", contexto)

    sucesso, texto = enviar_mensagem_waha(numero, mensagem)

    if sucesso:
        contexto["sucesso"] = texto
    else:
        contexto["erro"] = texto

    return render(request, "estoque_app/teste_waha.html", contexto)


@csrf_exempt
@require_POST
def webhook_waha(request):
    """
    Receptor mínimo do WAHA.
    Só lê o JSON, imprime no terminal e responde HTTP 200.
    Não envia resposta automática.
    """
    try:
        dados = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse(
            {"status": "erro", "mensagem": "JSON inválido."},
            status=400,
        )

    if not isinstance(dados, dict):
        return JsonResponse(
            {"status": "erro", "mensagem": "JSON inválido."},
            status=400,
        )

    evento = dados.get("event")
    sessao = dados.get("session")
    payload = dados.get("payload") or {}

    if not isinstance(payload, dict):
        payload = {}

    # Outros eventos do WAHA são ignorados nesta etapa
    if evento != "message":
        return JsonResponse({"status": "ok"}, status=200)

    # Mensagem enviada pelo próprio número conectado
    if payload.get("fromMe") is True:
        return JsonResponse({"status": "ok"}, status=200)

    remetente = str(payload.get("from") or "")
    mensagem = str(payload.get("body") or "")

    # Grupo: não processar nesta versão
    if remetente.endswith("@g.us"):
        return JsonResponse({"status": "ok"}, status=200)

    # Status do WhatsApp
    if remetente == "status@broadcast":
        return JsonResponse({"status": "ok"}, status=200)

    # Canal
    if remetente.endswith("@newsletter"):
        return JsonResponse({"status": "ok"}, status=200)

    # Sem texto (mídia, figurinha, evento vazio etc.)
    if not mensagem.strip():
        return JsonResponse({"status": "ok"}, status=200)

    # @c.us: mostra só o número. @lid: mantém o identificador completo.
    if remetente.endswith("@c.us"):
        identificador_exibicao = remetente[:-len("@c.us")]
    else:
        identificador_exibicao = remetente

    print("=== MENSAGEM RECEBIDA DO WAHA ===")
    print(f"Sessão: {sessao}")
    print(f"Identificador: {identificador_exibicao}")
    print(f"Mensagem: {mensagem}")
    print("=================================")

    return JsonResponse({"status": "ok"}, status=200)
