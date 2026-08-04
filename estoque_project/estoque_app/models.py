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
    criado_em = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = 'usuarios' 

class Produto(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    estoque = models.IntegerField()
    tipo = models.CharField(max_length=50, blank=True, null=True)
    categoria = models.CharField(max_length=50, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'produtos' 

class Pedido(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    data_pedido = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=[('pendente','Pendente'),('pago','Pago'),('cancelado','Cancelado')], default='pendente')

    class Meta:
        db_table = 'pedidos'

class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.IntegerField()
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'itens_pedido'