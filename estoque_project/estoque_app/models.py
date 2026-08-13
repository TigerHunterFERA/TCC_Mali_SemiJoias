# from django.db import models

# # Create your models here.

# class Usuario(models.Model):
#     nome = models.CharField(max_length=100)
#     email = models.EmailField(unique=True)
#     senha = models.CharField(max_length=255)
#     tipo = models.CharField(max_length=10, choices=[('admin','Admin'),('cliente','Cliente')], default='cliente')
#     criado_em = models.DateTimeField(auto_now_add=True)

# class Produto(models.Model):
#     nome = models.CharField(max_length=100)
#     descricao = models.TextField(blank=True, null=True)
#     preco = models.DecimalField(max_digits=10, decimal_places=2)
#     estoque = models.IntegerField()
#     tipo = models.CharField(max_length=50, blank=True, null=True)
#     categoria = models.CharField(max_length=50, blank=True, null=True)
#     criado_em = models.DateTimeField(auto_now_add=True)

# class Pedido(models.Model):
#     usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
#     data_pedido = models.DateTimeField(auto_now_add=True)
#     status = models.CharField(max_length=10, choices=[('pendente','Pendente'),('pago','Pago'),('cancelado','Cancelado')], default='pendente')

# class ItemPedido(models.Model):
#     pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
#     produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
#     quantidade = models.IntegerField()
#     preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

from django.db import models

class Usuario(models.Model):
    nome = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    senha = models.CharField(max_length=255)
    tipo = models.CharField(max_length=10, choices=[('admin','Admin'),('cliente','Cliente')], default='cliente')
    # Preparação para identificação futura por WhatsApp (opcional nos usuários antigos)
    telefone = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = 'usuarios'

# Tipos de banho reutilizáveis (ex.: Ouro, Prata)
class TipoBanho(models.Model):
    nome = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "tipos_banho"

    def __str__(self):
        return self.nome

class Produto(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    estoque = models.IntegerField()
    tipo = models.CharField(max_length=50, blank=True, null=True)
    categoria = models.CharField(max_length=50, blank=True, null=True)
    # Peso em gramas (opcional para não quebrar produtos antigos)
    peso = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    banho = models.ForeignKey(
        TipoBanho,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'produtos'

    def __str__(self):
        return self.nome


class MovimentacaoEstoque(models.Model):
    """Histórico simples de entradas e saídas de estoque."""

    TIPO_ENTRADA = "entrada"
    TIPO_SAIDA = "saida"
    TIPOS = [
        (TIPO_ENTRADA, "Entrada"),
        (TIPO_SAIDA, "Saída"),
    ]

    produto = models.ForeignKey(
        Produto,
        on_delete=models.PROTECT,
        related_name="movimentacoes",
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)
    quantidade = models.PositiveIntegerField()
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "movimentacoes_estoque"

    def __str__(self):
        return f"{self.tipo} - {self.produto.nome} ({self.quantidade})"


class Pedido(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT)#on_delete=models.PROTECT
    data_pedido = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=25,
        choices=[
            ('pendente', 'Pendente'),
            ('aguardando_pagamento', 'Aguardando pagamento'),
            ('pago', 'Pago'),
            ('cancelado', 'Cancelado'),
        ],
        default='pendente',
    )

    class Meta:
        db_table = 'pedidos'

class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField() #quantidade = models.IntegerField()
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'itens_pedido'