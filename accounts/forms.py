from django import forms
from .models import StudentProfile

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

