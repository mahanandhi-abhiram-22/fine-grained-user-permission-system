from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

# The assignment defines permission codes as unique uppercase strings, and the
# authorization layer compares against exactly these values, so enforce the
# character set in the model rather than relying on the seed command alone.
UPPERCASE_CODE_VALIDATOR = RegexValidator(
    regex=r'^[A-Z0-9_]+$',
    message='Permission and module codes must be uppercase letters, digits, and underscores only.',
)


class Module(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True, validators=[UPPERCASE_CODE_VALIDATOR])
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Function(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='functions')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True, validators=[UPPERCASE_CODE_VALIDATOR])
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
