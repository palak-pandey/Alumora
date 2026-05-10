from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError 


class Institution(models.Model):
    name = models.CharField(max_length=200)
    address = models.TextField()

    def __str__(self):
         return self.name




class User(AbstractUser):
    ROLE_CHOICES = [
        ('SUPER_ADMIN', 'Super Admin'),
        ('ADMIN', 'Institution Admin'),
        ('FACULTY', 'Faculty'),
        ('STUDENT', 'Student'),
        ('ALUMNI', 'Alumni'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_verified = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add= True)
    updated_at = models.DateTimeField(auto_now= True)
    

    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )


#Student Profile. **************************************************************************************************
class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete= models.CASCADE, related_name= 'student_profile')
    enrollment_number = models.CharField(max_length =50, null = True, blank = True)
    department = models.CharField(max_length = 100, null = True, blank = True)
    batch_year = models.CharField(max_length=20, null=True, blank=True)
    bio = models.TextField(blank=True, null=True)
    skills = models.CharField(max_length=255, blank=True, null=True)
    about = models.TextField(blank=True, null=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    cover_photo = models.ImageField(upload_to='cover_photos/', null=True, blank=True)
    
    
    
    def __str__(self):
        return f"Student Profile - {self.user.username}"
    



#Faculty profile *************************************************************************************************
class FacultyProfile(models.Model):
    user = models.OneToOneField(User, on_delete= models.CASCADE, related_name='faculty_profile')
    department =models.CharField(max_length=100, null = True, blank = True) 
    designation = models.CharField(max_length=100, null = True, blank = True)

    def __str__(self):
        return f"Faculty Profile - {self.user.username}"
    



#Alumni Profile ************************************************************************************************
class AlumniProfile(models.Model):
    user =models.OneToOneField(User, on_delete= models.CASCADE, related_name='alumni_profile')

    graduation_year= models.IntegerField(null = True, blank = True)
    degree = models.CharField(max_length=100, null = True, blank= True)
    current_company = models.CharField(max_length= 200, blank= True)
    job_title = models.CharField(max_length= 200, blank= True)

    mentorship_available = models.BooleanField(default= False)
    

    def __str__(self):
        return f"Alumni Profile - {self.user.username}"
    



#****************************************  Verification Workflow *************************************************
class VerificationRequest(models.Model):
    
    STATUS_CHOICES = [
        ('PENDING','Pending'),
        ('FACULTY_APPROVED', 'Faculty Approved'),
        ('ADMIN_APPROVED', 'Admin Approved'),
        ('VERIFIED','Verified'),
        ('REJECTED','Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_requests')
    
    faculty_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='faculty_verified_users'
    )
    
    admin_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_verified_users'
    )
    
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Verification - {self.user.username} ({self.status})"

# *************************************** Mentorship Request System ******************************************************
class MentorshipRequest(models.Model):

    STATUS_CHOICES = [('PENDING', 'Pending'), ('ACCEPTED', 'Accepted'), ('REJECTED','Rejected'),]
    student = models.ForeignKey(User, on_delete = models.CASCADE, related_name= 'sent_requests')
    alumni = models.ForeignKey(User, on_delete = models.CASCADE, related_name= 'received_requests')
    status = models.CharField(max_length =20, choices = STATUS_CHOICES, default= 'PENDING')

    created_at = models.DateTimeField(auto_now_add= True)

    


    def clean(self):
        if self.student == self.alumni:
            raise ValidationError("You cannot send a mentorship request to yourself.")

        if self.student.role != 'STUDENT':
            raise ValidationError("Only students can send mentorship requests.")

        if self.alumni.role != 'ALUMNI':
            raise ValidationError("Mentorship requests can be sent to alumni only.")

        if not hasattr(self.alumni, 'alumni_profile'):
            raise ValidationError("Invalid alumni profile.")

        if not self.alumni.alumni_profile.mentorship_available:
            raise ValidationError("This alumni is not available for mentorship.")

        if self.alumni.is_suspended:
            raise ValidationError("This alumni is currently suspended.")

        if self.student.is_suspended:
            raise ValidationError("Your account is suspended.")

        # Prevent duplicate pending request
        if MentorshipRequest.objects.filter(
        student=self.student,
        alumni=self.alumni,
        status='PENDING').exists():
            raise ValidationError("You already have a pending request with this alumni.")

        # Prevent student from taking mentorship from another mentor.
        if MentorshipRequest.objects.filter(
        student=self.student,
        status="ACCEPTED").exists():
            raise ValidationError("You already have a mentor.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.student.username} - {self.alumni.username} ({self.status})"



    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'alumni'],
                condition=models.Q(status='PENDING'),
                name='unique_pending_request'
            )
        ]


# ****************************************** Suspension log **************************************************************
class SuspensionLog(models.Model):
    user = models.ForeignKey(User, on_delete= models.CASCADE, related_name= 'suspension_logs')
    suspended_by = models.ForeignKey(User, on_delete = models.SET_NULL, null= True, related_name= 'suspensions_done')
    reason = models.TextField()
    is_active = models.BooleanField(default = True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Suspension - {self.user.username}"


#--------------------------------------- Chat system --------------------------------------------------------------------

class Conversation(models.Model):
    participants = models.ManyToManyField(User)
    updated_at = models.DateTimeField(auto_now=True)  
    is_accepted = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Conversation {self.id}"

    def clean(self):
        if self.participants.count() != 2:
            raise ValidationError("Only 2 participants allowed")

class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username}: {self.content[:20]}"

    class Meta:
        ordering = ['created_at']  

