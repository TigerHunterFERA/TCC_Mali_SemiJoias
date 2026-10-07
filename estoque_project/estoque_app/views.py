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

from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import check_password, make_password, identify_hasher
from django.db import transaction, IntegrityError
from django.db.models import Q, Count, Sum, F, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.conf import settings
from .models import Produto, TipoBanho, MovimentacaoEstoque, Pedido, ItemPedido, Usuario
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
# from django.shortcuts import render, redirect
import json
import re
import unicodedata
import requests
import secrets
import base64
import mimetypes
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


def senha_armazenada_e_hash(senha_armazenada):
    """True se o valor já estiver no formato de hash do Django."""
    if not senha_armazenada:
        return False
    try:
        identify_hasher(senha_armazenada)
        return True
    except ValueError:
        return False


def senha_admin_confere(usuario, senha_digitada):
    """
    Confere a senha do administrador.
    Se ainda estiver em texto puro (legado), compara e grava hash no primeiro acerto.
    """
    senha_digitada = senha_digitada or ""
    senha_armazenada = usuario.senha or ""

    if senha_armazenada_e_hash(senha_armazenada):
        return check_password(senha_digitada, senha_armazenada)

    if senha_digitada and senha_digitada == senha_armazenada:
        usuario.senha = make_password(senha_digitada)
        usuario.save(update_fields=["senha"])
        return True

    return False


def exigir_login_admin(view_func):
    """Redireciona para o login se a sessão administrativa não estiver válida."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.session.get("autenticado"):
            return redirect("login")
        if not request.session.get("usuario_id"):
            return redirect("login")
        return view_func(request, *args, **kwargs)

    return _wrapped


def login(request):
    """Login administrativo único. Não cria conta e não autentica cliente."""
    if request.method != "POST" and request.session.get("autenticado"):
        return redirect("pagina_inicial")

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        senha = request.POST.get("senha") or ""
        mensagem_erro = "E-mail ou senha inválidos."

        if not email or not senha:
            return render(
                request,
                "estoque_app/login.html",
                {"mensagem": mensagem_erro},
            )

        admin = Usuario.objects.filter(
            email__iexact=email,
            tipo="admin",
        ).first()

        if admin is None or not senha_admin_confere(admin, senha):
            return render(
                request,
                "estoque_app/login.html",
                {"mensagem": mensagem_erro},
            )

        request.session.cycle_key()
        request.session["usuario_id"] = admin.id
        request.session["autenticado"] = True
        return redirect("pagina_inicial")

    return render(request, "estoque_app/login.html")


@require_POST
def logout(request):
    """Encerra a sessão administrativa e volta ao login."""
    request.session.flush()
    return redirect("login")


@exigir_login_admin
def pagina_inicial(request):
    """Tela de entrada após o login, com atalhos para os módulos."""
    return render(request, "estoque_app/pagina_inicial.html")


@exigir_login_admin
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

@exigir_login_admin
def listar_produtos(request):
    # select_related evita consulta extra ao mostrar o nome do banho
    produtos = Produto.objects.select_related("banho").all()
    return render(request, "estoque_app/produtos.html", {"produtos": produtos})

@exigir_login_admin
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
            foto=request.FILES.get("foto") or None,
        )
        return redirect("produtos")

    tipos_banho = TipoBanho.objects.all().order_by("nome")
    return render(request, "estoque_app/adicionar.html", {"tipos_banho": tipos_banho})

@exigir_login_admin
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
        nova_foto = request.FILES.get("foto")
        if nova_foto:
            produto.foto = nova_foto
        produto.save()
        return redirect("produtos")

    tipos_banho = TipoBanho.objects.all().order_by("nome")
    return render(
        request,
        "estoque_app/editar.html",
        {"produto": produto, "tipos_banho": tipos_banho},
    )

@exigir_login_admin
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


@exigir_login_admin
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


@exigir_login_admin
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


@exigir_login_admin
def listar_pedidos(request):
    """Lista os pedidos existentes."""
    pedidos = (
        Pedido.objects.select_related("usuario")
        .order_by("-data_pedido")
    )
    return render(request, "estoque_app/pedidos.html", {"pedidos": pedidos})


@exigir_login_admin
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


@exigir_login_admin
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


@exigir_login_admin
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


@exigir_login_admin
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


@exigir_login_admin
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


@exigir_login_admin
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


@exigir_login_admin
def listar_clientes(request):
    """Lista usuários do tipo cliente (nome, e-mail e telefone)."""
    clientes = Usuario.objects.filter(tipo="cliente").order_by("nome")

    # Atributo só para a tela; o valor no banco permanece só com dígitos.
    for cliente in clientes:
        cliente.telefone_exibicao = formatar_telefone_para_exibicao(cliente.telefone)

    return render(request, "estoque_app/clientes.html", {"clientes": clientes})


@exigir_login_admin
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


def enviar_imagem_waha(numero, dados_base64, nome_arquivo, mimetype, caption=""):
    """
    Envia uma imagem pelo WAHA (POST /api/sendImage).
    Usa base64 para o container Docker não precisar ler o disco do Django.
    Retorna (True, texto) em sucesso ou (False, texto) em erro.
    """
    digitos = "".join(c for c in str(numero) if c.isdigit())

    if not digitos:
        return False, "Informe um número válido."

    if not dados_base64:
        return False, "Informe o conteúdo da imagem."

    chat_id = f"{digitos}@c.us"
    url = settings.WAHA_API_URL.rstrip("/") + "/api/sendImage"
    arquivo = {
        "mimetype": mimetype,
        "filename": nome_arquivo,
        "data": dados_base64,
    }
    corpo = {
        "session": settings.WAHA_SESSION,
        "chatId": chat_id,
        "file": arquivo,
    }
    if caption:
        corpo["caption"] = caption

    cabecalhos = {
        "Content-Type": "application/json",
        "X-Api-Key": settings.WAHA_API_KEY,
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
        return True, "Imagem enviada com sucesso pelo WAHA."

    if resposta.status_code == 401:
        return False, "Não autorizado pelo WAHA. Verifique a API Key."

    return False, f"O WAHA retornou o status {resposta.status_code}."


def tentar_enviar_foto_produto_waha(numero, produto_id):
    """
    Tenta enviar a foto principal do Produto pelo WhatsApp.
    A imagem vem somente de Produto.foto. Falha não interrompe o fluxo textual.
    """
    try:
        produto = Produto.objects.filter(id=produto_id).first()
        if produto is None:
            print("Foto do produto não enviada; fluxo textual preservado.")
            return False

        if not produto.foto:
            print("Ação: produto selecionado")
            print("Foto: não cadastrada")
            return False

        if not produto.foto.storage.exists(produto.foto.name):
            print("Foto do produto não enviada; fluxo textual preservado.")
            return False

        with produto.foto.open("rb") as arquivo_foto:
            conteudo = arquivo_foto.read()

        if not conteudo:
            print("Foto do produto não enviada; fluxo textual preservado.")
            return False

        nome_arquivo = str(produto.foto.name).replace("\\", "/").split("/")[-1]
        mimetype, _extensao = mimetypes.guess_type(nome_arquivo)
        if not mimetype or not mimetype.startswith("image/"):
            mimetype = "image/jpeg"

        dados_base64 = base64.b64encode(conteudo).decode("ascii")
        sucesso, _mensagem = enviar_imagem_waha(
            numero,
            dados_base64,
            nome_arquivo,
            mimetype,
            caption=produto.nome,
        )
        if sucesso:
            print("Ação: foto do produto enviada")
            print(f"Produto: {produto.nome}")
            return True

        print("Foto do produto não enviada; fluxo textual preservado.")
        return False
    except Exception:
        print("Foto do produto não enviada; fluxo textual preservado.")
        return False


@exigir_login_admin
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

# Último produto escolhido por número no catálogo (Bloco 22.3).
# telefone -> id do Produto. Só leitura depois; não cria pedido.
# Se o Django reiniciar, este dicionário é perdido — esperado nesta etapa.
clientes_produto_em_contexto = {}

# Estados temporários do carrinho (Bloco 22.4). Somente memória.
# Se o Django reiniciar, são perdidos — esperado nesta etapa.
# telefone -> lista de ids de ItemPedido na ordem exibida.
clientes_aguardando_remocao_carrinho = {}
# telefone -> lista de ids de ItemPedido na ordem exibida.
clientes_aguardando_item_alteracao = {}
# telefone -> id do ItemPedido cuja quantidade será alterada.
clientes_aguardando_nova_quantidade = {}
# telefones aguardando SIM/NÃO para esvaziar o carrinho.
clientes_aguardando_confirmacao_limpar_carrinho = set()


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


def normalizar_mensagem(texto):
    """
    Normaliza texto do WhatsApp para comparar comandos e frases.
    Não acessa banco, não chama WAHA e não altera pedido nem estoque.
    """
    if texto is None:
        return ""

    texto = str(texto).strip().casefold()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = re.sub(r" +", " ", texto)
    return texto.strip()


COMANDOS_CATALOGO_WHATSAPP = {
    "produto",
    "produtos",
    "catalogo",
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

# Frases naturais já no formato de normalizar_mensagem.
# Os comandos exatos continuam em COMANDOS_*; o webhook usa só eles.
ALIASES_CATALOGO_WHATSAPP = {
    "ver produtos",
    "ver produto",
    "mostrar produtos",
    "mostrar produto",
    "mostra os produtos",
    "me mostra os produtos",
    "me mostre os produtos",
    "quero ver os produtos",
    "quero ver produtos",
    "listar produtos",
    "lista de produtos",
    "ver catalogo",
    "listar catalogo",
    "mostrar catalogo",
    "mostra o catalogo",
    "me mostra o catalogo",
    "me mostre o catalogo",
    "abre o catalogo",
    "abrir catalogo",
    "quero ver o catalogo",
    "quais produtos voces tem",
    "o que voces tem",
    "o que tem disponivel",
    "o que voces tem disponivel",
    "quero ver as pecas",
    "me mostra as pecas",
    "ver semijoias",
    "quero ver semijoias",
    "mostra as joias",
    "pode me mostrar os produtos",
    "queria ver o catalogo",
}

ALIASES_PEDIDOS_WHATSAPP = {
    "ver pedidos",
    "ver meus pedidos",
    "consultar pedido",
    "consultar pedidos",
    "status do pedido",
    "acompanhar pedido",
    "acompanhar pedidos",
    "como esta meu pedido",
    "como esta o meu pedido",
    "onde esta meu pedido",
    "ver meu pedido",
    "ver o meu pedido",
    "pedido pendente",
    "pedido pago",
    "pedido cancelado",
    "meu pedido foi confirmado",
    "ja confirmou meu pedido",
    "qual o numero do pedido",
    "historico de pedidos",
    "ultimo pedido",
    "acompanhar compra",
    "quero ver meus pedidos",
    "quais sao meus pedidos",
    "tenho algum pedido",
}

ALIASES_FINALIZACAO_WHATSAPP = {
    "finalizar compra",
    "fechar pedido",
    "concluir compra",
    "concluir pedido",
    "quero finalizar",
    "quero finalizar meu pedido",
    "quero finalizar o meu pedido",
    "quero finalizar minha compra",
    "pode finalizar",
    "pode finalizar meu pedido",
    "vamos finalizar",
    "fechar compra",
    "terminar pedido",
    "confirmar compra",
    "confirmar pedido",
    "finaliza pra mim",
    "quero fechar o pedido",
    "quero fechar meu pedido",
    "quero concluir a compra",
}

ALIASES_PAGAMENTO_WHATSAPP = {
    "formas de pagamento",
    "forma de pagamento",
    "como pagar",
    "como eu pago",
    "como faco para pagar",
    "aceita pix",
    "pagar com pix",
    "quero pagar",
    "quero pagar meu pedido",
    "ir para pagamento",
    "dados do pagamento",
    "chave pix",
    "manda o pix",
    "qual a chave pix",
    "qual chave pix",
    "qual e a chave pix",
    "como funciona o pix",
    "onde pago",
    "onde eu pago",
}

# Frases de preço, estoque e detalhes (já normalizadas).
ALIASES_PRECO_WHATSAPP = {
    "preco",
    "valor",
    "quanto custa",
    "quanto e",
    "qual o preco",
    "qual o valor",
    "quanto custa esse produto",
    "quanto custa esse brinco",
    "preco do produto",
    "valor do produto",
    "quanto sai",
    "quanto fica",
    "me passa o preco",
    "me fala o valor",
    "tem preco",
    "qto custa",
    "qt custa",
    "quanto ta",
    "valor desse produto",
}

ALIASES_ESTOQUE_WHATSAPP = {
    "tem estoque",
    "tem disponivel",
    "esta disponivel",
    "ainda tem",
    "tem esse produto",
    "tem essa peca",
    "quantos tem",
    "quantas unidades tem",
    "tem pronta entrega",
    "esta em estoque",
    "estoque desse produto",
    "ver estoque",
    "acabou",
    "esta esgotado",
    "tem disponibilidade",
    "tem mais de um",
}

ALIASES_DETALHES_WHATSAPP = {
    "detalhes",
    "ver detalhes",
    "detalhes do produto",
    "mais detalhes",
    "quero saber mais",
    "me fala mais desse produto",
    "qual a descricao",
    "qual o material",
    "qual o banho",
    "tem descricao",
    "me mostra a descricao",
    "informacoes do produto",
    "info do produto",
    "ver informacoes",
    "qual o peso",
    "essa peca e dourada",
    "essa peca e prata",
}

ALIASES_ADICIONAR_CARRINHO_WHATSAPP = {
    "adicionar ao carrinho",
    "adiciona no carrinho",
    "colocar no carrinho",
    "coloca no carrinho",
    "quero esse",
    "quero esse produto",
    "vou levar esse",
    "pode adicionar",
    "adiciona esse",
    "coloca esse pra mim",
    "adicionar produto",
    "quero comprar esse",
    "selecionar produto",
    "escolher esse",
    "add carrinho",
    "add no carrinho",
}

ALIASES_VER_CARRINHO_WHATSAPP = {
    "carrinho",
    "ver carrinho",
    "meu carrinho",
    "ver meu carrinho",
    "mostrar carrinho",
    "mostra o carrinho",
    "mostrar meu carrinho",
    "verifique o carrinho",
    "verificar carrinho",
    "checar carrinho",
    "o que tem no carrinho",
    "o que eu coloquei no carrinho",
    "quais itens estao no carrinho",
    "quais produtos escolhi",
    "ver itens",
    "meus itens",
    "minha sacola",
    "ver sacola",
    "sacola",
    "resumo do carrinho",
    "resumo da compra",
    "quanto deu o carrinho",
    "total do carrinho",
    "como esta meu carrinho",
    "abrir carrinho",
}

ALIASES_REMOVER_ITEM_WHATSAPP = {
    "remover item",
    "remover produto",
    "tirar do carrinho",
    "tira do carrinho",
    "remove esse produto",
    "excluir item",
    "excluir produto",
    "apagar item",
    "retira esse produto",
    "remover do carrinho",
}

ALIASES_ALTERAR_QUANTIDADE_WHATSAPP = {
    "alterar quantidade",
    "mudar quantidade",
    "trocar quantidade",
    "aumentar quantidade",
    "diminuir quantidade",
    "mudar qtd",
    "quantidade do carrinho",
}

ALIASES_LIMPAR_CARRINHO_WHATSAPP = {
    "limpar carrinho",
    "esvaziar carrinho",
    "apagar carrinho",
    "remover tudo",
    "tirar tudo do carrinho",
    "zerar carrinho",
    "deixa o carrinho vazio",
    "excluir todos os itens",
    "limpa tudo",
    "esvazia meu carrinho",
}

ALIASES_CONTINUAR_COMPRANDO_WHATSAPP = {
    "continuar comprando",
    "quero continuar comprando",
    "ver mais produtos",
    "adicionar outro produto",
    "comprar mais",
    "escolher outro produto",
    "voltar para produtos",
}

ALIASES_CANCELAR_OPERACAO_CARRINHO_WHATSAPP = {
    "cancelar",
    "voltar",
}

# Chave interna -> título da lista e termos para filtrar tipo/nome no banco.
# O campo Produto.categoria no banco atual é "Feminina", não o tipo da peça.
CATEGORIAS_WHATSAPP = {
    "brinco": {
        "titulo": "Brincos",
        "termos": ["brinco", "brincos"],
    },
    "colar": {
        "titulo": "Colares",
        "termos": ["colar", "colares"],
    },
    "pulseira": {
        "titulo": "Pulseiras",
        "termos": ["pulseira", "pulseiras"],
    },
    "anel": {
        "titulo": "Anéis",
        "termos": ["anel", "aneis"],
    },
    "conjunto": {
        "titulo": "Conjuntos",
        "termos": ["conjunto", "conjuntos"],
    },
    "argola": {
        "titulo": "Argolas",
        "termos": ["argola", "argolas"],
    },
    "corrente": {
        "titulo": "Correntes",
        "termos": ["corrente", "correntes"],
    },
    "gargantilha": {
        "titulo": "Gargantilhas",
        "termos": ["gargantilha", "gargantilhas"],
    },
    "bracelete": {
        "titulo": "Braceletes",
        "termos": ["bracelete", "braceletes"],
    },
}

MENSAGEM_SEM_PRODUTO_CONTEXTO = (
    "Escolha primeiro um produto do catálogo. "
    "Envie o número do produto depois de ver a lista."
)


INTENCOES_WHATSAPP_PERMITIDAS = {
    "consultar_catalogo",
    "consultar_pedidos",
    "iniciar_finalizacao",
    "consultar_pagamento",
    "buscar_categoria",
    "detalhar_produto",
    "consultar_preco",
    "consultar_estoque",
    "adicionar_carrinho",
    "ver_carrinho",
    "remover_item",
    "alterar_quantidade",
    "limpar_carrinho",
    "continuar_comprando",
    "desconhecida",
}


def identificar_categoria_whatsapp(texto):
    """
    Lê um texto já normalizado (ou normaliza se ainda não estiver)
    e devolve a chave de CATEGORIAS_WHATSAPP, ou None.
    Termos mais específicos vêm primeiro (ex.: gargantilha antes de colar).
    """
    texto = normalizar_mensagem(texto)
    if texto == "":
        return None

    if "gargantilha" in texto:
        return "gargantilha"
    elif "bracelete" in texto:
        return "bracelete"
    elif "conjunto" in texto:
        return "conjunto"
    elif "argola" in texto:
        return "argola"
    elif "corrente" in texto:
        return "corrente"
    elif "brinco" in texto:
        return "brinco"
    elif "colar" in texto:
        return "colar"
    elif "pulseira" in texto:
        return "pulseira"
    elif "anel" in texto or "aneis" in texto:
        return "anel"

    return None


def interpretar_intencao_whatsapp(mensagem):
    """
    Classifica frases naturais no contrato fechado {"intencao": ...}.
    Não acessa banco, não altera pedido/estoque e não chama WAHA.

    Ordem (para não misturar preço, carrinho e categoria):
    1. catálogo, pedidos, finalização e pagamento (BLOCO 22.2);
    2. carrinho (ver, adicionar, remover, alterar, limpar, continuar);
    3. preço;
    4. estoque;
    5. detalhes;
    6. categoria (palavra no texto);
    7. desconhecida.
    """
    texto = normalizar_mensagem(mensagem)

    if texto in COMANDOS_CATALOGO_WHATSAPP or texto in ALIASES_CATALOGO_WHATSAPP:
        intencao = "consultar_catalogo"
    elif texto in COMANDOS_PEDIDOS_WHATSAPP or texto in ALIASES_PEDIDOS_WHATSAPP:
        intencao = "consultar_pedidos"
    elif texto in COMANDOS_FINALIZAR_WHATSAPP or texto in ALIASES_FINALIZACAO_WHATSAPP:
        intencao = "iniciar_finalizacao"
    elif texto in COMANDOS_PAGAMENTO_WHATSAPP or texto in ALIASES_PAGAMENTO_WHATSAPP:
        intencao = "consultar_pagamento"
    elif texto in ALIASES_VER_CARRINHO_WHATSAPP:
        intencao = "ver_carrinho"
    elif texto in ALIASES_ADICIONAR_CARRINHO_WHATSAPP:
        intencao = "adicionar_carrinho"
    elif texto in ALIASES_REMOVER_ITEM_WHATSAPP:
        intencao = "remover_item"
    elif texto in ALIASES_ALTERAR_QUANTIDADE_WHATSAPP:
        intencao = "alterar_quantidade"
    elif texto in ALIASES_LIMPAR_CARRINHO_WHATSAPP:
        intencao = "limpar_carrinho"
    elif texto in ALIASES_CONTINUAR_COMPRANDO_WHATSAPP:
        intencao = "continuar_comprando"
    elif texto in ALIASES_PRECO_WHATSAPP:
        intencao = "consultar_preco"
    elif texto in ALIASES_ESTOQUE_WHATSAPP:
        intencao = "consultar_estoque"
    elif texto in ALIASES_DETALHES_WHATSAPP:
        intencao = "detalhar_produto"
    elif identificar_categoria_whatsapp(texto) is not None:
        intencao = "buscar_categoria"
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


def formatar_preco_whatsapp(preco):
    """Formata Decimal do banco para o padrão já usado no catálogo."""
    return f"{preco:.2f}".replace(".", ",")


def montar_catalogo_categoria_whatsapp(chave_categoria):
    """
    Lista produtos com estoque > 0 cujo tipo ou nome combina com a categoria.
    Somente leitura. Devolve (texto, acao, ids) no mesmo formato do catálogo.
    """
    info = CATEGORIAS_WHATSAPP.get(chave_categoria)
    if info is None:
        return (
            "Não encontrei essa categoria. Envie produtos para ver o catálogo.",
            "categoria não reconhecida",
            [],
        )

    filtro = Q()
    for termo in info["termos"]:
        filtro = filtro | Q(tipo__icontains=termo) | Q(nome__icontains=termo)

    produtos = list(
        Produto.objects.filter(estoque__gt=0).filter(filtro).order_by("nome")
    )
    titulo = info["titulo"]

    if not produtos:
        return (
            f"No momento não temos {titulo.lower()} disponíveis em estoque.",
            "categoria vazia",
            [],
        )

    linhas = [f"{titulo} disponíveis:", ""]
    ids = []
    for indice, produto in enumerate(produtos, start=1):
        preco_texto = formatar_preco_whatsapp(produto.preco)
        linhas.append(f"{indice}. {produto.nome}")
        linhas.append(f"Preço: R$ {preco_texto}")
        linhas.append(f"Estoque: {produto.estoque}")
        linhas.append("")
        ids.append(produto.id)

    linhas.append("Envie o número do produto que deseja conhecer melhor.")
    return "\n".join(linhas).strip(), "categoria enviada", ids


def obter_produto_contexto_whatsapp(produto_id):
    """Busca o Produto pelo id. Não altera estoque. None se o id for inválido."""
    if produto_id is None:
        return None
    return Produto.objects.filter(id=produto_id).first()


def montar_consulta_preco_whatsapp(produto_id):
    """Responde o preço real do produto em contexto. Somente leitura."""
    produto = obter_produto_contexto_whatsapp(produto_id)
    if produto is None:
        return MENSAGEM_SEM_PRODUTO_CONTEXTO, "preço sem produto"

    preco_texto = formatar_preco_whatsapp(produto.preco)
    texto = (
        f"Produto: {produto.nome}\n"
        f"Preço: R$ {preco_texto}"
    )
    return texto, "preço enviado"


def montar_consulta_estoque_whatsapp(produto_id):
    """Responde o estoque real do produto em contexto. Não altera o banco."""
    produto = obter_produto_contexto_whatsapp(produto_id)
    if produto is None:
        return MENSAGEM_SEM_PRODUTO_CONTEXTO, "estoque sem produto"

    if produto.estoque <= 0:
        texto = (
            f"Produto: {produto.nome}\n"
            "Estoque: indisponível (esgotado)."
        )
        return texto, "estoque esgotado"

    texto = (
        f"Produto: {produto.nome}\n"
        f"Estoque disponível: {produto.estoque} unidade(s)"
    )
    return texto, "estoque enviado"


def montar_detalhes_produto_whatsapp(produto_id):
    """
    Mostra campos reais e preenchidos do Produto em contexto.
    Não envia id, foto nem caminhos de arquivo.
    """
    produto = obter_produto_contexto_whatsapp(produto_id)
    if produto is None:
        return MENSAGEM_SEM_PRODUTO_CONTEXTO, "detalhes sem produto"

    linhas = [f"Produto: {produto.nome}"]

    descricao = (produto.descricao or "").strip()
    if descricao:
        linhas.append(f"Descrição: {descricao}")

    linhas.append(f"Preço: R$ {formatar_preco_whatsapp(produto.preco)}")

    tipo = (produto.tipo or "").strip()
    if tipo:
        linhas.append(f"Tipo: {tipo}")

    categoria = (produto.categoria or "").strip()
    if categoria:
        linhas.append(f"Categoria: {categoria}")

    if produto.banho_id and produto.banho:
        linhas.append(f"Banho: {produto.banho.nome}")

    if produto.peso is not None:
        peso_texto = f"{produto.peso:.2f}".replace(".", ",")
        linhas.append(f"Peso: {peso_texto} g")

    linhas.append(f"Estoque: {produto.estoque}")
    return "\n".join(linhas), "detalhes enviados"


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


def limpar_estados_operacao_carrinho_whatsapp(telefone):
    """Sai das etapas de remover, alterar quantidade e limpar o carrinho."""
    clientes_aguardando_remocao_carrinho.pop(telefone, None)
    clientes_aguardando_item_alteracao.pop(telefone, None)
    clientes_aguardando_nova_quantidade.pop(telefone, None)
    clientes_aguardando_confirmacao_limpar_carrinho.discard(telefone)


def obter_pedido_pendente_do_cliente(cliente):
    """
    Carrinho atual = Pedido pendente mais recente do próprio cliente.
    Não busca por id enviado no WhatsApp.
    Pedidos pendentes antigos não são apagados nem mesclados.
    """
    if cliente is None:
        return None
    return (
        Pedido.objects.filter(usuario=cliente, status="pendente")
        .order_by("-data_pedido", "-id")
        .first()
    )


def listar_itens_carrinho(pedido):
    """Itens do carrinho em ordem estável (id). Não altera o banco."""
    if pedido is None:
        return []
    return list(
        ItemPedido.objects.filter(pedido=pedido).order_by("id")
    )


def obter_item_do_carrinho_do_cliente(cliente, item_id):
    """Só devolve ItemPedido que pertence ao Pedido pendente do cliente."""
    pedido = obter_pedido_pendente_do_cliente(cliente)
    if pedido is None or item_id is None:
        return None
    return ItemPedido.objects.filter(id=item_id, pedido=pedido).first()


def montar_carrinho_whatsapp(cliente):
    """
    Monta o texto do carrinho (Pedido pendente).
    Total = soma de quantidade * preco_unitario (Decimal).
    """
    pedido = obter_pedido_pendente_do_cliente(cliente)
    itens = listar_itens_carrinho(pedido)
    if not itens:
        return "Seu carrinho está vazio.", "carrinho vazio", []

    linhas = ["Carrinho:", ""]
    ids_itens = []
    total = Decimal("0")
    for indice, item in enumerate(itens, start=1):
        subtotal = item.quantidade * item.preco_unitario
        total = total + subtotal
        linhas.append(f"{indice}. {item.produto.nome}")
        linhas.append(f"Quantidade: {item.quantidade}")
        linhas.append(
            f"Unitário: R$ {formatar_preco_whatsapp(item.preco_unitario)}"
        )
        linhas.append(f"Subtotal: R$ {formatar_preco_whatsapp(subtotal)}")
        linhas.append("")
        ids_itens.append(item.id)

    linhas.append(f"Total: R$ {formatar_preco_whatsapp(total)}")
    return "\n".join(linhas).strip(), "carrinho enviado", ids_itens


def iniciar_quantidade_produto_contexto_whatsapp(telefone):
    """
    'adicionar ao carrinho' com produto em contexto:
    pede a quantidade usando o fluxo já existente.
    """
    produto_id = clientes_produto_em_contexto.get(telefone)
    if produto_id is None:
        return MENSAGEM_SEM_PRODUTO_CONTEXTO, "carrinho sem produto"

    produto = Produto.objects.filter(id=produto_id).first()
    if produto is None or produto.estoque <= 0:
        return (
            "O produto selecionado não está mais disponível. "
            "Envie 'produtos' para consultar o catálogo novamente.",
            "produto indisponível",
        )

    clientes_aguardando_quantidade[telefone] = produto.id
    preco_texto = formatar_preco_whatsapp(produto.preco)
    texto = (
        f"{produto.nome}\n"
        f"Preço: R$ {preco_texto}\n"
        f"Estoque disponível: {produto.estoque}\n"
        "\n"
        "Quantas unidades você deseja?"
    )
    return texto, "aguardando quantidade"


def carrinho_possui_estoque_suficiente(pedido):
    """
    Só consulta Produto.estoque. Não baixa e não cria movimentação.
    Retorna (True, None) ou (False, nome_do_produto).
    """
    itens = listar_itens_carrinho(pedido)
    for item in itens:
        produto = Produto.objects.filter(id=item.produto_id).first()
        if produto is None or item.quantidade > produto.estoque:
            nome = produto.nome if produto else "selecionado"
            return False, nome
    return True, None


def iniciar_finalizacao_whatsapp(cliente):
    """
    Localiza o pedido pendente mais recente do próprio cliente
    e monta o pedido de confirmação. Não altera o banco.
    """
    pedido = obter_pedido_pendente_do_cliente(cliente)
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

    estoque_ok, nome_produto = carrinho_possui_estoque_suficiente(pedido)
    if not estoque_ok:
        return (
            f"Não foi possível finalizar. Estoque insuficiente para {nome_produto}. "
            "Ajuste o carrinho e tente novamente.",
            "estoque insuficiente para finalizar",
            pedido.id,
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
    No SIM, coloca o item no Pedido pendente (carrinho) sem baixar estoque.
    Retorna (texto, acao, pedido_id, nome_produto, quantidade).
    """
    mensagem = (mensagem or "").strip().lower()

    if mensagem in ("nao", "não"):
        return (
            "Item não adicionado ao carrinho. Envie 'produtos' para consultar o catálogo novamente.",
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
    Coloca o item no Pedido pendente mais recente do cliente (carrinho).
    Se não houver pendente, cria um novo. Não baixa estoque.
    """
    try:
        with transaction.atomic():
            produto = Produto.objects.filter(id=produto_id).first()
            if not produto or quantidade is None or quantidade < 1:
                return (
                    "O produto não está mais disponível na quantidade solicitada. "
                    "Envie 'produtos' para consultar o catálogo novamente.",
                    "produto indisponível",
                    None,
                    None,
                    None,
                )

            pedido = obter_pedido_pendente_do_cliente(cliente)
            if pedido is None:
                pedido = Pedido.objects.create(usuario=cliente)

            item_existente = ItemPedido.objects.filter(
                pedido=pedido,
                produto=produto,
            ).first()
            quantidade_no_carrinho = 0
            if item_existente:
                quantidade_no_carrinho = item_existente.quantidade

            quantidade_final = quantidade_no_carrinho + quantidade
            if quantidade_final > produto.estoque:
                return (
                    "Não foi possível adicionar. A quantidade no carrinho "
                    "ultrapassaria o estoque disponível.\n"
                    f"Estoque: {produto.estoque}\n"
                    f"Já no carrinho: {quantidade_no_carrinho}",
                    "estoque insuficiente no carrinho",
                    pedido.id,
                    produto.nome,
                    quantidade,
                )

            if item_existente:
                item_existente.quantidade = quantidade_final
                item_existente.save(update_fields=["quantidade"])
            else:
                ItemPedido.objects.create(
                    pedido=pedido,
                    produto=produto,
                    quantidade=quantidade,
                    preco_unitario=produto.preco,
                )

            texto = (
                "Produto adicionado ao carrinho.\n"
                "\n"
                f"Produto: {produto.nome}\n"
                f"Quantidade: {quantidade}\n"
                "\n"
                "Você pode:\n"
                "- continuar comprando\n"
                "- ver carrinho\n"
                "- finalizar pedido"
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


def remover_item_carrinho_whatsapp(cliente, item_id):
    """Remove só o ItemPedido do carrinho do próprio cliente. Não altera estoque."""
    item = obter_item_do_carrinho_do_cliente(cliente, item_id)
    if item is None:
        return (
            "Não encontrei esse item no seu carrinho.",
            "item não encontrado no carrinho",
        )

    item.delete()
    texto_carrinho, acao_carrinho, _ids = montar_carrinho_whatsapp(cliente)
    texto = "Item removido do carrinho.\n\n" + texto_carrinho
    return texto, acao_carrinho


def alterar_quantidade_item_carrinho_whatsapp(cliente, item_id, nova_quantidade):
    """
    Troca a quantidade de um ItemPedido do próprio cliente.
    Nova quantidade deve ser > 0 e <= estoque. Não baixa estoque.
    """
    item = obter_item_do_carrinho_do_cliente(cliente, item_id)
    if item is None:
        return (
            "Não encontrei esse item no seu carrinho.",
            "item não encontrado no carrinho",
        )

    if nova_quantidade is None or nova_quantidade < 1:
        return (
            "A quantidade deve ser um número maior que 0. "
            "Para retirar o item, envie 'remover item'.",
            "quantidade do carrinho inválida",
        )

    produto = Produto.objects.filter(id=item.produto_id).first()
    if produto is None or nova_quantidade > produto.estoque:
        estoque_atual = produto.estoque if produto else 0
        return (
            "Não foi possível alterar. A quantidade ultrapassa o estoque "
            f"disponível ({estoque_atual}).",
            "estoque insuficiente no carrinho",
        )

    item.quantidade = nova_quantidade
    item.save(update_fields=["quantidade"])
    texto_carrinho, acao_carrinho, _ids = montar_carrinho_whatsapp(cliente)
    texto = "Quantidade atualizada.\n\n" + texto_carrinho
    return texto, acao_carrinho


def limpar_itens_carrinho_whatsapp(cliente):
    """Apaga só os ItemPedido do Pedido pendente. Mantém o Pedido. Não altera estoque."""
    pedido = obter_pedido_pendente_do_cliente(cliente)
    if pedido is None:
        return "Seu carrinho está vazio.", "carrinho vazio"

    ItemPedido.objects.filter(pedido=pedido).delete()
    return "Seu carrinho foi esvaziado.", "carrinho limpo"


def iniciar_remocao_item_carrinho_whatsapp(cliente):
    texto, acao, ids_itens = montar_carrinho_whatsapp(cliente)
    if not ids_itens:
        return texto, acao, []
    texto = texto + "\n\nEnvie o número do item que deseja remover.\nOu envie cancelar."
    return texto, "aguardando remoção do carrinho", ids_itens


def interpretar_remocao_item_carrinho_whatsapp(mensagem, ids_itens, cliente):
    texto = normalizar_mensagem(mensagem)
    if texto in ALIASES_CANCELAR_OPERACAO_CARRINHO_WHATSAPP:
        return "Remoção cancelada.", "operação do carrinho cancelada"

    mensagem_crua = (mensagem or "").strip()
    if not mensagem_crua.isdigit():
        return (
            "Opção inválida. Envie o número do item ou cancele.",
            "remoção inválida",
        )

    numero = int(mensagem_crua)
    if numero < 1 or numero > len(ids_itens):
        return (
            "Opção inválida. Envie o número do item ou cancele.",
            "remoção inválida",
        )

    return remover_item_carrinho_whatsapp(cliente, ids_itens[numero - 1])


def iniciar_alteracao_quantidade_carrinho_whatsapp(cliente):
    texto, acao, ids_itens = montar_carrinho_whatsapp(cliente)
    if not ids_itens:
        return texto, acao, []
    texto = (
        texto
        + "\n\nEnvie o número do item para alterar a quantidade.\nOu envie cancelar."
    )
    return texto, "aguardando item alteração", ids_itens


def interpretar_item_alteracao_carrinho_whatsapp(mensagem, ids_itens):
    texto = normalizar_mensagem(mensagem)
    if texto in ALIASES_CANCELAR_OPERACAO_CARRINHO_WHATSAPP:
        return "Alteração cancelada.", "operação do carrinho cancelada", None

    mensagem_crua = (mensagem or "").strip()
    if not mensagem_crua.isdigit():
        return (
            "Opção inválida. Envie o número do item ou cancele.",
            "item alteração inválido",
            None,
        )

    numero = int(mensagem_crua)
    if numero < 1 or numero > len(ids_itens):
        return (
            "Opção inválida. Envie o número do item ou cancele.",
            "item alteração inválido",
            None,
        )

    item_id = ids_itens[numero - 1]
    return (
        "Informe a nova quantidade (número maior que 0).\nOu envie cancelar.",
        "aguardando nova quantidade",
        item_id,
    )


def interpretar_nova_quantidade_carrinho_whatsapp(mensagem, item_id, cliente):
    texto = normalizar_mensagem(mensagem)
    if texto in ALIASES_CANCELAR_OPERACAO_CARRINHO_WHATSAPP:
        return "Alteração cancelada.", "operação do carrinho cancelada"

    mensagem_crua = (mensagem or "").strip()
    if not mensagem_crua.isdigit():
        return (
            "Quantidade inválida. Informe um número maior que 0 ou cancele.",
            "quantidade do carrinho inválida",
        )

    nova_quantidade = int(mensagem_crua)
    return alterar_quantidade_item_carrinho_whatsapp(
        cliente,
        item_id,
        nova_quantidade,
    )


def iniciar_limpeza_carrinho_whatsapp(cliente):
    pedido = obter_pedido_pendente_do_cliente(cliente)
    itens = listar_itens_carrinho(pedido)
    if not itens:
        return "Seu carrinho está vazio.", "carrinho vazio"
    texto = (
        "Deseja realmente limpar o carrinho? Responda sim ou não.\n"
        "Ou envie cancelar."
    )
    return texto, "aguardando confirmação limpar carrinho"


def interpretar_limpeza_carrinho_whatsapp(mensagem, cliente):
    texto = normalizar_mensagem(mensagem)
    if texto in ALIASES_CANCELAR_OPERACAO_CARRINHO_WHATSAPP or texto == "nao":
        return "O carrinho não foi alterado.", "limpeza do carrinho cancelada"
    if texto != "sim":
        return (
            "Resposta inválida. Responda sim ou não.",
            "confirmação limpar inválida",
        )
    return limpar_itens_carrinho_whatsapp(cliente)


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
            mensagem_normalizada = normalizar_mensagem(mensagem)
            # Novo catálogo cancela quantidade/confirmação/finalização e substitui a lista.
            if mensagem_normalizada in COMANDOS_CATALOGO_WHATSAPP:
                clientes_aguardando_quantidade.pop(telefone, None)
                clientes_aguardando_confirmacao.pop(telefone, None)
                clientes_aguardando_finalizacao.pop(telefone, None)
                limpar_estados_operacao_carrinho_whatsapp(telefone)
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
                    "estoque insuficiente no carrinho",
                ):
                    clientes_aguardando_confirmacao.pop(telefone, None)
                if acao_exibicao == "produto indisponível":
                    clientes_produto_em_contexto.pop(telefone, None)
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
                    clientes_produto_em_contexto.pop(telefone, None)
            elif telefone in clientes_aguardando_confirmacao_limpar_carrinho:
                (
                    texto_resposta,
                    acao_exibicao,
                ) = interpretar_limpeza_carrinho_whatsapp(mensagem, cliente)
                if acao_exibicao in (
                    "carrinho limpo",
                    "carrinho vazio",
                    "limpeza do carrinho cancelada",
                ):
                    clientes_aguardando_confirmacao_limpar_carrinho.discard(
                        telefone
                    )
            elif telefone in clientes_aguardando_remocao_carrinho:
                ids_itens = clientes_aguardando_remocao_carrinho[telefone]
                (
                    texto_resposta,
                    acao_exibicao,
                ) = interpretar_remocao_item_carrinho_whatsapp(
                    mensagem,
                    ids_itens,
                    cliente,
                )
                if acao_exibicao in (
                    "carrinho enviado",
                    "carrinho vazio",
                    "operação do carrinho cancelada",
                    "item não encontrado no carrinho",
                ):
                    clientes_aguardando_remocao_carrinho.pop(telefone, None)
            elif telefone in clientes_aguardando_nova_quantidade:
                item_id_alteracao = clientes_aguardando_nova_quantidade[telefone]
                (
                    texto_resposta,
                    acao_exibicao,
                ) = interpretar_nova_quantidade_carrinho_whatsapp(
                    mensagem,
                    item_id_alteracao,
                    cliente,
                )
                if acao_exibicao in (
                    "carrinho enviado",
                    "carrinho vazio",
                    "operação do carrinho cancelada",
                    "item não encontrado no carrinho",
                    "estoque insuficiente no carrinho",
                ):
                    clientes_aguardando_nova_quantidade.pop(telefone, None)
            elif telefone in clientes_aguardando_item_alteracao:
                ids_itens = clientes_aguardando_item_alteracao[telefone]
                (
                    texto_resposta,
                    acao_exibicao,
                    item_id_alteracao,
                ) = interpretar_item_alteracao_carrinho_whatsapp(
                    mensagem,
                    ids_itens,
                )
                if acao_exibicao == "aguardando nova quantidade":
                    clientes_aguardando_item_alteracao.pop(telefone, None)
                    clientes_aguardando_nova_quantidade[telefone] = (
                        item_id_alteracao
                    )
                elif acao_exibicao in (
                    "operação do carrinho cancelada",
                    "item alteração inválido",
                ):
                    if acao_exibicao == "operação do carrinho cancelada":
                        clientes_aguardando_item_alteracao.pop(telefone, None)
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
                    clientes_produto_em_contexto[telefone] = (
                        produto_id_selecionado
                    )
                    # Foto primeiro; o texto da quantidade segue abaixo.
                    tentar_enviar_foto_produto_waha(
                        telefone,
                        produto_id_selecionado,
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
                    "estoque insuficiente para finalizar",
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
                elif intencao == "buscar_categoria":
                    chave_categoria = identificar_categoria_whatsapp(mensagem)
                    texto_resposta, acao_exibicao, ids_catalogo = (
                        montar_catalogo_categoria_whatsapp(chave_categoria)
                    )
                    if ids_catalogo:
                        clientes_aguardando_produto[telefone] = ids_catalogo
                    else:
                        clientes_aguardando_produto.pop(telefone, None)
                elif intencao == "consultar_preco":
                    produto_id_contexto = clientes_produto_em_contexto.get(
                        telefone
                    )
                    texto_resposta, acao_exibicao = (
                        montar_consulta_preco_whatsapp(produto_id_contexto)
                    )
                elif intencao == "consultar_estoque":
                    produto_id_contexto = clientes_produto_em_contexto.get(
                        telefone
                    )
                    texto_resposta, acao_exibicao = (
                        montar_consulta_estoque_whatsapp(produto_id_contexto)
                    )
                elif intencao == "detalhar_produto":
                    produto_id_contexto = clientes_produto_em_contexto.get(
                        telefone
                    )
                    texto_resposta, acao_exibicao = (
                        montar_detalhes_produto_whatsapp(produto_id_contexto)
                    )
                elif intencao == "ver_carrinho":
                    texto_resposta, acao_exibicao, _ids_carrinho = (
                        montar_carrinho_whatsapp(cliente)
                    )
                elif intencao == "adicionar_carrinho":
                    texto_resposta, acao_exibicao = (
                        iniciar_quantidade_produto_contexto_whatsapp(telefone)
                    )
                elif intencao == "continuar_comprando":
                    limpar_estados_operacao_carrinho_whatsapp(telefone)
                    texto_resposta, acao_exibicao, ids_catalogo = (
                        montar_catalogo_whatsapp()
                    )
                    if ids_catalogo:
                        clientes_aguardando_produto[telefone] = ids_catalogo
                    else:
                        clientes_aguardando_produto.pop(telefone, None)
                elif intencao == "remover_item":
                    limpar_estados_operacao_carrinho_whatsapp(telefone)
                    clientes_aguardando_produto.pop(telefone, None)
                    (
                        texto_resposta,
                        acao_exibicao,
                        ids_itens,
                    ) = iniciar_remocao_item_carrinho_whatsapp(cliente)
                    if ids_itens:
                        clientes_aguardando_remocao_carrinho[telefone] = (
                            ids_itens
                        )
                elif intencao == "alterar_quantidade":
                    limpar_estados_operacao_carrinho_whatsapp(telefone)
                    clientes_aguardando_produto.pop(telefone, None)
                    (
                        texto_resposta,
                        acao_exibicao,
                        ids_itens,
                    ) = iniciar_alteracao_quantidade_carrinho_whatsapp(cliente)
                    if ids_itens:
                        clientes_aguardando_item_alteracao[telefone] = (
                            ids_itens
                        )
                elif intencao == "limpar_carrinho":
                    limpar_estados_operacao_carrinho_whatsapp(telefone)
                    texto_resposta, acao_exibicao = (
                        iniciar_limpeza_carrinho_whatsapp(cliente)
                    )
                    if acao_exibicao == "aguardando confirmação limpar carrinho":
                        clientes_aguardando_confirmacao_limpar_carrinho.add(
                            telefone
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
