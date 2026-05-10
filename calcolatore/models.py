from django.db import models
from django.contrib.auth.models import User

class Dataset(models.Model):
    """Dataset inserito dall'utente (tempi + tensioni)."""
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='datasets')
    csv_name          = models.CharField(max_length=255, help_text="Nome del csv")
    step             = models.FloatField(help_text="Passo tra i campioni (es. 0.02 s)")
    time_values   = models.JSONField(help_text="Lista dei valori di tempo [0, 0.02, ...]")
    voltage_values = models.JSONField(help_text="Lista dei valori di tensione [0, 0.1, ...]")
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def n(self):
        """Numero di intervalli."""
        return len(self.time_values) - 1

class Calculation(models.Model):
    dataset           = models.OneToOneField(Dataset, on_delete=models.CASCADE, related_name='calculation')
    rects             = models.JSONField()
    trapezius          = models.JSONField()
    simpson            = models.JSONField()
    result_rectangles = models.FloatField()
    result_trapezius  = models.FloatField()
    result_simpson    = models.FloatField()
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"rect:{self.result_rectangles} trap:{self.result_trapezius} simp:{self.result_simpson}"