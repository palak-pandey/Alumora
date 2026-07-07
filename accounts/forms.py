from django import forms
from .models import StudentProfile, FacultyProfile, AlumniProfile, VerificationRequest

class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['bio', 'about', 'department', 'batch_year', 'skills']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
            'about': forms.Textarea(attrs={'rows': 4}),
            'skills': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': f'Enter {name.replace("_", " ").title()}'
            })
            field.required = False  # Validation fallback protection


class FacultyProfileForm(forms.ModelForm):
    class Meta:
        model = FacultyProfile
        fields = [
            'department', 'bio', 'about', 'profile_pic', 'cover_photo',
            'current_designation', 'current_join_year', 
            'past_company_1', 'past_designation_1', 'past_timeline_1', 
            'past_company_2', 'past_designation_2', 'past_timeline_2', 
            'research_publications'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.required = False  # Custom handling ke liye bypass safety


class AlumniProfileForm(forms.ModelForm):
    class Meta:
        model = AlumniProfile
        # Jo fields model mein nahi thin unhe hata kar safe list kar diya hai
        fields = [
            'bio', 'about', 'profile_pic', 'cover_photo','skills',
            'current_join_year', 'current_company', 'job_title',
            'past_company_1', 'past_designation_1', 'past_timeline_1',
            'past_company_2', 'past_designation_2', 'past_timeline_2'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.required = False  # Crash protection



class FacultyNotificationForm(forms.Form):
    AUDIENCE_CHOICES = [
        ('STUDENT', 'All Students'),
        ('ALUMNI', 'All Alumni'),
        ('BOTH', 'All Students & Alumni'),
    ]
    audience = forms.ChoiceField(
        choices=AUDIENCE_CHOICES,
        help_text="Ignored if you enter a specific username below.",
    )
    specific_username = forms.CharField(
        max_length=150,
        required=False,
        label="Send to a specific username (optional)",
        help_text="Leave blank to send to the whole audience selected above. "
                   "If filled, only this student/alumni (from your institution) will receive it.",
    )
    title = forms.CharField(max_length=150)
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}))

class VerificationRequestForm(forms.ModelForm):
    class Meta:
        model = VerificationRequest
        fields = [
            'first_name', 'last_name', 'father_name',
            'degree_course', 'abc_apaar_id', 'degree_certificate',
        ]    