from django import forms
from .models import Cliente, Producto, Categoria

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['codigo', 'nombre', 'categoria', 'proveedor', 'precio_costo', 'precio_venta', 'stock', 'es_granel']
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-xs font-semibold text-gray-800 focus:outline-none focus:border-blue-500',
                'placeholder': 'Código de barras (Opcional)'
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-xs font-semibold text-gray-800 focus:outline-none focus:border-blue-500',
                'placeholder': 'Ej: Ruffles Queso 50g'
            }),
            'categoria': forms.Select(attrs={
                'class': 'w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-xs font-semibold text-gray-800 focus:outline-none focus:border-blue-500'
            }),
            'proveedor': forms.Select(attrs={
                'class': 'w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-xs font-semibold text-gray-800 focus:outline-none focus:border-blue-500'
            }),
            'precio_costo': forms.NumberInput(attrs={
                'class': 'w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-xs font-semibold text-gray-800 focus:outline-none focus:border-blue-500',
                'step': '0.50'
            }),
            'precio_venta': forms.NumberInput(attrs={
                'class': 'w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-xs font-semibold text-gray-800 focus:outline-none focus:border-blue-500',
                'step': '0.50'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-xs font-semibold text-gray-800 focus:outline-none focus:border-blue-500',
                'step': '0.001'
            }),
            'es_granel': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
        }
class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'telefono', 'email', 'direccion']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-xs font-semibold text-gray-800 focus:outline-none focus:border-blue-500 focus:bg-white transition',
                'placeholder': 'Nombre completo del cliente'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-xs font-semibold text-gray-800 focus:outline-none focus:border-blue-500 focus:bg-white transition',
                'placeholder': 'Número telefónico'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-xs font-semibold text-gray-800 focus:outline-none focus:border-blue-500 focus:bg-white transition',
                'placeholder': 'correo@ejemplo.com'
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-xs font-semibold text-gray-800 focus:outline-none focus:border-blue-500 focus:bg-white transition',
                'rows': 3,
                'placeholder': 'Dirección completa'
            }),
        }