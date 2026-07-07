from .models import Notification

def notifications(request):
    context = {
        'unread_notifications_count': 0,
        'recent_notifications': [],
        'user_profile_pic_url': None,
        'user_role_icon': 'fa-user' # Default icon
    }
    
    if request.user.is_authenticated:
        # Notifications logic
        qs = Notification.objects.filter(recipient=request.user)
        context['unread_notifications_count'] = qs.filter(is_read=False).count()
        context['recent_notifications'] = qs[:5]
        
        # Profile Picture & Icon Logic based on Role
        role = getattr(request.user, 'role', '').upper()
        
        try:
            if role == 'FACULTY' and hasattr(request.user, 'faculty_profile'):
                profile = request.user.faculty_profile
                context['user_role_icon'] = 'fa-user-tie'
            elif role == 'ALUMNI' and hasattr(request.user, 'alumni_profile'):
                profile = request.user.alumni_profile
                context['user_role_icon'] = 'fa-user-graduate'
            elif hasattr(request.user, 'student_profile'):
                profile = request.user.student_profile
                context['user_role_icon'] = 'fa-user'
            else:
                profile = None
                
            # Agar profile mili aur usme pic hai toh url uthao
            if profile and profile.profile_pic:
                context['user_profile_pic_url'] = profile.profile_pic.url
        except Exception:
            pass  # Back safe fallback agar profile query fail ho jaye
            
    return context