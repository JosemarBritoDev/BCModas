"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from apps.clientes import views as clientes_views
from apps.pedidos import views as pedidos_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', pedidos_views.catalogo_home, name='catalogo_home'),
    path(
        'catalogo/<slug:slug>/',
        pedidos_views.catalogo_publico,
        name='catalogo_publico',
    ),
    path(
        'catalogo/<slug:slug>/login/',
        clientes_views.catalogo_cliente_login,
        name='catalogo_cliente_login',
    ),
    path(
        'catalogo/<slug:slug>/cadastro/',
        clientes_views.catalogo_cliente_cadastro,
        name='catalogo_cliente_cadastro',
    ),
    path(
        'catalogo/<slug:slug>/sair/',
        clientes_views.catalogo_cliente_logout,
        name='catalogo_cliente_logout',
    ),
    path(
        'catalogo/<slug:slug>/termos/',
        pedidos_views.catalogo_legal,
        name='catalogo_legal',
    ),
    path(
        'catalogo/<slug:slug>/finalizar/',
        pedidos_views.catalogo_checkout,
        name='catalogo_checkout',
    ),
    path(
        'catalogo/<slug:slug>/pedido/<int:pedido_id>/',
        pedidos_views.catalogo_pedido_enviado,
        name='catalogo_pedido_enviado',
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
