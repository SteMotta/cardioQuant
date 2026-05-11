import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username=os.environ.get('ADMIN_USERNAME', 'admin'),
                password=os.environ.get('ADMIN_PASSWORD'),
            )
            self.stdout.write('Superuser creato')
        else:
            self.stdout.write('Superuser già esistente')