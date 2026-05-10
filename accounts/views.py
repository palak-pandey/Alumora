from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from .models import User, Institution, MentorshipRequest
from django.shortcuts import get_object_or_404 
from django.urls import reverse
from .models import VerificationRequest, StudentProfile
from .models import Conversation , Message
from django.utils import timezone
from .forms import StudentProfileForm

# ---------------------- LOGIN VIEW ----------------------
def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            if user.is_suspended:
                messages.error(request, "Your account is suspended.")
                return redirect("accounts:login")

            login(request, user)

            # Redirect based on role
            if user.role == "STUDENT":
                return redirect("accounts:student_dashboard")
            elif user.role == "ALUMNI":
                return redirect("accounts:alumni_dashboard")
            elif user.role == "FACULTY":
                return redirect("accounts:faculty_dashboard")
            else:
                messages.error(request, "Role not recognized.")
                return redirect("accounts:login")
        else:
            messages.error(request, "Invalid username or password")
            return redirect("accounts:login")

    return render(request, "login.html")


# ---------------------- LOGOUT VIEW ----------------------
def user_logout(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("accounts:login")


# ---------------------- DASHBOARDS ----------------------
def student_dashboard(request):
    student = request.user

    accepted_request = MentorshipRequest.objects.filter(
        student=student,
        status='ACCEPTED'
    ).select_related('alumni').first()

    pending_requests = MentorshipRequest.objects.filter(
        student=student,
        status='PENDING'
    )

    context = {
        'accepted_request': accepted_request,
        'pending_requests': pending_requests
    }

    return render(request, 'student_dashboard.html', context)


def alumni_dashboard(request):
    user = request.user

    # Mentorship
    mentorship_pending = MentorshipRequest.objects.filter(
        alumni=user,
        status='PENDING'
    ).select_related('student')

    mentorship_accepted = MentorshipRequest.objects.filter(
        alumni=user,
        status='ACCEPTED'
    ).select_related('student')

    # Verification (as faculty role)
    verification_requests = VerificationRequest.objects.filter(
        status='PENDING'
    ).select_related('user')

    context = {
        'mentorship_pending': mentorship_pending,
        'mentorship_accepted': mentorship_accepted,
        'verification_requests': verification_requests
    }

    return render(request, 'alumni_dashboard.html', context)

#------------------------------------------------------------------------------------------------------------------------------------

def faculty_dashboard(request):
    if not request.user.is_authenticated or request.user.role != "FACULTY":
        return HttpResponseForbidden("Access denied.")

    verification_requests = VerificationRequest.objects.filter(
        user__institution=request.user.institution
    )

    return render(request, "faculty_dashboard.html", {
        "verification_requests": verification_requests
    })



# ---------------------- ALUMNI LIST (STUDENTS ONLY) ----------------------

def alumni_list(request):
    if not request.user.is_authenticated or request.user.role != "STUDENT":
        return HttpResponseForbidden("Only students can view alumni.")

    if request.user.is_suspended:
        return HttpResponseForbidden("Your account is suspended.")

    available_alumni = User.objects.select_related(
        "alumni_profile", "institution"
    ).filter(
        role="ALUMNI",
        is_suspended=False,
        alumni_profile__mentorship_available=True
    )

    institution_id = request.GET.get("institution")
    if institution_id and Institution.objects.filter(id=institution_id).exists():
        available_alumni = available_alumni.filter(institution_id=institution_id)

    # Pagination
    paginator = Paginator(available_alumni, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    
    sent_requests = MentorshipRequest.objects.filter(
        student=request.user,
        status="PENDING"
    ).values_list("alumni_id", flat=True)

    html = "<h2>Available Alumni:</h2><ul>"

    sent_requests = set(sent_requests)


    for alumni in page_obj:

        if alumni.id in sent_requests:
            action = "Request Sent"
        else:
            action = f"<a href='{reverse('accounts:send_request', args=[alumni.id])}'>Request Mentorship</a>"

        html += f"""
        <li>
        {alumni.username} | {alumni.institution.name if alumni.institution else 'No Institution'}
        {action}
        </li>
        """

    html += "</ul>"
    html += f"<br><a href='{reverse('accounts:student_dashboard')}'>Back</a> | <a href='{reverse('accounts:logout')}'>Logout</a>"

    return HttpResponse(html)



#send request 
def send_request(request, alumni_id):

    if not request.user.is_authenticated or request.user.role != "STUDENT":
        return HttpResponseForbidden("Only students can send requests.")

    alumni = get_object_or_404(User, id=alumni_id)

    if MentorshipRequest.objects.filter(
        student=request.user,
        status="ACCEPTED"
    ).exists():
        messages.error(request, "You already have a mentor.")
        return redirect("accounts:alumni_list")
 

    existing = MentorshipRequest.objects.filter(
        student=request.user,
        alumni=alumni,
        status="PENDING"
    ).exists()

    if existing:
        messages.warning(request, "Request already sent.")
        return redirect("accounts:alumni_list")
    
    
    try:
        MentorshipRequest.objects.create(
            student=request.user,
            alumni=alumni
        )
        messages.success(request, "Mentorship request sent successfully.")
    except Exception as e:
        messages.error(request, str(e))

    return redirect("accounts:alumni_list")
    
    
    
# My request 
def my_requests(request):

    if not request.user.is_authenticated or request.user.role != "STUDENT":
        return HttpResponseForbidden("Access denied.")

    mentorship_requests = MentorshipRequest.objects.filter(student=request.user)

    html = "<h2>My Mentorship Requests</h2><ul>"

    for req in mentorship_requests :
        if req.status == "ACCEPTED":
            html += f"<li>{req.alumni.username} - ACCEPTED (Your Mentor)</li>"

        elif req.status == "REJECTED":
            html += f"<li>{req.alumni.username} - REJECTED</li>"

        else :
            html += f"<li>{req.alumni.username} - PENDING</li>"

    html += "</ul>"
    html += f"<br><a href='{reverse('accounts:student_dashboard')}'>Back to Dashboard</a>"

    return HttpResponse(html)    

            


#    return HttpResponse(html)


# Alumni incoming request.
def alumni_requests(request):

    if not request.user.is_authenticated or request.user.role != "ALUMNI":
        return HttpResponseForbidden("Only alumni can view requests.")

    mentorship_requests = MentorshipRequest.objects.filter(alumni=request.user)

    html = "<h2>Incoming Requests</h2><ul>"

    for req in mentorship_requests:
        html += f"""
        <li>
        {req.student.username} - {req.status}
        <a href='{reverse('accounts:accept_request', args=[req.id])}'>Accept</a>
        <a href='{reverse('accounts:reject_request', args=[req.id])}'>Reject</a>
        </li>
        """

    html += "</ul>"
    html += f"<br><a href='{reverse('accounts:alumni_dashboard')}'>Back</a>"
    return HttpResponse(html)


# Alumni accept request.
def accept_request(request, request_id):

    if not request.user.is_authenticated or request.user.role != "ALUMNI":
        return HttpResponseForbidden("Access denied.")

    req = get_object_or_404(MentorshipRequest, id=request_id, alumni= request.user)

    if req.alumni != request.user:
        return HttpResponseForbidden("Not your request.")

    if req.status != "PENDING":
        return HttpResponse("Request already processed.")

    if MentorshipRequest.objects.filter( student = req.student, status = "ACCEPTED").exists():
        return HttpResponse("Student already has a mentor.")
    
    
    req.status = "ACCEPTED"
    req.save()

    MentorshipRequest.objects.filter(
        student = req.student, status= "PENDING").exclude(id= req.id).update(status= "REJECTED") 
    
    
    return redirect("accounts:alumni_requests")



# Alumni reject requests.
def reject_request(request, request_id):

    if not request.user.is_authenticated or request.user.role != "ALUMNI":
        return HttpResponseForbidden("Access denied.")

    req = get_object_or_404(MentorshipRequest,id=request_id,alumni=request.user
    )

    if req.alumni != request.user:
        return HttpResponseForbidden("Not your request.")

    if req.status != "PENDING":
        return HttpResponse("Request already processed.")

    req.status = "REJECTED"
    req.save()

    return redirect("accounts:alumni_requests")


#------------------------------ verification flow ------------------------------------------------------------------
def faculty_approve(request, request_id):
    if request.user.role != "FACULTY":
        return HttpResponseForbidden("Only faculty allowed.")

    v = get_object_or_404(VerificationRequest, id=request_id)

    if v.status != "PENDING":
        return HttpResponse("Already processed.")

    v.faculty_approved_by = request.user
    v.status = "FACULTY_APPROVED"
    v.save()

    return redirect("faculty_dashboard")



def faculty_reject(request, request_id):
    if request.user.role != "FACULTY":
        return HttpResponseForbidden("Only faculty allowed.")

    v = get_object_or_404(VerificationRequest, id=request_id)

    if v.status != "PENDING":
        return HttpResponse("Already processed.")

    v.status = "REJECTED"   # BUT NOT FINAL
    v.save()

    return redirect("faculty_dashboard")



def admin_approve(request, req_id):

    req = get_object_or_404(VerificationRequest, id=req_id)

    if request.user.role != "ADMIN":
        return HttpResponseForbidden()

    if req.status != "FACULTY_APPROVED":
        return HttpResponse("Faculty approval required first")

    req.admin_approved_by = request.user
    req.status = "VERIFIED"
    req.user.is_verified = True
    req.user.save()
    req.save()

    return redirect("admin_dashboard")




#-------------------------- chat view --------------------------------   

def inbox(request):
    conversations = Conversation.objects.filter(
        participants=request.user
    ).order_by('-updated_at')

    sent_requests = MentorshipRequest.objects.filter(
    student=request.user,
    status__in=['PENDING', 'ACCEPTED']
)

    users = User.objects.filter(
    id__in=sent_requests.values_list('alumni_id', flat=True)
    )

    convo_data = []

    for convo in conversations:
        unread_count = convo.messages.filter(
            is_read=False
        ).exclude(sender=request.user).count()

        other_user = convo.participants.exclude(id=request.user.id).first()

        last_message = convo.messages.last()

        convo_data.append({
            'convo': convo,
            'unread_count': unread_count,
            'other_user': other_user,
            'last_message': last_message,
        })

    return render(request, "chat/inbox.html", {
        "convo_data": convo_data,
        "users": users   
    })

def chat_view(request, convo_id):
    convo = get_object_or_404(Conversation, id=convo_id, participants=request.user)
    messages = convo.messages.all()

    # Seen system
    messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    # Conversations for sidebar
    conversations = Conversation.objects.filter(participants=request.user).order_by('-updated_at')

    return render(request, "chat/chat.html", {
        "conversation": convo,
        "messages": messages,
        "conversations": conversations, 
        "is_pending": not convo.is_accepted 
    })


def send_message(request, convo_id):
    convo = get_object_or_404(Conversation, id=convo_id, participants=request.user)

    
    if not convo.is_accepted:
        return redirect("accounts:chat_view", convo_id=convo.id)

    if request.method == "POST":
        content = request.POST.get("content")

        if content and content.strip():
            Message.objects.create(
                conversation=convo,
                sender=request.user,
                content=content
            )

            convo.updated_at = timezone.now()
            convo.save()

    return redirect("accounts:chat_view", convo_id=convo.id)

def start_chat(request, user_id):
    other_user = get_object_or_404(User, id=user_id)

    convo = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    ).first()

    
    is_mentor = MentorshipRequest.objects.filter(
    student=request.user,
    alumni=other_user,
    status="accepted"
    ).exists()
    if not convo:
        convo = Conversation.objects.create(
            is_accepted=is_mentor  
        )
        convo.participants.add(request.user, other_user)

    return redirect("accounts:chat_view", convo_id=convo.id)


def accept_message_request(request, convo_id):
    convo = get_object_or_404(Conversation, id=convo_id)

    # Only other user (alumni) can accept
    if request.user not in convo.participants.all():
        return HttpResponseForbidden("Not allowed")

    convo.is_accepted = True
    convo.save()

    return redirect("accounts:chat_view", convo_id=convo.id)


def student_profile(request):
    student, _ = StudentProfile.objects.get_or_create(user=request.user)

    edit_mode = request.GET.get('edit') == 'true'

    if request.method == "POST":
        student.bio = request.POST.get("bio")
        student.about = request.POST.get("about")
        student.department = request.POST.get("department")
        student.batch_year = request.POST.get("batch_year")
        student.skills = request.POST.get("skills")
        
       # PROFILE PIC
        if 'profile_pic' in request.FILES:
            student.profile_pic = request.FILES['profile_pic']

        # COVER PHOTO
        if 'cover_photo' in request.FILES:
            student.cover_photo = request.FILES['cover_photo']

        student.save()
        return redirect('accounts:student_profile')

    return render(request, "student_profile.html", {
        "student": student,
        "edit_mode": edit_mode
    })

def edit_profile(request):
    student, _ = StudentProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = StudentProfileForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            return redirect('accounts:student_profile')
    else:
        form = StudentProfileForm(instance=student)

    return render(request, 'edit_profile.html', {'form': form})