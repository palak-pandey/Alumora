from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError 
from django.db.models import Q
from django.utils import timezone
import uuid
import random
import string
from django.conf import settings




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
    banned_until = models.DateTimeField(
        null=True, blank=True,
        help_text="Set when an unverified alumni account is banned. "
                  "If still unverified after this date, the account is deleted."
    )
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
    bio = models.TextField(blank=True, null=True)
    about = models.TextField(blank=True, null=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    cover_photo = models.ImageField(upload_to='cover_photos/', null=True, blank=True)
    
    current_designation = models.CharField(max_length=255, blank=True, null=True)
    current_join_year = models.CharField(max_length=50, blank=True, null=True)

    past_company_1 = models.CharField(max_length=255, blank=True, null=True, verbose_name="Past Institution/Company 1")
    past_designation_1 = models.CharField(max_length=255, blank=True, null=True)
    past_timeline_1 = models.CharField(max_length=100, blank=True, null=True)
   
    past_company_2 = models.CharField(max_length=255, blank=True, null=True, verbose_name="Past Institution/Company 2")
    past_designation_2 = models.CharField(max_length=255, blank=True, null=True)
    past_timeline_2 = models.CharField(max_length=100, blank=True, null=True)

    # ── RESEARCH & PUBLICATIONS ──
    research_publications = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Faculty Profile - {self.user.username}"
    

#Alumni Profile ************************************************************************************************
class AlumniProfile(models.Model):
    user =models.OneToOneField(User, on_delete= models.CASCADE, related_name='alumni_profile')
    bio = models.TextField(blank=True, null=True)
    skills = models.CharField(max_length=255, blank=True, null=True)
    about = models.TextField(blank=True, null=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    cover_photo = models.ImageField(upload_to='cover_photos/', null=True, blank=True)

    #work experience
    current_company = models.CharField(max_length= 200, blank= True) 
    job_title = models.CharField(max_length= 200, blank= True)
    current_join_year = models.CharField(max_length=50, blank=True, null=True)
    
    past_company_1 = models.CharField(max_length=255, blank=True, null=True, verbose_name="Past Institution/Company 1")
    past_designation_1 = models.CharField(max_length=255, blank=True, null=True)
    past_timeline_1 = models.CharField(max_length=100, blank=True, null=True)
   
    past_company_2 = models.CharField(max_length=255, blank=True, null=True, verbose_name="Past Institution/Company 2")
    past_designation_2 = models.CharField(max_length=255, blank=True, null=True)
    past_timeline_2 = models.CharField(max_length=100, blank=True, null=True)

   #education 
    recent_degree = models.CharField(max_length=255, blank=True, null=True, verbose_name="Past Degree/Course")
    batch = models.CharField(max_length=100, blank=True, null=True)
    
    past_university1 = models.CharField(max_length=255, blank=True, null=True, verbose_name="Past Institution Name")
    past_degree_course1 = models.CharField(max_length=255, blank=True, null=True, verbose_name="Past Degree/Course")
    batch1= models.CharField(max_length=100, blank=True, null=True)
    
    skills = models.CharField(max_length=255, blank=True, null=True) 
    mentorship_available = models.BooleanField(default= False)
    

    def __str__(self):
        return f"Alumni Profile - {self.user.username}"
    



#****************************************  Verification Workflow *************************************************
class VerificationRequest(models.Model):

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('FACULTY_APPROVED', 'Faculty Approved'),
        ('ADMIN_APPROVED', 'Admin Approved'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='verification_requests'
    )
    
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    father_name = models.CharField(max_length=100)
    degree_course = models.CharField(max_length=200)
    abc_apaar_id = models.CharField(max_length=50, verbose_name="ABC / APAAR ID")
    degree_certificate = models.ImageField(upload_to='verification_documents/')



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

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    rejection_reason = models.TextField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Agar status ADMIN_APPROVED ya VERIFIED par set ho gaya hai (jaise shell se ya admin panel se)
        if self.status in ['ADMIN_APPROVED', 'VERIFIED']:
            # Custom sync logic: User model par is_verified ko True mark karo
            if not self.user.is_verified:
                self.user.is_verified = True
                self.user.save(update_fields=['is_verified'])
                
        super().save(*args, **kwargs)



    # ---------------- VALIDATIONS ---------------- #

    def clean(self):

        # Suspended users cannot request verification
        if self.user.is_suspended:
            raise ValidationError(
                "Suspended users cannot request verification."
            )

        # Prevent duplicate pending request
        if VerificationRequest.objects.filter(
            user=self.user,
            status='PENDING'
        ).exclude(id=self.id).exists():

            raise ValidationError(
                "You already have a pending verification request."
            )

        # Faculty approver must be FACULTY
        if self.faculty_approved_by:

            if self.faculty_approved_by.role != 'FACULTY':
                raise ValidationError(
                    "Only faculty can approve at faculty level."
                )

        # Admin approver must be ADMIN
        if self.admin_approved_by:

            if self.admin_approved_by.role != 'ADMIN':
                raise ValidationError(
                    "Only admins can approve at admin level."
                )

        # VERIFIED requires both approvals
        if self.status == 'VERIFIED':

            if not self.faculty_approved_by:
                raise ValidationError(
                    "Faculty approval required before verification."
                )

            if not self.admin_approved_by:
                raise ValidationError(
                    "Admin approval required before verification."
                )

        # ADMIN_APPROVED requires faculty approval first
        if self.status == 'ADMIN_APPROVED':

            if not self.faculty_approved_by:
                raise ValidationError(
                    "Faculty approval required first."
                )

        # REJECTED should contain rejection reason
        if self.status == 'REJECTED':

            if not self.rejection_reason:
                raise ValidationError(
                    "Please provide rejection reason."
                )

    # ---------------- SAVE ---------------- #

    def save(self, *args, **kwargs):

        self.full_clean()

        super().save(*args, **kwargs)

    # ---------------- STRING ---------------- #

    def __str__(self):

        return f"Verification - {self.user.username} ({self.status})"

    # ---------------- META ---------------- #

    class Meta:

        ordering = ['-created_at']

        constraints = [

            models.UniqueConstraint(
                fields=['user'],
                condition=Q(status='PENDING'),
                name='unique_pending_verification_request'
            )

        ]

# *************************************** Mentorship Request System ******************************************************
class MentorshipRequest(models.Model):

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),   # NEW: mentorship has ended, student is free to send new requests
    ]
    student = models.ForeignKey(User, on_delete = models.CASCADE, related_name= 'sent_requests')
    alumni = models.ForeignKey(User, on_delete = models.CASCADE, related_name= 'received_requests')
    status = models.CharField(max_length =20, choices = STATUS_CHOICES, default= 'PENDING')

    created_at = models.DateTimeField(auto_now_add= True)
    ended_at = models.DateTimeField(null=True, blank=True)  # NEW: timestamp for when mentorship was marked COMPLETED

    


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
        status='PENDING').exclude(id=self.id).exists():
            raise ValidationError("You already have a pending request with this alumni.")

        # Prevent student from taking mentorship from another mentor.
        if MentorshipRequest.objects.filter(
        student=self.student,
        status="ACCEPTED").exclude(id=self.id).exists():
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

    SUSPENSION_TYPE = [
        ('TEMPORARY', 'Temporary'),
        ('PERMANENT', 'Permanent'),
    ]

    DURATION_CHOICES = [
        (15, '15 Days'),
        (30, '30 Days'),
        (45, '45 Days'),
        (60, '60 Days'),
    ]

    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='suspension_logs'
    )

    suspended_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='suspensions_done'
    )

    institution = models.ForeignKey(
        'Institution',
        on_delete=models.CASCADE,
        related_name='suspensions',
        null= True, blank= True)

    reason = models.TextField()

    evidence = models.TextField(
        blank=True,
        help_text="Screenshots, complaint references, proof etc."
    )

    suspension_type = models.CharField(
        max_length=20,
        choices=SUSPENSION_TYPE,null =True, blank=True
    )

    duration_days = models.IntegerField(
        choices=DURATION_CHOICES,
        null=True,
        blank=True
    )

    suspended_until = models.DateTimeField(
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):

        # Prevent self suspension
        if self.user == self.suspended_by:
            raise ValidationError(
                "Users cannot suspend themselves."
            )

        # Only institution admins can suspend
        if self.suspended_by.role != 'ADMIN':
            raise ValidationError(
                "Only institution admins can suspend users."
            )

        # Admin can suspend only users of same institution
        if self.user.institution != self.suspended_by.institution:
            raise ValidationError(
                "Admins can suspend only their institution users."
            )

        # Institution consistency check
        if self.user.institution != self.institution:
            raise ValidationError(
                "Suspension institution mismatch."
            )

        # Only students and alumni can be suspended
        if self.user.role not in ['STUDENT', 'ALUMNI']:
            raise ValidationError(
                "Only students and alumni can be suspended."
            )

        # Temporary suspension validation
        if self.suspension_type == 'TEMPORARY':

            if not self.duration_days:
                raise ValidationError(
                    "Temporary suspension requires duration."
                )

            self.suspended_until = (
                timezone.now() +
                timezone.timedelta(days=self.duration_days)
            )

        # Permanent suspension validation
        if self.suspension_type == 'PERMANENT':

            self.duration_days = None
            self.suspended_until = None

    def save(self, *args, **kwargs):

        self.full_clean()

        # Mark user suspended
        self.user.is_suspended = True
        self.user.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.suspension_type}"

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


class Notification(models.Model):
    TYPE_CHOICES = [
        ('MENTORSHIP_REQUEST', 'Mentorship Request'),
        ('MENTORSHIP_ACCEPTED', 'Mentorship Accepted'),
        ('MENTORSHIP_REJECTED', 'Mentorship Rejected'),
        ('FACULTY_ANNOUNCEMENT', 'Faculty Announcement'),
        ('VERIFICATION_UPDATE', 'Verification Update'),
        ('SESSION_SCHEDULED', 'Session Scheduled'),
        ('SESSION_LIVE', 'Session Live'),
        ('GENERAL', 'General'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')

    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='GENERAL')
    title = models.CharField(max_length=150)
    message = models.TextField()

    # Optional deep-link, e.g. reverse('accounts:alumni_requests') or a chat URL
    link_url = models.CharField(max_length=255, blank=True, null=True)

    is_read = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} → {self.recipient.username}"

#-------------------------------------- sessions -------------------------------------------------
def generate_session_code():
    # Jaise abc-defg-hij hota hai, waise hi unique 9 letter code
    chars = string.ascii_lowercase
    part1 = ''.join(random.choice(chars) for _ in range(3))
    part2 = ''.join(random.choice(chars) for _ in range(4))
    part3 = ''.join(random.choice(chars) for _ in range(3))
    return f"{part1}-{part2}-{part3}"

class MentorshipSession(models.Model):
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_sessions')
    participant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='joined_sessions')
    session_code = models.CharField(max_length=15, unique=True, default=generate_session_code)
    
    date = models.DateField(null=True, blank=True)
    timings = models.TimeField(null=True, blank=True)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='SCHEDULED')
    
    # NEW FIELDS: Active users count track karne ke liye
    active_users_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session {self.session_code} ({self.status})"