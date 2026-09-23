from django.contrib import admin
from django.urls import path
from ventas import views

urlpatterns = [
    # Panel de administración de Django
    path('admin/', admin.site.urls),

    # Autenticación
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard y Punto de Venta
    path('', views.dashboard, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('pos/', views.pos_view, name='pos'),

    # API de Procesamiento de Ventas y Tickets
    path('api/procesar-venta/', views.procesar_venta_api, name='procesar_venta_api'),
    path('procesar_venta/', views.procesar_venta_api, name='procesar_venta'), # alias de compatibilidad
    path('finalizar-venta/', views.finalizar_venta, name='finalizar_venta'),
    path('venta/ticket/<int:venta_id>/', views.ver_ticket_view, name='ver_ticket'),
    path('ticket/<int:venta_id>/', views.detalle_ticket_view, name='detalle_ticket'),
    path('api/detalle-venta/<int:venta_id>/', views.detalle_venta_api, name='detalle_venta_api'),

    # Gestión de Productos
    path('productos/', views.productos_view, name='productos'),
    path('productos/crear/', views.productos_view, name='crear_producto'),
    path('productos/editar/<int:pk>/', views.editar_producto, name='editar_producto'),
    path('productos/eliminar/<int:pk>/', views.eliminar_producto, name='eliminar_producto'),
    path('api/categoria/crear/', views.crear_categoria_api, name='crear_categoria_api'),

    # Corte de Caja
    path('corte-caja/', views.corte_caja_view, name='corte_caja'),

    # Proveedores
    path('proveedores/', views.proveedores_list, name='proveedores'),
    path('proveedores/eliminar/<int:id>/', views.eliminar_proveedor, name='eliminar_proveedor'),

    #clientes 
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/crear/', views.crear_cliente, name='crear_cliente'),
    path('clientes/editar/<int:pk>/', views.editar_cliente, name='editar_cliente'),
    path('clientes/eliminar/<int:pk>/', views.eliminar_cliente, name='eliminar_cliente'),
]   