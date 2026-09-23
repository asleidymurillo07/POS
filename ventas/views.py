import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum, F, ExpressionWrapper, DecimalField
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.core.serializers.json import DjangoJSONEncoder

from .models import CorteCaja, DetalleVenta, Producto, Proveedor, Venta, Cliente, Categoria
from .forms import ClienteForm


# ==========================================
# AUTENTICACIÓN
# ==========================================

def login_view(request):
    if request.user.is_authenticated:
        return redirect('pos')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            usuario = form.get_user()
            login(request, usuario)
            next_url = request.GET.get('next', 'pos')
            return redirect(next_url)
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = AuthenticationForm()

    return render(request, 'ventas/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def obtener_corte_activo():
    """ Obtiene el corte activo de la caja o crea uno nuevo de ser necesario. """
    corte_activo = CorteCaja.objects.filter(cerrado=False).order_by('id').last()
    if not corte_activo:
        corte_activo = CorteCaja.objects.create(fecha_inicio=timezone.now(), cerrado=False)
    return corte_activo


# ==========================================
# PUNTO DE VENTA (POS) Y VENTAS
# ==========================================

@login_required
def pos_view(request):
    productos = Producto.objects.filter(stock__gt=0).select_related('categoria').only(
        'id', 'nombre', 'precio_venta', 'stock', 'codigo', 'es_granel', 'categoria'
    ).order_by('nombre')
    
    clientes = Cliente.objects.all().order_by('nombre')
    
    return render(request, 'ventas/pos.html', {
        'productos': productos,
        'clientes': clientes
    })


@login_required
@transaction.atomic
def procesar_venta_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            cliente_id = data.get('cliente_id')
            metodo_pago = data.get('metodo_pago', 'efectivo')
            referencia_pago = data.get('referencia_pago', '').strip()
            
            if not items:
                return JsonResponse({'success': False, 'error': 'El carrito está vacío'})
            
            corte_activo = obtener_corte_activo()
            cajero_actual = request.user if request.user.is_authenticated else None
            cliente_obj = Cliente.objects.filter(id=cliente_id).first() if cliente_id else None
            
            # Crear la Venta con cliente, método de pago y referencia
            venta = Venta.objects.create(
                total=Decimal('0.00'),
                cajero=cajero_actual,
                cliente=cliente_obj,
                corte=corte_activo,
                metodo_pago=metodo_pago,
                referencia_pago=referencia_pago if referencia_pago else None
            )
            
            total_acumulado = Decimal('0.00')

            # Guardar detalles y descontar stock
            for item in items:
                producto = Producto.objects.select_for_update().get(id=item['id'])
                cantidad = Decimal(str(item['cantidad']))
                
                if producto.stock < cantidad:
                    transaction.set_rollback(True)
                    return JsonResponse({
                        'success': False, 
                        'error': f'Stock insuficiente para {producto.nombre}. Disponible: {producto.stock}'
                    })

                precio_unitario = producto.precio_venta
                subtotal = precio_unitario * cantidad
                total_acumulado += subtotal

                DetalleVenta.objects.create(
                    venta=venta,
                    producto=producto,
                    precio_costo=producto.precio_costo,
                    precio_unitario=precio_unitario,
                    cantidad=cantidad,
                    subtotal=subtotal
                )

                Producto.objects.filter(id=producto.id).update(stock=F('stock') - cantidad)

            venta.total = total_acumulado
            venta.save()

            ticket_url = reverse('ver_ticket', args=[venta.id])
            return JsonResponse({'success': True, 'redirect_url': ticket_url})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@login_required
def ver_ticket_view(request, venta_id):
    """Vista dedicada exclusivamente para mostrar el ticket centrado"""
    venta = get_object_or_404(Venta, id=venta_id)
    detalles = venta.detalles.select_related('producto').all()
    
    context = {
        'venta': venta,
        'detalles': detalles
    }
    return render(request, 'ventas/ticket_standalone.html', context)


@login_required
def detalle_ticket_view(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    detalles = venta.detalles.select_related('producto').all()
    
    context = {
        'venta': venta,
        'detalles': detalles,
    }
    return render(request, 'ventas/detalle_ticket.html', context)


@login_required
def detalle_venta_api(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('producto')

    detalles_data = [
        {
            'producto': item.producto.nombre,
            'cantidad': float(item.cantidad),
            'precio_unitario': float(item.precio_unitario),
            'subtotal': float(item.subtotal),
        }
        for item in detalles
    ]

    return JsonResponse({
        'success': True,
        'venta_id': venta.id,
        'fecha': venta.fecha.strftime('%d/%m/%Y %H:%M:%S'),
        'total': float(venta.total),
        'detalles': detalles_data,
    })


@login_required
@transaction.atomic
def finalizar_venta(request):
    """Soporte para cobro mediante sesión HTTP (fallback tradicional)"""
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('pos')

    corte_activo = obtener_corte_activo()
    cajero_actual = request.user if request.user.is_authenticated else None
    
    total_venta = Decimal('0.00')
    venta = Venta.objects.create(
        total=Decimal('0.00'), 
        cajero=cajero_actual, 
        corte=corte_activo
    )

    for producto_id, item in cart.items():
        producto = Producto.objects.select_for_update().get(id=producto_id)
        cantidad = Decimal(str(item['cantidad']))

        precio_unitario = producto.precio_venta
        subtotal = precio_unitario * cantidad
        total_venta += subtotal

        DetalleVenta.objects.create(
            venta=venta,
            producto=producto,
            precio_costo=producto.precio_costo,
            precio_unitario=precio_unitario,
            cantidad=cantidad,
            subtotal=subtotal
        )
        
        Producto.objects.filter(id=producto.id).update(stock=F('stock') - cantidad)

    venta.total = total_venta
    venta.save()

    request.session['cart'] = {}
    request.session.modified = True

    return redirect('ver_ticket', venta_id=venta.id)


# ==========================================
# GESTIÓN DE PRODUCTOS Y CATEGORÍAS
# ==========================================

@login_required
def productos_view(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        precio_costo = request.POST.get('precio_costo')
        precio_venta = request.POST.get('precio_venta')
        stock = request.POST.get('stock')
        codigo = request.POST.get('codigo', '').strip()
        es_granel = request.POST.get('es_granel') == 'on'
        proveedor_id = request.POST.get('proveedor')
        categoria_id = request.POST.get('categoria')

        proveedor = Proveedor.objects.get(id=proveedor_id) if proveedor_id else None
        categoria = Categoria.objects.get(id=categoria_id) if categoria_id else None

        if nombre and precio_costo and precio_venta and stock:
            Producto.objects.create(
                nombre=nombre,
                precio_costo=Decimal(precio_costo),
                precio_venta=Decimal(precio_venta),
                stock=Decimal(stock),
                codigo=codigo if codigo else None,
                es_granel=es_granel,
                proveedor=proveedor,
                categoria=categoria
            )
            messages.success(request, 'Producto guardado correctamente.')
            return redirect('productos')

    query = request.GET.get('q', '').strip()
    proveedor_id = request.GET.get('proveedor', '')
    categoria_id = request.GET.get('categoria', '')

    productos = Producto.objects.select_related('proveedor', 'categoria').all().order_by('-id')

    if query:
        productos = productos.filter(Q(nombre__icontains=query) | Q(codigo__icontains=query))

    if proveedor_id:
        productos = productos.filter(proveedor_id=proveedor_id)

    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)

    proveedores = Proveedor.objects.all()
    categorias = Categoria.objects.all()

    context = {
        'productos': productos,
        'proveedores': proveedores,
        'categorias': categorias,
        'query': query,
        'proveedor_id': proveedor_id,
        'categoria_id': categoria_id,
    }
    return render(request, 'ventas/productos.html', context)


@login_required
def editar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip()
        producto.codigo = codigo if codigo else None
        producto.nombre = request.POST.get('nombre')
        producto.precio_costo = Decimal(request.POST.get('precio_costo', producto.precio_costo))
        producto.precio_venta = Decimal(request.POST.get('precio_venta', producto.precio_venta))
        producto.stock = Decimal(request.POST.get('stock', producto.stock))
        producto.es_granel = request.POST.get('es_granel') == 'on'

        proveedor_id = request.POST.get('proveedor')
        categoria_id = request.POST.get('categoria')

        producto.proveedor = Proveedor.objects.get(id=proveedor_id) if proveedor_id else None
        producto.categoria = Categoria.objects.get(id=categoria_id) if categoria_id else None

        producto.save()
        messages.success(request, 'Producto actualizado correctamente.')

    return redirect('productos')


@login_required
def eliminar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    producto.delete()
    messages.success(request, 'Producto eliminado correctamente.')
    return redirect('productos')


@login_required
def crear_categoria_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre', '').strip()
            
            if not nombre:
                return JsonResponse({'success': False, 'error': 'El nombre es obligatorio.'})
            
            categoria, created = Categoria.objects.get_or_create(nombre=nombre)
            
            return JsonResponse({
                'success': True,
                'id': categoria.id,
                'nombre': categoria.nombre,
                'creado': created
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


# ==========================================
# PROVEEDORES
# ==========================================

@login_required
def proveedores_list(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        contacto = request.POST.get('contacto')
        telefono = request.POST.get('telefono')
        email = request.POST.get('email')
        direccion = request.POST.get('direccion')

        if nombre:
            Proveedor.objects.create(
                nombre=nombre,
                contacto=contacto,
                telefono=telefono,
                email=email,
                direccion=direccion
            )
            messages.success(request, 'Proveedor registrado con éxito.')
            return redirect('proveedores')

    query = request.GET.get('q', '').strip()
    proveedores = Proveedor.objects.all().order_by('-fecha_registro')

    if query:
        proveedores = proveedores.filter(Q(nombre__icontains=query) | Q(contacto__icontains=query))

    context = {
        'proveedores': proveedores,
        'query': query,
    }
    return render(request, 'ventas/proveedores.html', context)


@login_required
def eliminar_proveedor(request, id):
    proveedor = get_object_or_404(Proveedor, id=id)
    proveedor.delete()
    messages.success(request, 'Proveedor eliminado correctamente.')
    return redirect('proveedores')


# ==========================================
# CLIENTES
# ==========================================

@login_required
def lista_clientes(request):
    query = request.GET.get('q', '')
    if query:
        clientes = Cliente.objects.filter(nombre__icontains=query)
    else:
        clientes = Cliente.objects.all()
    
    return render(request, 'ventas/clientes_list.html', {
        'clientes': clientes,
        'query': query
    })


@login_required
def crear_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente registrado correctamente.')
            return redirect('lista_clientes')
    else:
        form = ClienteForm()
    
    return render(request, 'ventas/cliente_form.html', {
        'form': form,
        'titulo': 'Registrar Nuevo Cliente'
    })


@login_required
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Información del cliente actualizada.')
            return redirect('lista_clientes')
    else:
        form = ClienteForm(instance=cliente)
    
    return render(request, 'ventas/cliente_form.html', {
        'form': form,
        'titulo': f'Editar Cliente: {cliente.nombre}'
    })


@login_required
def eliminar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        cliente.delete()
        messages.success(request, 'Cliente eliminado exitosamente.')
        return redirect('lista_clientes')
    
    return render(request, 'ventas/cliente_confirm_delete.html', {
        'cliente': cliente
    })


# ==========================================
# DASHBOARD
# ==========================================

@login_required
def dashboard(request):
    hoy = timezone.now().date()
    ayer = hoy - timedelta(days=1)

    ventas_hoy_qs = Venta.objects.filter(fecha__date=hoy)
    ventas_ayer_qs = Venta.objects.filter(fecha__date=ayer)

    ventas_hoy_count = ventas_hoy_qs.count()
    ingresos_hoy = ventas_hoy_qs.aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    ventas_ayer_count = ventas_ayer_qs.count()
    ingresos_ayer = ventas_ayer_qs.aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    dif_ingresos_pct = float((ingresos_hoy - ingresos_ayer) / ingresos_ayer * 100) if ingresos_ayer > 0 else 0.0
    dif_ventas_pct = float((ventas_hoy_count - ventas_ayer_count) / ventas_ayer_count * 100) if ventas_ayer_count > 0 else 0.0

    total_productos = Producto.objects.count()
    productos_bajo_stock = Producto.objects.filter(stock__lte=5)
    productos_bajo_stock_count = productos_bajo_stock.count()
    productos_sin_stock_count = Producto.objects.filter(stock__lte=0).count()

    detalles_hoy = DetalleVenta.objects.filter(venta__in=ventas_hoy_qs).select_related('producto')
    costo_hoy = sum(d.precio_costo * d.cantidad for d in detalles_hoy) if detalles_hoy else Decimal('0.00')
    ganancia_hoy = ingresos_hoy - costo_hoy

    ultimas_ventas = Venta.objects.all().order_by('-fecha')[:10]

    top_productos = (
        DetalleVenta.objects
        .values('producto__nombre')
        .annotate(total_vendido=Sum('cantidad'))
        .order_by('-total_vendido')[:5]
    )

    context = {
        'ventas_hoy': ventas_hoy_count,
        'ingresos_hoy': ingresos_hoy,
        'ganancia_hoy': ganancia_hoy,
        'dif_ingresos_pct': dif_ingresos_pct,
        'dif_ventas_pct': dif_ventas_pct,
        'total_productos': total_productos,
        'productos_bajo_stock_count': productos_bajo_stock_count,
        'productos_sin_stock_count': productos_sin_stock_count,
        'productos_bajo_stock': productos_bajo_stock[:5],
        'ultimas_ventas': ultimas_ventas,
        'top_productos': top_productos,
        'fecha_hoy': hoy,
    }
    return render(request, 'ventas/dashboard.html', context)


# ==========================================
# CORTE DE CAJA
# ==========================================

@login_required
def corte_caja_view(request):
    fecha_filtro = request.GET.get('fecha', '').strip()
    corte_id = request.GET.get('corte_id', '').strip()

    # Manejo del cierre de caja activa por POST
    if request.method == 'POST' and 'cerrar_corte' in request.POST:
        corte_a_cerrar = obtener_corte_activo()
        corte_a_cerrar.cerrado = True
        corte_a_cerrar.fecha_cierre = timezone.now()
        corte_a_cerrar.save()
        
        # Iniciar inmediatamente un nuevo corte activo
        CorteCaja.objects.create(fecha_inicio=timezone.now(), cerrado=False)
        return redirect('corte_caja')

    # Determinar el corte actual a consultar
    corte_actual = None
    if corte_id:
        corte_actual = CorteCaja.objects.filter(id=corte_id).first()
    
    if not corte_actual:
        corte_actual = obtener_corte_activo()

    es_corte_activo = not corte_actual.cerrado

    # Historial de cortes para el selector
    historial_cortes = CorteCaja.objects.all().order_by('-fecha_inicio')
    if fecha_filtro:
        try:
            fecha_obj = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
            historial_cortes = historial_cortes.filter(fecha_inicio__date=fecha_obj)
        except ValueError:
            pass

    # Filtrar ventas correspondientes al corte seleccionado
    ventas = Venta.objects.filter(corte=corte_actual).select_related('cajero', 'cliente').prefetch_related('detalles__producto')

    # Totales Financieros y por Método de Pago
    ingresos_totales = ventas.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    ventas_efectivo = ventas.filter(metodo_pago='efectivo').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    ventas_tarjeta = ventas.filter(metodo_pago='tarjeta').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    ventas_transferencia = ventas.filter(metodo_pago='transferencia').aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    # Desglose de Costo de Mercadería e Inversión
    detalles = DetalleVenta.objects.filter(venta__corte=corte_actual)
    costo_total = detalles.annotate(
        costo_linea=ExpressionWrapper(F('cantidad') * F('precio_costo'), output_field=DecimalField())
    ).aggregate(total_costo=Sum('costo_linea'))['total_costo'] or Decimal('0.00')

    # Ganancia Neta y Métricas Secundarias
    ganancia_total = ingresos_totales - costo_total
    total_ventas_count = ventas.count()
    ticket_promedio = (ingresos_totales / total_ventas_count) if total_ventas_count > 0 else Decimal('0.00')
    margen_ganancia = ((ganancia_total / ingresos_totales) * 100) if ingresos_totales > 0 else Decimal('0.00')

    # Resumen de Productos Vendidos (Top e ítems)
    productos_vendidos = detalles.values(
        'producto__nombre'
    ).annotate(
        total_cantidad=Sum('cantidad'),
        total_recaudado=Sum('subtotal')
    ).order_by('-total_cantidad')

    total_articulos = detalles.aggregate(total_cant=Sum('cantidad'))['total_cant'] or Decimal('0.00')

    # Formatear Lista JSON para Consumo de Modales JavaScript
    ventas_lista = []
    for venta in ventas:
        detalles_lista = []
        for det in venta.detalles.all():
            detalles_lista.append({
                'producto': det.producto.nombre if det.producto else 'Producto eliminado',
                'cantidad': float(det.cantidad),
                'precio': float(det.precio_unitario),
                'subtotal': float(det.subtotal)
            })

        cajero_nombre = venta.cajero.get_full_name() or venta.cajero.username if venta.cajero else "General"
        cliente_nombre = venta.cliente.nombre if venta.cliente else "Público General"
        metodo_display = dict(getattr(Venta, 'METODOS_PAGO', [])).get(venta.metodo_pago, venta.metodo_pago.capitalize())

        ventas_lista.append({
            'id': venta.id,
            'fecha': venta.fecha.strftime('%d/%m/%Y %H:%M:%S'),
            'cajero': cajero_nombre,
            'cliente': cliente_nombre,
            'metodo_pago': metodo_display,
            'referencia': getattr(venta, 'referencia_pago', '') or '',
            'total': float(venta.total),
            'detalles': detalles_lista
        })

    contexto = {
        'corte_actual': corte_actual,
        'es_corte_activo': es_corte_activo,
        'historial_cortes': historial_cortes,
        'fecha_filtro': fecha_filtro,
        'ventas': ventas,
        'ventas_lista': ventas_lista,
        'ingresos_totales': ingresos_totales,
        'ventas_efectivo': ventas_efectivo,
        'ventas_tarjeta': ventas_tarjeta,
        'ventas_transferencia': ventas_transferencia,
        'costo_total': costo_total,
        'ganancia_total': ganancia_total,
        'margen_ganancia': margen_ganancia,
        'ticket_promedio': ticket_promedio,
        'total_ventas_count': total_ventas_count,
        'total_articulos': total_articulos,
        'productos_vendidos': productos_vendidos,
    }

    return render(request, 'ventas/corte_caja.html', contexto)