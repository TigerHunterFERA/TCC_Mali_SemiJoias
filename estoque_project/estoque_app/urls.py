from django.urls import path
from . import views

urlpatterns = [
    path("", views.login, name="login"), 
    path("login/", views.login, name="login"),
    path("inicio/", views.pagina_inicial, name="pagina_inicial"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("produtos/", views.listar_produtos, name="produtos"), 
    path("adicionar/", views.adicionar_produto, name="adicionar"),
    path("editar/<int:produto_id>/", views.editar_produto, name="editar"),
    path("remover/<int:produto_id>/", views.remover_produto, name="remover"),
    path(
        "movimentar/<int:produto_id>/",
        views.movimentar_estoque,
        name="movimentar",
    ),
    path("movimentacoes/", views.listar_movimentacoes, name="movimentacoes"),
    path("pedidos/", views.listar_pedidos, name="pedidos"),
    path("clientes/", views.listar_clientes, name="clientes"),
    path(
        "clientes/<int:cliente_id>/telefone/",
        views.editar_telefone_cliente,
        name="editar_telefone_cliente",
    ),
    # pedidos/novo/ deve ficar ANTES de pedidos/<int:pedido_id>/
    path("pedidos/novo/", views.criar_pedido, name="novo_pedido"),
    path(
        "pedidos/<int:pedido_id>/adicionar-item/",
        views.adicionar_item_pedido,
        name="adicionar_item_pedido",
    ),
    # finalizar/ deve ficar ANTES de pedidos/<int:pedido_id>/
    path(
        "pedidos/<int:pedido_id>/finalizar/",
        views.finalizar_pedido,
        name="finalizar_pedido",
    ),
    path(
        "pedidos/<int:pedido_id>/confirmar-pagamento/",
        views.confirmar_pagamento,
        name="confirmar_pagamento",
    ),
    path(
        "pedidos/<int:pedido_id>/cancelar/",
        views.cancelar_pedido,
        name="cancelar_pedido",
    ),
    path(
        "pedidos/<int:pedido_id>/",
        views.detalhe_pedido,
        name="detalhe_pedido",
    ),
    path("waha/teste/", views.teste_waha, name="teste_waha"),
    path("waha/webhook/", views.webhook_waha, name="webhook_waha"),
]
