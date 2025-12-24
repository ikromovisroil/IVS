from django.db import models
from main.models import Employee

class AuditLog(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True)
    ACTIONS = (
        ("login", "Login"),
        ("logout", "Logout"),
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
    )
    action = models.CharField(max_length=20, choices=ACTIONS)
    model = models.CharField(max_length=100)
    object_id = models.PositiveIntegerField(null=True)
    path = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    ip = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    description = models.TextField(blank=True)
    date_creat = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} {self.model}#{self.object_id} by {self.employee}"

    class Meta:
        db_table = 'auditLog'
        verbose_name = "Harakat"
        verbose_name_plural = "Harakatlar"