from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, StudentProfile, FacultyProfile, AlumniProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):

    if created:

        if instance.role == 'STUDENT':
            StudentProfile.objects.get_or_create(user=instance)

        elif instance.role == 'FACULTY':
            FacultyProfile.objects.get_or_create(user=instance)

        elif instance.role == 'ALUMNI':
            AlumniProfile.objects.get_or_create(user=instance)