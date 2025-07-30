from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    wallet_address = models.CharField(max_length=42, unique=True)

    def __str__(self):
        return f"{self.user.username} – {self.wallet_address}"
