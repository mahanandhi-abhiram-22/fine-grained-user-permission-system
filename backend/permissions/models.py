from django.conf import settings
from django.db import models


class Module(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Function(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='functions')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.module.code}.{self.code}"


class UserFunction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_functions')
    function = models.ForeignKey(Function, on_delete=models.CASCADE, related_name='user_assignments')
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='granted_permissions')

    class Meta:
        unique_together = ('user', 'function')
        ordering = ['function__code']

    def __str__(self):
        return f"{self.user.email} - {self.function.code}"
