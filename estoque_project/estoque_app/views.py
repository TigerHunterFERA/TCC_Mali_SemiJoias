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
from django.db.models import Q, Count, Sum, F, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.conf import settings
from .models import Produto, TipoBanho, MovimentacaoEstoque, Pedido, ItemPedido, Usuario
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
# from django.shortcuts import render, redirect
import json
import requests
import secrets
from urllib.parse import quote

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
    """
    Painel administrativo com indicadores reais do banco.
    Apenas consulta Produto, Pedido, ItemPedido e MovimentacaoEstoque.
    Não altera estoque, pedidos nem pagamentos.
    """
    try:
        totais_produto = Produto.objects.aggregate(
            total=Count("id"),
            estoque_baixo=Count(
                "id",
                filter=Q(estoque__gte=1, estoque__lte=5),
            ),
            sem_estoque=Count("id", filter=Q(estoque=0)),
        )

        totais_pedido = Pedido.objects.aggregate(
            total=Count("id"),
            pagos=Count("id", filter=Q(status="pago")),
            aguardando=Count("id", filter=Q(status="aguardando_pagamento")),
            pendentes=Count("id", filter=Q(status="pendente")),
            cancelados=Count("id", filter=Q(status="cancelado")),
        )

        hoje = timezone.localdate()
        pedidos_hoje = Pedido.objects.filter(data_pedido__date=hoje).count()

        receita_confirmada = ItemPedido.objects.filter(
            pedido__status="pago",
        ).aggregate(
            total=Coalesce(
                Sum(
                    F("quantidade") * F("preco_unitario"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                Decimal("0.00"),
            )
        )["total"]
        receita_exibicao = f"{receita_confirmada:.2f}".replace(".", ",")

        ultimos_pedidos = list(
            Pedido.objects.select_related("usuario")
            .prefetch_related("itempedido_set")
            .order_by("-data_pedido", "-id")[:5]
        )
        for pedido in ultimos_pedidos:
            total = Decimal("0.00")
            for item in pedido.itempedido_set.all():
                total = total + (item.quantidade * item.preco_unitario)
            pedido.total_exibicao = f"{total:.2f}".replace(".", ",")

        ultimas_movimentacoes = (
            MovimentacaoEstoque.objects.select_related("produto")
            .order_by("-data", "-id")[:5]
        )

        produtos_atencao = Produto.objects.filter(
            estoque__lte=5,
        ).order_by("estoque", "nome")[:8]

        return render(
            request,
            "estoque_app/dashboard.html",
            {
                "total_produtos": totais_produto["total"],
                "estoque_baixo": totais_produto["estoque_baixo"],
                "sem_estoque": totais_produto["sem_estoque"],
                "total_pedidos": totais_pedido["total"],
                "pedidos_pagos": totais_pedido["pagos"],
                "pedidos_aguardando": totais_pedido["aguardando"],
                "pedidos_pendentes": totais_pedido["pendentes"],
                "pedidos_cancelados": totais_pedido["cancelados"],
                "pedidos_hoje": pedidos_hoje,
                "receita_exibicao": receita_exibicao,
                "ultimos_pedidos": ultimos_pedidos,
                "ultimas_movimentacoes": ultimas_movimentacoes,
                "produtos_atencao": produtos_atencao,
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


def confirmar_pagamento_do_pedido(pedido_id):
    """
    Aplica a regra segura de pagamento: aguardando_pagamento -> pago.
    Trava Pedido e Produtos, relê status/estoque e aplica baixa,
    movimentações e status em uma única transação.
    Retorna (True, None) se confirmou, ou (False, mensagem) se recusou.
    Não verifica o dono do pedido; quem chama deve garantir isso.
    """
    with transaction.atomic():
        # Lock do Pedido: outra confirmação do mesmo pedido espera aqui.
        pedido = Pedido.objects.select_for_update().get(id=pedido_id)

        # Status relido depois do lock (protege duplo clique).
        if pedido.status != "aguardando_pagamento":
            return False, "Este pedido não está aguardando pagamento."

        itens = list(ItemPedido.objects.filter(pedido=pedido))
        if not itens:
            return False, "Não é possível confirmar pagamento de um pedido sem itens."

        # Mesmo produto em vários itens → uma única baixa consolidada.
        necessidade_por_produto = {}
        for item in itens:
            id_produto = item.produto_id
            if id_produto not in necessidade_por_produto:
                necessidade_por_produto[id_produto] = 0
            necessidade_por_produto[id_produto] += item.quantidade

        # Lock dos Produtos na mesma ordem (id) para reduzir deadlock.
        produtos_bloqueados = list(
            Produto.objects.select_for_update()
            .filter(id__in=necessidade_por_produto.keys())
            .order_by("id")
        )
        produtos_por_id = {}
        for produto in produtos_bloqueados:
            produtos_por_id[produto.id] = produto

        # Estoque relido depois do lock (protege a última unidade).
        for id_produto, quantidade_total in necessidade_por_produto.items():
            produto = produtos_por_id.get(id_produto)
            if produto is None or quantidade_total > produto.estoque:
                nome_produto = produto.nome if produto else "selecionado"
                return (
                    False,
                    f"Estoque insuficiente para o produto {nome_produto}.",
                )

        # Baixa UMA vez por produto, usando a soma total.
        for id_produto, quantidade_total in necessidade_por_produto.items():
            produto = produtos_por_id[id_produto]
            produto.estoque = produto.estoque - quantidade_total
            produto.save(update_fields=["estoque"])

        # Mantém uma movimentação de saída por ItemPedido.
        for item in itens:
            MovimentacaoEstoque.objects.create(
                produto=produtos_por_id[item.produto_id],
                tipo=MovimentacaoEstoque.TIPO_SAIDA,
                quantidade=item.quantidade,
            )

        pedido.status = "pago"
        pedido.save(update_fields=["status"])

    return True, None


@require_POST
def confirmar_pagamento(request, pedido_id):
    """
    View web: recebe o POST e mostra o detalhe do pedido.
    A regra de estoque e status fica em confirmar_pagamento_do_pedido.
    """
    get_object_or_404(Pedido, id=pedido_id)
    sucesso, mensagem = confirmar_pagamento_do_pedido(pedido_id)
    if not sucesso:
        pedido = get_object_or_404(
            Pedido.objects.select_related("usuario"),
            id=pedido_id,
        )
        return render(
            request,
            "estoque_app/detalhe_pedido.html",
            montar_contexto_detalhe_pedido(pedido, mensagem),
        )
    return redirect("detalhe_pedido", pedido_id=pedido_id)


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


def obter_telefone_waha(identificador):
    """
    Converte o identificador do WAHA em telefone (só dígitos).
    @c.us: usa o próprio identificador, sem chamar a API.
    @lid: consulta GET /api/{session}/lids/{lid}.
    Em qualquer falha, devolve None sem quebrar o webhook.
    """
    identificador = str(identificador or "").strip()

    if not identificador:
        return None

    if identificador.endswith("@c.us"):
        telefone = identificador[:-len("@c.us")]
        digitos = "".join(c for c in telefone if c.isdigit())
        if not digitos:
            return None
        return digitos

    if not identificador.endswith("@lid"):
        return None

    url = (
        settings.WAHA_API_URL.rstrip("/")
        + "/api/"
        + quote(str(settings.WAHA_SESSION), safe="")
        + "/lids/"
        + quote(identificador, safe="")
    )
    cabecalhos = {
        "X-Api-Key": settings.WAHA_API_KEY,
    }

    try:
        resposta = requests.get(url, headers=cabecalhos, timeout=15)
    except requests.exceptions.RequestException:
        print("Não foi possível consultar o LID no WAHA.")
        return None

    if resposta.status_code != 200:
        print(f"WAHA retornou status {resposta.status_code} na consulta do LID.")
        return None

    try:
        dados = resposta.json()
    except ValueError:
        print("Resposta inesperada do WAHA na consulta do LID.")
        return None

    if not isinstance(dados, dict):
        print("Resposta inesperada do WAHA na consulta do LID.")
        return None

    pn = dados.get("pn")
    if not pn:
        print("WAHA não encontrou telefone para este LID.")
        return None

    pn = str(pn)
    if pn.endswith("@c.us"):
        telefone = pn[:-len("@c.us")]
    else:
        telefone = pn

    digitos = "".join(c for c in telefone if c.isdigit())
    if not digitos:
        print("WAHA não encontrou telefone para este LID.")
        return None

    return digitos


# Estado temporário em memória (Aula 17).
# Guarda telefones que já receberam o pedido de nome.
# Se o Django reiniciar, este conjunto é perdido — esperado nesta etapa.
telefones_aguardando_nome = set()

# Estado temporário em memória (Aula 18.2).
# telefone -> lista de ids na mesma ordem do catálogo enviado.
# Se o Django reiniciar, este dicionário é perdido — esperado nesta etapa.
clientes_aguardando_produto = {}

# Estado temporário em memória (Aula 18.3).
# telefone -> id do produto selecionado, aguardando a quantidade.
# Se o Django reiniciar, este dicionário é perdido — esperado nesta etapa.
clientes_aguardando_quantidade = {}

# Estado temporário em memória (Aula 18.4).
# telefone -> {"produto_id": id, "quantidade": n}, aguardando SIM/NÃO.
# Se o Django reiniciar, este dicionário é perdido — esperado nesta etapa.
clientes_aguardando_confirmacao = {}

# Estado temporário em memória (Aula 19.2).
# telefone -> id do pedido pendente, aguardando SIM/NÃO para finalizar.
# Se o Django reiniciar, este dicionário é perdido — esperado nesta etapa.
clientes_aguardando_finalizacao = {}

# Estado temporário em memória (Bloco 21.3 — somente desenvolvimento).
# telefone -> cobrança PIX AbacatePay do pedido aguardando pagamento.
# Se o Django reiniciar, este dicionário é perdido — esperado nesta etapa.
# O webhook NÃO usa este dicionário para descobrir o Pedido pago:
# ele usa externalId no formato pedido-<id>.
cobrancas_abacatepay_whatsapp = {}


def validar_nome_whatsapp(nome):
    """
    Validação mínima do nome informado pelo WhatsApp.
    Exige nome e sobrenome, sem números e sem pontuação de pergunta/exclamação.
    """
    nome = (nome or "").strip()

    if not nome:
        return False

    if len(nome) > 100:
        return False

    if "?" in nome or "!" in nome:
        return False

    if any(caractere.isdigit() for caractere in nome):
        return False

    palavras = nome.split()
    if len(palavras) < 2:
        return False

    for palavra in palavras:
        if len(palavra) < 2:
            return False

        for caractere in palavra:
            if not (caractere.isalpha() or caractere in "-'"):
                return False

    return True


def salvar_cliente_whatsapp(nome, telefone):
    """
    Reutiliza cliente com o mesmo nome e telefone vazio,
    ou cria um novo Usuario.
    Email e senha técnicos existem só porque o model exige esses campos.
    O login atual do sistema ainda não usa a tabela usuarios.
    """
    nome = (nome or "").strip()
    if not nome:
        print("Nome informado está vazio. Cadastro não realizado.")
        return None, None

    if len(nome) > 100:
        print("Nome informado é longo demais. Cadastro não realizado.")
        return None, None

    try:
        cliente = (
            Usuario.objects.filter(nome=nome, tipo="cliente")
            .filter(Q(telefone__isnull=True) | Q(telefone=""))
            .first()
        )

        if cliente:
            cliente.telefone = telefone
            cliente.save()
            return cliente, "cliente existente atualizado"

        cliente = Usuario.objects.create(
            nome=nome,
            email=f"whatsapp_{telefone}@mali.local",
            senha="whatsapp",
            tipo="cliente",
            telefone=telefone,
        )
        return cliente, "novo cliente criado"
    except Exception:
        print("Não foi possível salvar o cliente do WhatsApp.")
        return None, None


COMANDOS_CATALOGO_WHATSAPP = {
    "produto",
    "produtos",
    "catalogo",
    "catálogo",
}

COMANDOS_PEDIDOS_WHATSAPP = {
    "pedido",
    "pedidos",
    "meu pedido",
    "meus pedidos",
}

COMANDOS_FINALIZAR_WHATSAPP = {
    "finalizar",
    "finalizar pedido",
}

COMANDOS_PAGAMENTO_WHATSAPP = {
    "pagamento",
    "pagar",
    "pix",
}

# Comando explícito de Sandbox/Dev Mode. Não passa pela IA.
COMANDO_SIMULAR_PAGAMENTO_WHATSAPP = "simular pagamento"

# Frases naturais curtas (Aula 20.2). Não substituem os comandos exatos.
FRASES_CATALOGO_WHATSAPP = {
    "quero ver os produtos",
    "quero ver as peças",
    "quero ver as pecas",
    "quais produtos vocês têm",
    "quais produtos voces tem",
    "o que vocês têm disponível",
    "o que voces tem disponivel",
    "me mostre o catálogo",
    "me mostre o catalogo",
}

FRASES_PEDIDOS_WHATSAPP = {
    "quero ver meus pedidos",
    "quais são meus pedidos",
    "quais sao meus pedidos",
    "tenho algum pedido",
    "como está meu pedido",
    "como esta meu pedido",
}

FRASES_FINALIZAR_WHATSAPP = {
    "quero finalizar meu pedido",
    "quero finalizar minha compra",
    "pode finalizar meu pedido",
    "quero fechar meu pedido",
}

FRASES_PAGAMENTO_WHATSAPP = {
    "como faço para pagar",
    "como faco para pagar",
    "qual a chave pix",
    "qual é a chave pix",
    "qual e a chave pix",
    "quero pagar meu pedido",
}


INTENCOES_WHATSAPP_PERMITIDAS = {
    "consultar_catalogo",
    "consultar_pedidos",
    "iniciar_finalizacao",
    "consultar_pagamento",
    "desconhecida",
}


def interpretar_intencao_whatsapp(mensagem):
    """
    Classifica frases naturais no contrato fechado {"intencao": ...}.
    Não acessa banco, não altera pedido/estoque e não chama WAHA.
    """
    texto = (mensagem or "").strip().lower()
    if texto.endswith("?"):
        texto = texto[:-1].strip()

    if texto in FRASES_CATALOGO_WHATSAPP:
        intencao = "consultar_catalogo"
    elif texto in FRASES_PEDIDOS_WHATSAPP:
        intencao = "consultar_pedidos"
    elif texto in FRASES_FINALIZAR_WHATSAPP:
        intencao = "iniciar_finalizacao"
    elif texto in FRASES_PAGAMENTO_WHATSAPP:
        intencao = "consultar_pagamento"
    else:
        intencao = "desconhecida"

    return {"intencao": intencao}


def validar_resultado_interpretacao_whatsapp(resultado):
    """
    Aceita só o contrato fechado: uma intenção permitida.
    Formato inválido ou intenção fora da lista vira desconhecida.
    Campos extras (pedido_id, acao etc.) são ignorados.
    """
    if not isinstance(resultado, dict):
        return {"intencao": "desconhecida"}

    intencao = resultado.get("intencao")
    if not isinstance(intencao, str):
        return {"intencao": "desconhecida"}

    if intencao not in INTENCOES_WHATSAPP_PERMITIDAS:
        return {"intencao": "desconhecida"}

    return {"intencao": intencao}


def montar_catalogo_whatsapp():
    """
    Consulta produtos com estoque maior que zero e monta o texto do catálogo.
    Retorna (texto, acao, ids) para o webhook enviar pelo WhatsApp.
    Os ids ficam na mesma ordem da lista numerada.
    Não altera o estoque nem o preço armazenado no banco.
    """
    produtos = list(
        Produto.objects.filter(estoque__gt=0).order_by("nome")
    )

    if not produtos:
        return (
            "No momento não temos produtos disponíveis em estoque.",
            "catálogo vazio",
            [],
        )

    linhas = ["Produtos disponíveis:", ""]
    ids = []

    for indice, produto in enumerate(produtos, start=1):
        preco_texto = f"{produto.preco:.2f}".replace(".", ",")
        linhas.append(f"{indice}. {produto.nome}")
        linhas.append(f"Preço: R$ {preco_texto}")
        linhas.append(f"Estoque: {produto.estoque}")
        linhas.append("")
        ids.append(produto.id)

    linhas.append("Envie o número do produto que deseja conhecer melhor.")

    return "\n".join(linhas).strip(), "catálogo enviado", ids


def montar_pedidos_whatsapp(cliente):
    """
    Consulta somente os pedidos do cliente identificado.
    Total usa quantidade * preco_unitario de cada ItemPedido.
    Somente leitura: não cria pedido nem altera estoque.
    """
    pedidos = list(
        Pedido.objects.filter(usuario=cliente)
        .order_by("-data_pedido")[:5]
    )

    if not pedidos:
        return (
            "Você ainda não possui pedidos cadastrados.",
            "pedidos vazios",
        )

    linhas = ["Meus pedidos:", ""]

    for pedido in pedidos:
        itens = ItemPedido.objects.filter(pedido=pedido)
        total = Decimal("0")
        for item in itens:
            total = total + (item.quantidade * item.preco_unitario)

        total_texto = f"{total:.2f}".replace(".", ",")
        data_texto = pedido.data_pedido.strftime("%d/%m/%Y")
        linhas.append(f"Pedido #{pedido.id}")
        linhas.append(f"Status: {pedido.get_status_display()}")
        linhas.append(f"Data: {data_texto}")
        linhas.append(f"Total: R$ {total_texto}")
        linhas.append("")

    return "\n".join(linhas).strip(), "pedidos enviados"


def calcular_total_pedido(pedido):
    """Soma quantidade * preco_unitario dos itens. Não usa Produto.preco."""
    total = Decimal("0")
    itens = ItemPedido.objects.filter(pedido=pedido)
    for item in itens:
        total = total + (item.quantidade * item.preco_unitario)
    return total


def converter_reais_para_centavos(valor):
    """
    Converte Decimal em reais para inteiro em centavos.
    Não usa float. Valor <= 0 devolve None.
    """
    if valor is None:
        return None
    if not isinstance(valor, Decimal):
        try:
            valor = Decimal(str(valor))
        except (InvalidOperation, ValueError, TypeError):
            return None
    if valor <= 0:
        return None
    centavos = (valor * Decimal("100")).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    return int(centavos)


def montar_resultado_pix_falha(mensagem_erro=None):
    return {
        "sucesso": False,
        "charge_id": None,
        "br_code": None,
        "dev_mode": None,
        "status": None,
        "expires_at": None,
        "erro": mensagem_erro or "Não foi possível gerar o pagamento PIX agora.",
    }


def criar_cobranca_pix_abacatepay(pedido):
    """
    Cria cobrança PIX na AbacatePay para um Pedido aguardando pagamento.
    Não altera status, estoque nem movimentação.
    """
    if pedido is None or pedido.status != "aguardando_pagamento":
        return montar_resultado_pix_falha()

    chave = (settings.ABACATEPAY_API_KEY or "").strip()
    if not chave:
        print("=== ABACATEPAY PIX ===")
        print(f"Pedido: {pedido.id}")
        print("Cobrança criada: não")
        print("======================")
        return montar_resultado_pix_falha()

    centavos = converter_reais_para_centavos(calcular_total_pedido(pedido))
    if centavos is None:
        print("=== ABACATEPAY PIX ===")
        print(f"Pedido: {pedido.id}")
        print("Cobrança criada: não")
        print("======================")
        return montar_resultado_pix_falha()

    url = settings.ABACATEPAY_API_URL.rstrip("/") + "/v2/transparents/create"
    cabecalhos = {
        "Authorization": "Bearer " + chave,
        "Content-Type": "application/json",
    }
    corpo = {
        "method": "PIX",
        "data": {
            "amount": centavos,
            "expiresIn": 3600,
            "description": f"Pedido #{pedido.id} - Mali Semijoias",
            "externalId": f"pedido-{pedido.id}",
            "metadata": {
                "pedido_id": pedido.id,
            },
        },
    }

    try:
        resposta = requests.post(
            url,
            json=corpo,
            headers=cabecalhos,
            timeout=15,
        )
    except requests.exceptions.RequestException:
        print("=== ABACATEPAY PIX ===")
        print(f"Pedido: {pedido.id}")
        print("Cobrança criada: não")
        print("======================")
        return montar_resultado_pix_falha()

    if resposta.status_code not in (200, 201):
        print("=== ABACATEPAY PIX ===")
        print(f"Pedido: {pedido.id}")
        print("Cobrança criada: não")
        print("======================")
        return montar_resultado_pix_falha()

    try:
        dados = resposta.json()
    except ValueError:
        print("=== ABACATEPAY PIX ===")
        print(f"Pedido: {pedido.id}")
        print("Cobrança criada: não")
        print("======================")
        return montar_resultado_pix_falha()

    if not isinstance(dados, dict):
        print("=== ABACATEPAY PIX ===")
        print(f"Pedido: {pedido.id}")
        print("Cobrança criada: não")
        print("======================")
        return montar_resultado_pix_falha()

    dados_cobranca = dados.get("data")
    if not isinstance(dados_cobranca, dict):
        print("=== ABACATEPAY PIX ===")
        print(f"Pedido: {pedido.id}")
        print("Cobrança criada: não")
        print("======================")
        return montar_resultado_pix_falha()

    charge_id = dados_cobranca.get("id")
    br_code = dados_cobranca.get("brCode")
    if not charge_id or not br_code:
        print("=== ABACATEPAY PIX ===")
        print(f"Pedido: {pedido.id}")
        print("Cobrança criada: não")
        print("======================")
        return montar_resultado_pix_falha()

    status_cobranca = dados_cobranca.get("status")
    dev_mode = dados_cobranca.get("devMode")
    print("=== ABACATEPAY PIX ===")
    print(f"Pedido: {pedido.id}")
    print(f"Status: {status_cobranca}")
    print(f"Dev mode: {dev_mode}")
    print("Cobrança criada: sim")
    print("======================")

    return {
        "sucesso": True,
        "charge_id": charge_id,
        "br_code": br_code,
        "dev_mode": bool(dev_mode),
        "status": status_cobranca,
        "expires_at": dados_cobranca.get("expiresAt"),
        "erro": None,
    }


def obter_cobranca_temporaria_whatsapp(telefone, pedido_id):
    """Devolve a cobrança em memória só se for do mesmo pedido e tiver PIX."""
    cobranca = cobrancas_abacatepay_whatsapp.get(telefone)
    if not cobranca:
        return None
    if cobranca.get("pedido_id") != pedido_id:
        return None
    if not cobranca.get("charge_id") or not cobranca.get("br_code"):
        return None
    return cobranca


def guardar_cobranca_temporaria_whatsapp(telefone, pedido_id, resultado):
    """Guarda a cobrança só para reexibir o PIX e para o comando de simulação."""
    if not telefone or not resultado or not resultado.get("sucesso"):
        return
    cobrancas_abacatepay_whatsapp[telefone] = {
        "pedido_id": pedido_id,
        "charge_id": resultado["charge_id"],
        "br_code": resultado["br_code"],
        "dev_mode": bool(resultado.get("dev_mode")),
    }


def limpar_cobranca_temporaria_whatsapp(telefone, pedido_id):
    cobranca = cobrancas_abacatepay_whatsapp.get(telefone)
    if cobranca and cobranca.get("pedido_id") == pedido_id:
        cobrancas_abacatepay_whatsapp.pop(telefone, None)


def montar_bloco_pix_whatsapp(pedido, br_code, dev_mode, titulo=None):
    """Monta o texto do PIX para o WhatsApp. Não baixa estoque."""
    total_texto = f"{calcular_total_pedido(pedido):.2f}".replace(".", ",")
    linhas = []
    if titulo:
        linhas.append(titulo)
        linhas.append("")
    linhas.extend(
        [
            f"Pedido #{pedido.id}",
            f"Status: {pedido.get_status_display()}",
            f"Total: R$ {total_texto}",
            "",
            "Pagamento via PIX",
            "",
            "PIX copia e cola:",
            "",
            br_code,
            "",
            "Após o pagamento, a confirmação será automática.",
        ]
    )
    if dev_mode:
        linhas.extend(
            [
                "",
                "Ambiente de desenvolvimento.",
                'Envie "simular pagamento" para simular a quitação.',
            ]
        )
    return "\n".join(linhas)


def simular_pagamento_abacatepay(charge_id):
    """
    Pede à AbacatePay para simular o pagamento no Dev Mode.
    Não confirma o Pedido e não altera estoque.
    """
    chave = (settings.ABACATEPAY_API_KEY or "").strip()
    if not chave or not charge_id:
        return False, "Não foi possível simular o pagamento agora."

    url = (
        settings.ABACATEPAY_API_URL.rstrip("/")
        + "/v2/transparents/simulate-payment"
    )
    cabecalhos = {
        "Authorization": "Bearer " + chave,
    }

    try:
        resposta = requests.post(
            url,
            params={"id": charge_id},
            headers=cabecalhos,
            timeout=15,
        )
    except requests.exceptions.RequestException:
        return False, "Não foi possível simular o pagamento agora."

    if resposta.status_code not in (200, 201):
        return False, "Não foi possível simular o pagamento agora."

    return True, "Simulação enviada. Aguarde a confirmação automática."


def interpretar_simulacao_pagamento_whatsapp(telefone):
    """
    Comando Dev Mode: simular pagamento.
    Só chama a API da AbacatePay. Não chama confirmar_pagamento_do_pedido.
    """
    cobranca = cobrancas_abacatepay_whatsapp.get(telefone)
    if not cobranca or not cobranca.get("charge_id"):
        return (
            "Não encontrei uma cobrança em aberto para simular.",
            "simulação indisponível",
        )

    if cobranca.get("dev_mode") is not True:
        return (
            "Esta operação está disponível somente no ambiente de desenvolvimento.",
            "simulação fora de dev",
        )

    sucesso, texto = simular_pagamento_abacatepay(cobranca["charge_id"])
    if sucesso:
        return texto, "simulação enviada"
    return texto, "erro na simulação"


def extrair_pedido_id_do_external_id(external_id):
    """Aceita somente o formato exato pedido-<numero>."""
    texto = str(external_id or "").strip()
    prefixo = "pedido-"
    if not texto.startswith(prefixo):
        return None
    resto = texto[len(prefixo):]
    if not resto.isdigit():
        return None
    return int(resto)


def valores_em_centavos_iguais(valor_api, esperado):
    try:
        return int(valor_api) == int(esperado)
    except (TypeError, ValueError):
        return False


def iniciar_finalizacao_whatsapp(cliente):
    """
    Localiza o pedido pendente mais recente do próprio cliente
    e monta o pedido de confirmação. Não altera o banco.
    """
    pedido = (
        Pedido.objects.filter(usuario=cliente, status="pendente")
        .order_by("-data_pedido")
        .first()
    )
    if not pedido or not ItemPedido.objects.filter(pedido=pedido).exists():
        return (
            "Você não possui pedido pendente para finalizar.",
            "sem pedido pendente",
            None,
        )

    total_texto = f"{calcular_total_pedido(pedido):.2f}".replace(".", ",")
    texto = (
        f"Pedido #{pedido.id}\n"
        f"Total: R$ {total_texto}\n"
        f"Status atual: {pedido.get_status_display()}\n"
        "\n"
        "Deseja finalizar este pedido para pagamento?\n"
        "Responda SIM ou NÃO."
    )
    return texto, "aguardando finalização", pedido.id


def interpretar_finalizacao_whatsapp(mensagem, pedido_id, cliente):
    """
    Interpreta SIM ou NÃO da finalização.
    Altera somente o status, como a tela web.
    Não baixa estoque nem cria movimentação.
    Depois do SIM, tenta gerar o PIX na AbacatePay.
    """
    mensagem = (mensagem or "").strip().lower()

    if mensagem in ("nao", "não"):
        return (
            "Finalização cancelada. Seu pedido continua pendente.",
            "finalização cancelada",
            None,
        )

    if mensagem != "sim":
        return (
            "Resposta inválida. Responda SIM ou NÃO.",
            "finalização inválida",
            None,
        )

    pedido = Pedido.objects.filter(id=pedido_id, usuario=cliente).first()
    if (
        not pedido
        or pedido.status != "pendente"
        or not ItemPedido.objects.filter(pedido=pedido).exists()
    ):
        return (
            "Este pedido não está mais disponível para finalização.",
            "pedido indisponível para finalização",
            None,
        )

    pedido.status = "aguardando_pagamento"
    pedido.save(update_fields=["status"])

    resultado = criar_cobranca_pix_abacatepay(pedido)
    if resultado["sucesso"]:
        guardar_cobranca_temporaria_whatsapp(
            cliente.telefone,
            pedido.id,
            resultado,
        )
        texto = montar_bloco_pix_whatsapp(
            pedido,
            resultado["br_code"],
            resultado["dev_mode"],
            titulo=f"Pedido #{pedido.id} finalizado com sucesso.",
        )
        return texto, "pedido aguardando pagamento", pedido.id

    total_texto = f"{calcular_total_pedido(pedido):.2f}".replace(".", ",")
    texto = (
        f"Pedido #{pedido.id} finalizado com sucesso.\n"
        "\n"
        f"Status: {pedido.get_status_display()}\n"
        f"Total: R$ {total_texto}\n"
        "\n"
        "Não foi possível gerar o pagamento PIX agora.\n"
        'Tente enviar "pix" em alguns instantes.'
    )
    return texto, "pedido aguardando pagamento", pedido.id


def montar_instrucoes_pagamento_whatsapp(cliente):
    """
    Envia o PIX do pedido aguardando pagamento mais recente.
    Reaproveita a cobrança em memória quando ainda é do mesmo pedido.
    Não altera status, estoque nem movimentação.
    """
    pedido = (
        Pedido.objects.filter(
            usuario=cliente,
            status="aguardando_pagamento",
        )
        .order_by("-data_pedido")
        .first()
    )
    if not pedido:
        return (
            "Você não possui pedido aguardando pagamento.",
            "pagamento não disponível",
            None,
        )

    cobranca = obter_cobranca_temporaria_whatsapp(cliente.telefone, pedido.id)
    if cobranca:
        texto = montar_bloco_pix_whatsapp(
            pedido,
            cobranca["br_code"],
            cobranca.get("dev_mode"),
        )
        return texto, "instruções de pagamento enviadas", pedido.id

    resultado = criar_cobranca_pix_abacatepay(pedido)
    if not resultado["sucesso"]:
        return (
            "Não foi possível gerar o pagamento PIX agora. Tente novamente em alguns instantes.",
            "pagamento não gerado",
            pedido.id,
        )

    guardar_cobranca_temporaria_whatsapp(
        cliente.telefone,
        pedido.id,
        resultado,
    )
    texto = montar_bloco_pix_whatsapp(
        pedido,
        resultado["br_code"],
        resultado["dev_mode"],
    )
    return texto, "instruções de pagamento enviadas", pedido.id


def interpretar_selecao_produto_whatsapp(mensagem, ids_produtos):
    """
    Interpreta o número enviado pelo cliente.
    ids_produtos é a lista de ids na mesma ordem do catálogo exibido.
    Retorna (texto, acao, nome_produto, produto_id).
    """
    texto_invalido = (
        "Opção inválida. Envie o número de um produto exibido no catálogo.",
        "seleção de produto inválida",
        None,
        None,
    )
    mensagem = (mensagem or "").strip()

    if not mensagem.isdigit():
        return texto_invalido

    numero = int(mensagem)
    if numero < 1 or numero > len(ids_produtos):
        return texto_invalido

    produto_id = ids_produtos[numero - 1]
    produto = Produto.objects.filter(id=produto_id, estoque__gt=0).first()
    if not produto:
        return texto_invalido

    preco_texto = f"{produto.preco:.2f}".replace(".", ",")
    texto = (
        "Produto selecionado:\n"
        "\n"
        f"{produto.nome}\n"
        f"Preço: R$ {preco_texto}\n"
        f"Estoque disponível: {produto.estoque}\n"
        "\n"
        "Quantas unidades você deseja?"
    )
    return texto, "produto selecionado", produto.nome, produto.id


def interpretar_quantidade_whatsapp(mensagem, produto_id):
    """
    Interpreta a quantidade informada pelo cliente.
    Busca o produto novamente e não altera o banco.
    Retorna (texto, acao, nome_produto, quantidade).
    """
    produto = Produto.objects.filter(id=produto_id).first()
    if not produto or produto.estoque <= 0:
        return (
            "O produto selecionado não está mais disponível. "
            "Envie 'produtos' para consultar o catálogo novamente.",
            "produto indisponível",
            None,
            None,
        )

    mensagem = (mensagem or "").strip()
    texto_invalido = (
        f"Quantidade inválida. Informe um número entre 1 e {produto.estoque}.",
        "quantidade inválida",
        None,
        None,
    )

    if not mensagem.isdigit():
        return texto_invalido

    quantidade = int(mensagem)
    if quantidade < 1 or quantidade > produto.estoque:
        return texto_invalido

    preco_texto = f"{produto.preco:.2f}".replace(".", ",")
    subtotal = produto.preco * quantidade
    subtotal_texto = f"{subtotal:.2f}".replace(".", ",")
    texto = (
        "Resumo da compra:\n"
        "\n"
        f"Produto: {produto.nome}\n"
        f"Quantidade: {quantidade}\n"
        f"Valor unitário: R$ {preco_texto}\n"
        f"Total: R$ {subtotal_texto}\n"
        "\n"
        "Deseja confirmar o pedido?\n"
        "Responda SIM ou NÃO."
    )
    return texto, "quantidade registrada", produto.nome, quantidade


def interpretar_confirmacao_whatsapp(mensagem, dados, cliente):
    """
    Interpreta SIM ou NÃO.
    No SIM, cria Pedido e ItemPedido sem baixar estoque
    (a baixa no sistema web ocorre somente no pagamento).
    Retorna (texto, acao, pedido_id, nome_produto, quantidade).
    """
    mensagem = (mensagem or "").strip().lower()

    if mensagem in ("nao", "não"):
        return (
            "Pedido cancelado. Envie 'produtos' para consultar o catálogo novamente.",
            "confirmação cancelada",
            None,
            None,
            None,
        )

    if mensagem != "sim":
        return (
            "Confirmação inválida. Responda SIM ou NÃO.",
            "confirmação inválida",
            None,
            None,
            None,
        )

    return criar_pedido_whatsapp(
        cliente,
        dados.get("produto_id"),
        dados.get("quantidade"),
    )


def criar_pedido_whatsapp(cliente, produto_id, quantidade):
    """
    Cria Pedido + ItemPedido em uma transação.
    Status inicial: pendente (mesmo padrão da tela web).
    Não baixa estoque nem cria MovimentacaoEstoque.
    """
    try:
        with transaction.atomic():
            produto = Produto.objects.filter(id=produto_id).first()
            if not produto or produto.estoque < quantidade:
                return (
                    "O produto não está mais disponível na quantidade solicitada. "
                    "Envie 'produtos' para consultar o catálogo novamente.",
                    "produto indisponível",
                    None,
                    None,
                    None,
                )

            pedido = Pedido.objects.create(usuario=cliente)
            ItemPedido.objects.create(
                pedido=pedido,
                produto=produto,
                quantidade=quantidade,
                preco_unitario=produto.preco,
            )

            total = produto.preco * quantidade
            total_texto = f"{total:.2f}".replace(".", ",")
            texto = (
                "Pedido realizado com sucesso!\n"
                "\n"
                f"Número do pedido: {pedido.id}\n"
                f"Produto: {produto.nome}\n"
                f"Quantidade: {quantidade}\n"
                f"Total: R$ {total_texto}\n"
                "\n"
                "Acompanhe seu pedido conosco pelo WhatsApp."
            )
            return (
                texto,
                "pedido criado",
                pedido.id,
                produto.nome,
                quantidade,
            )
    except Exception:
        print("Não foi possível criar o pedido do WhatsApp.")
        return (
            "Não foi possível criar seu pedido agora. Tente novamente em alguns instantes.",
            "erro ao criar pedido",
            None,
            None,
            None,
        )


@csrf_exempt
@require_POST
def webhook_waha(request):
    """
    Receptor do WAHA.
    Lê o JSON, identifica o cliente pelo telefone e responde de forma simples.
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

    telefone = obter_telefone_waha(remetente)
    cliente = None
    resposta_exibicao = "não enviada"
    acao_exibicao = None
    texto_resposta = None
    nome_informado = None
    produto_exibicao = None
    quantidade_exibicao = None
    pedido_exibicao = None

    if telefone:
        telefone_exibicao = telefone
        cliente = Usuario.objects.filter(
            telefone=telefone,
            tipo="cliente",
        ).first()
        if cliente:
            cliente_exibicao = cliente.nome
            mensagem_normalizada = mensagem.strip().lower()
            # Novo catálogo cancela quantidade/confirmação/finalização e substitui a lista.
            if mensagem_normalizada in COMANDOS_CATALOGO_WHATSAPP:
                clientes_aguardando_quantidade.pop(telefone, None)
                clientes_aguardando_confirmacao.pop(telefone, None)
                clientes_aguardando_finalizacao.pop(telefone, None)
                texto_resposta, acao_exibicao, ids_catalogo = (
                    montar_catalogo_whatsapp()
                )
                if ids_catalogo:
                    clientes_aguardando_produto[telefone] = ids_catalogo
                else:
                    clientes_aguardando_produto.pop(telefone, None)
            elif telefone in clientes_aguardando_confirmacao:
                dados_confirmacao = clientes_aguardando_confirmacao[telefone]
                (
                    texto_resposta,
                    acao_exibicao,
                    pedido_exibicao,
                    produto_exibicao,
                    quantidade_exibicao,
                ) = interpretar_confirmacao_whatsapp(
                    mensagem,
                    dados_confirmacao,
                    cliente,
                )
                if acao_exibicao in (
                    "confirmação cancelada",
                    "produto indisponível",
                    "pedido criado",
                ):
                    clientes_aguardando_confirmacao.pop(telefone, None)
            elif telefone in clientes_aguardando_quantidade:
                produto_id = clientes_aguardando_quantidade[telefone]
                (
                    texto_resposta,
                    acao_exibicao,
                    produto_exibicao,
                    quantidade_exibicao,
                ) = interpretar_quantidade_whatsapp(mensagem, produto_id)
                if acao_exibicao == "quantidade registrada":
                    clientes_aguardando_quantidade.pop(telefone, None)
                    clientes_aguardando_confirmacao[telefone] = {
                        "produto_id": produto_id,
                        "quantidade": quantidade_exibicao,
                    }
                elif acao_exibicao == "produto indisponível":
                    clientes_aguardando_quantidade.pop(telefone, None)
            elif telefone in clientes_aguardando_produto:
                ids_catalogo = clientes_aguardando_produto[telefone]
                (
                    texto_resposta,
                    acao_exibicao,
                    produto_exibicao,
                    produto_id_selecionado,
                ) = interpretar_selecao_produto_whatsapp(
                    mensagem,
                    ids_catalogo,
                )
                if acao_exibicao == "produto selecionado":
                    clientes_aguardando_produto.pop(telefone, None)
                    clientes_aguardando_quantidade[telefone] = (
                        produto_id_selecionado
                    )
            elif telefone in clientes_aguardando_finalizacao:
                pedido_id_finalizacao = clientes_aguardando_finalizacao[telefone]
                (
                    texto_resposta,
                    acao_exibicao,
                    pedido_exibicao,
                ) = interpretar_finalizacao_whatsapp(
                    mensagem,
                    pedido_id_finalizacao,
                    cliente,
                )
                if acao_exibicao in (
                    "finalização cancelada",
                    "pedido aguardando pagamento",
                    "pedido indisponível para finalização",
                ):
                    clientes_aguardando_finalizacao.pop(telefone, None)
            elif mensagem_normalizada in COMANDOS_PEDIDOS_WHATSAPP:
                texto_resposta, acao_exibicao = montar_pedidos_whatsapp(cliente)
            elif mensagem_normalizada in COMANDOS_FINALIZAR_WHATSAPP:
                texto_resposta, acao_exibicao, pedido_id_finalizacao = (
                    iniciar_finalizacao_whatsapp(cliente)
                )
                if pedido_id_finalizacao:
                    clientes_aguardando_finalizacao[telefone] = (
                        pedido_id_finalizacao
                    )
                pedido_exibicao = pedido_id_finalizacao
            elif mensagem_normalizada in COMANDOS_PAGAMENTO_WHATSAPP:
                texto_resposta, acao_exibicao, pedido_exibicao = (
                    montar_instrucoes_pagamento_whatsapp(cliente)
                )
            elif mensagem_normalizada == COMANDO_SIMULAR_PAGAMENTO_WHATSAPP:
                texto_resposta, acao_exibicao = (
                    interpretar_simulacao_pagamento_whatsapp(telefone)
                )
            else:
                resultado = interpretar_intencao_whatsapp(mensagem)
                resultado = validar_resultado_interpretacao_whatsapp(resultado)
                intencao = resultado["intencao"]
                if intencao == "consultar_catalogo":
                    texto_resposta, acao_exibicao, ids_catalogo = (
                        montar_catalogo_whatsapp()
                    )
                    if ids_catalogo:
                        clientes_aguardando_produto[telefone] = ids_catalogo
                    else:
                        clientes_aguardando_produto.pop(telefone, None)
                elif intencao == "consultar_pedidos":
                    texto_resposta, acao_exibicao = montar_pedidos_whatsapp(
                        cliente
                    )
                elif intencao == "iniciar_finalizacao":
                    texto_resposta, acao_exibicao, pedido_id_finalizacao = (
                        iniciar_finalizacao_whatsapp(cliente)
                    )
                    if pedido_id_finalizacao:
                        clientes_aguardando_finalizacao[telefone] = (
                            pedido_id_finalizacao
                        )
                    pedido_exibicao = pedido_id_finalizacao
                elif intencao == "consultar_pagamento":
                    texto_resposta, acao_exibicao, pedido_exibicao = (
                        montar_instrucoes_pagamento_whatsapp(cliente)
                    )
                else:
                    texto_resposta = (
                        f"Olá, {cliente.nome}! Bem-vindo à Mali Semijoias."
                    )
        elif telefone in telefones_aguardando_nome:
            nome_informado = mensagem.strip()
            if not validar_nome_whatsapp(nome_informado):
                cliente_exibicao = "não identificado"
                acao_exibicao = "nome inválido"
                texto_resposta = (
                    "Não consegui identificar um nome válido. "
                    "Por favor, informe seu nome e sobrenome."
                )
            else:
                cliente, acao_exibicao = salvar_cliente_whatsapp(
                    nome_informado,
                    telefone,
                )
                if cliente:
                    telefones_aguardando_nome.discard(telefone)
                    cliente_exibicao = cliente.nome
                    texto_resposta = (
                        f"Cadastro concluído, {cliente.nome}! "
                        "Bem-vindo à Mali Semijoias."
                    )
                else:
                    cliente_exibicao = "não identificado"
        else:
            cliente_exibicao = "não identificado"
            telefones_aguardando_nome.add(telefone)
            acao_exibicao = "solicitando nome"
            texto_resposta = (
                "Olá! Não encontrei seu cadastro. Qual é o seu nome?"
            )
    else:
        telefone_exibicao = "não identificado"
        cliente_exibicao = "não identificado"

    if texto_resposta:
        sucesso_envio, _ = enviar_mensagem_waha(telefone, texto_resposta)
        if sucesso_envio:
            resposta_exibicao = "enviada"
        else:
            print("Não foi possível enviar a resposta automática pelo WAHA.")

    print("=== MENSAGEM RECEBIDA DO WAHA ===")
    print(f"Sessão: {sessao}")
    print(f"Identificador: {identificador_exibicao}")
    print(f"Telefone: {telefone_exibicao}")
    print(f"Cliente: {cliente_exibicao}")
    print(f"Mensagem: {mensagem}")
    if acao_exibicao:
        print(f"Ação: {acao_exibicao}")
    if nome_informado:
        print(f"Nome informado: {nome_informado}")
    if produto_exibicao:
        print(f"Produto: {produto_exibicao}")
    if quantidade_exibicao is not None:
        print(f"Quantidade: {quantidade_exibicao}")
    if pedido_exibicao:
        print(f"Pedido: {pedido_exibicao}")
    print(f"Resposta automática: {resposta_exibicao}")
    print("=================================")

    return JsonResponse({"status": "ok"}, status=200)


def secret_webhook_abacatepay_valido(request):
    """
    Bloco DEV/local: autenticação por webhookSecret na query string.
    Em produção pública, complementar com HMAC conforme a documentação da AbacatePay.
    """
    secret_esperado = settings.ABACATEPAY_WEBHOOK_SECRET or ""
    secret_recebido = request.GET.get("webhookSecret") or ""
    if not secret_esperado:
        return False
    try:
        return secrets.compare_digest(secret_recebido, secret_esperado)
    except (TypeError, ValueError):
        return False


@csrf_exempt
@require_POST
def webhook_abacatepay(request):
    """
    Receptor da AbacatePay.
    Confirma o Pedido somente com confirmar_pagamento_do_pedido.
    Não baixa estoque por conta própria.
    """
    if not secret_webhook_abacatepay_valido(request):
        return JsonResponse(
            {"status": "erro", "mensagem": "Não autorizado."},
            status=401,
        )

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

    evento = dados.get("event") or dados.get("type")
    if evento != "transparent.completed":
        return JsonResponse({"status": "ok", "mensagem": "Evento ignorado."})

    payload = dados.get("data") or {}
    if not isinstance(payload, dict):
        payload = {}
    transparent = payload.get("transparent")
    if not isinstance(transparent, dict):
        print("=== PAGAMENTO ABACATEPAY ===")
        print(f"Evento: {evento}")
        print("Pagamento processado: não")
        print("===========================")
        return JsonResponse(
            {"status": "erro", "mensagem": "Payload inválido."},
            status=400,
        )

    status_pagamento = transparent.get("status")
    print("=== PAGAMENTO ABACATEPAY ===")
    print(f"Evento: {evento}")
    print(f"Status: {status_pagamento}")

    if status_pagamento != "PAID":
        print("Pagamento processado: não")
        print("===========================")
        return JsonResponse(
            {"status": "erro", "mensagem": "Pagamento não está PAID."},
            status=400,
        )

    pedido_id = extrair_pedido_id_do_external_id(transparent.get("externalId"))
    if pedido_id is None:
        print("Pagamento processado: não")
        print("===========================")
        return JsonResponse(
            {"status": "erro", "mensagem": "externalId inválido."},
            status=400,
        )

    print(f"Pedido: {pedido_id}")

    pedido = (
        Pedido.objects.select_related("usuario")
        .filter(id=pedido_id)
        .first()
    )
    if pedido is None:
        print("Pagamento processado: não")
        print("===========================")
        return JsonResponse(
            {"status": "erro", "mensagem": "Pedido não encontrado."},
            status=404,
        )

    if pedido.status == "pago":
        print("Pagamento processado: já processado")
        print("===========================")
        return JsonResponse(
            {"status": "ok", "mensagem": "Evento já processado."}
        )

    if pedido.status != "aguardando_pagamento":
        print("Pagamento processado: não")
        print("===========================")
        return JsonResponse(
            {"status": "erro", "mensagem": "Pedido não está aguardando pagamento."},
            status=400,
        )

    esperado_centavos = converter_reais_para_centavos(
        calcular_total_pedido(pedido)
    )
    paid_amount = transparent.get("paidAmount")
    amount = transparent.get("amount")
    dev_mode = (
        transparent.get("devMode") is True
        or dados.get("devMode") is True
    )

    # amount sempre precisa bater com o total do Pedido.
    if esperado_centavos is None or not valores_em_centavos_iguais(
        amount,
        esperado_centavos,
    ):
        print("Pagamento processado: não")
        print("===========================")
        return JsonResponse(
            {"status": "erro", "mensagem": "Valor pago diferente do pedido."},
            status=400,
        )

    # Sandbox real pode enviar paidAmount=null. Só aceitamos isso em Dev Mode.
    if paid_amount is None:
        if not dev_mode:
            print("Pagamento processado: não")
            print("===========================")
            return JsonResponse(
                {"status": "erro", "mensagem": "Valor pago diferente do pedido."},
                status=400,
            )
    elif not valores_em_centavos_iguais(paid_amount, esperado_centavos):
        print("Pagamento processado: não")
        print("===========================")
        return JsonResponse(
            {"status": "erro", "mensagem": "Valor pago diferente do pedido."},
            status=400,
        )

    sucesso, _mensagem = confirmar_pagamento_do_pedido(pedido.id)
    if not sucesso:
        pedido.refresh_from_db(fields=["status"])
        if pedido.status == "pago":
            print("Pagamento processado: já processado")
            print("===========================")
            return JsonResponse(
                {"status": "ok", "mensagem": "Evento já processado."}
            )
        print("Pagamento processado: não")
        print("===========================")
        return JsonResponse(
            {"status": "erro", "mensagem": "Pagamento não confirmado."},
            status=409,
        )

    print("Pagamento processado: sim")
    print("===========================")

    telefone = pedido.usuario.telefone
    if telefone:
        texto = (
            "✅ Pagamento confirmado!\n"
            "\n"
            f"Pedido #{pedido.id} pago com sucesso.\n"
            "\n"
            "Seu pagamento foi identificado automaticamente.\n"
            "\n"
            "Obrigado pela compra!"
        )
        enviar_mensagem_waha(telefone, texto)
        limpar_cobranca_temporaria_whatsapp(telefone, pedido.id)

    return JsonResponse({"status": "ok", "mensagem": "Pagamento confirmado."})
