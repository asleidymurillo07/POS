import json
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.conf import settings


class Proveedor(models.Model):
    nombre = models.CharField(max_length=150)
    contacto = models.CharField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(max_length=100, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


from django.db import models

class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    codigo = models.CharField(max_length=50, blank=True, null=True, unique=True)
    nombre = models.CharField(max_length=150)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos',
        help_text="Marca o Departamento (Ej: Sabritas, Barcel, Coca Cola, Verduras)"
    )
    proveedor = models.ForeignKey(
        'Proveedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos'
    )
    precio_costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    stock = models.DecimalField(max_digits=10, decimal_places=3, default=0.000)
    es_granel = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['nombre']

    def __str__(self):
        cat = f" [{self.categoria.nombre}]" if self.categoria else ""
        return f"{self.nombre}{cat}"
class CorteCaja(models.Model):
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    cerrado = models.BooleanField(default=False)
    
    total_ventas = models.IntegerField(default=0)
    total_ingresos = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    ganancia_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = "Corte de Caja"
        verbose_name_plural = "Cortes de Caja"
        ordering = ['-fecha_inicio']

    def __str__(self):
        estado = "Cerrado" if self.cerrado else "Abierto"
        return f"Corte #{self.id} - {self.fecha_inicio.strftime('%d/%m/%Y %H:%M')} ({estado})"


class Venta(models.Model):
    METODOS_PAGO = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia'),
    ]

    cajero = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventas'
    )
    cliente = models.ForeignKey(
        'Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventas'
    )
    corte = models.ForeignKey(
        'CorteCaja',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventas'
    )
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    metodo_pago = models.CharField(
        max_length=20,
        choices=METODOS_PAGO,
        default='efectivo'
    )
    referencia_pago = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Número de autorización, voucher de tarjeta o folio/rastreo de transferencia"
    )

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-fecha']

    def __str__(self):
        cajero_nombre = self.cajero.username if self.cajero else "Desconocido"
        cliente_nombre = self.cliente.nombre if self.cliente else "Público General"
        return f"Venta #{self.id} - {cajero_nombre} - Cliente: {cliente_nombre} - ${self.total}"


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey('Producto', on_delete=models.PROTECT, related_name='ventas_detalles')
    
    # Captura histórica de precios al momento exacto de la venta
    precio_costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.DecimalField(max_digits=10, decimal_places=3)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Detalle de Venta"
        verbose_name_plural = "Detalles de Venta"

    def save(self, *args, **kwargs):
        # Auto-captura del precio de costo actual del producto si no se asignó explícitamente
        if not self.precio_costo and self.producto:
            self.precio_costo = self.producto.precio_costo
        # Auto-cálculo del subtotal
        if self.precio_unitario and self.cantidad:
            self.subtotal = Decimal(str(self.precio_unitario)) * Decimal(str(self.cantidad))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} en Venta #{self.venta.id}"

    @property
    def ganancia_linea(self):
        """Calcula la ganancia generada específicamente por este artículo."""
        return (self.precio_unitario - self.precio_costo) * self.cantidad
class Cliente(models.Model):
    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre