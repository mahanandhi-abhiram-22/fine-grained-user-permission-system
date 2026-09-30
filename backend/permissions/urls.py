from django.urls import path
from .views import ManagePermissionsView, PermissionAdminOptionsView, UserPermissionsView

urlpatterns = [
    path('me/', UserPermissionsView.as_view(), name='user-permissions'),
    path('manage/', PermissionAdminOptionsView.as_view(), name='permission-admin-options'),
    path('assign/', ManagePermissionsView.as_view(), name='assign-permissions'),
]
