from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Institution




class UserAdmin(BaseUserAdmin):

    list_display = ('username', 'email', 'role', 'institution', 'is_staff', 'is_active', 'is_verified')
    list_filter = ('role', 'institution','is_staff')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'groups', 'user_permissions')}),
        ('Custom Fields', {'fields': ('role', 'institution', 'is_verified')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role', 'institution', 'is_verified'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        if request.user.role == 'ADMIN' and request.user.institution:
            return qs.filter(institution=request.user.institution)

        if request.user.role == 'FACULTY' and request.user.institution:
            return qs.filter(institution=request.user.institution, role='STUDENT')

        return qs.none()


    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "institution":
            if not request.user.is_superuser and request.user.institution:
                kwargs["queryset"] = Institution.objects.filter(
                    pk=request.user.institution.pk
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


    def get_readonly_fields(self, request, obj=None):

        if request.user.is_superuser:
            return []

        if request.user.role == 'FACULTY':
            return [
                'username',
                'email',
                'role',
                'institution',
                'is_staff',
                'is_active'
            ]

        return []


    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.institution = request.user.institution
        super().save_model(request, obj, form, change)



    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "role":
            
            if request.user.is_superuser:
                return super().formfield_for_choice_field(db_field, request, **kwargs)

            if request.user.role == "ADMIN":
                kwargs["choices"] = [
                ("FACULTY", "Faculty"),
                ("STUDENT", "Student"),
                ("ALUMNI", "Alumni"),
                ]

        return super().formfield_for_choice_field(db_field, request, **kwargs)


  
    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))

        if not request.user.is_superuser and "institution" in fields:
            fields.remove("institution")

        return fields



class InstitutionAdmin(admin.ModelAdmin):
    
    def get_queryset(self,request):
        qs = super().get_queryset(request)
        
        if request.user.is_superuser:
            return qs
        
        if request.user.role == 'ADMIN' and request.user.institution:
            return qs.filter(pk=request.user.institution.pk)
        
        return qs.none()

   
   
    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        
        return False
    
        
        
        
    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        
        return True
    

   
   
    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True

        if request.user.role == 'ADMIN'and request.user.institution:
            if obj is None:
                return True  # list view access
            return obj.pk == request.user.institution.pk

        return False
   

    def get_readonly_fields(self,request, obj= None):
        if request.user.is_superuser:
            return []
        
        if request.user.role=='ADMIN':
            return ['name']
        
        return []    


    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True

        if request.user.role == 'ADMIN' and request.user.institution:
            if obj is None:
                return True
            return obj.pk == request.user.institution.pk

        return False


# Register your models here.    
admin.site.register(User, UserAdmin)
admin.site.register(Institution, InstitutionAdmin)