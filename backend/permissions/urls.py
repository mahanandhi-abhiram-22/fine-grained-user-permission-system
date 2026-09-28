from django.urls import path
from .views import UserPermissionsView, ManagePermissionsView

urlpatterns = [
    path('me/', UserPermissionsView.as_view(), name='user-permissions'),
    path('assign/', ManagePermissionsView.as_view(), name='assign-permissions'),
]
