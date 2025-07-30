from django.db import models
from django.conf import settings

class Property(models.Model):
    name = models.CharField(max_length=200)
    symbol = models.CharField(max_length=50)
    crowdfund_address = models.CharField(max_length=42, unique=True)
    goal = models.DecimalField(max_digits=30, decimal_places=18)

    def __str__(self):
        return f"{self.name} ({self.symbol})"

class Investment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=30, decimal_places=18)
    currency = models.CharField(max_length=20, default='MON')
    distributed = models.BooleanField(default=False)
    tx_hash = models.CharField(max_length=66, unique=True)
    block_number = models.BigIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} invested {self.amount} in {self.property.symbol}"
