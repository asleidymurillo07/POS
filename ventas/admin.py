from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Producto, Venta, DetalleVenta


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    # Cambiamos 'codigo_barras' por 'codigo' y 'precio' por 'precio_costo' y 'precio_venta'
    list_display = ('id', 'nombre', 'codigo', 'precio_costo', 'precio_venta', 'stock')
    search_fields = ('nombre', 'codigo')

class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'total')
    inlines = [DetalleVentaInline]