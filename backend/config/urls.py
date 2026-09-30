from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    path('api/permissions/', include('permissions.urls')),
    path('api/employees/', include('employees.urls')),

    # OpenAPI schema and Swagger UI.
    #
    # The assignment requires authentication on every endpoint except login, so
    # these routes are NOT public. No permission_classes override is passed here,
    # so access falls through to SPECTACULAR_SETTINGS['SERVE_PERMISSIONS'],
    # which is rest_framework.permissions.IsAuthenticated. Schema generation is
    # unaffected; only access to the result is gated. Authenticated users make
    # requests from the Swagger UI with the "Authorize" button, which uses
    # SPECTACULAR_SETTINGS['SERVE_AUTHENTICATION'] (JWTAuthentication).
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]