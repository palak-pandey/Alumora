from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from .models import User, Institution, MentorshipRequest
from django.shortcuts import get_object_or_404 
from django.urls import reverse
from .models import VerificationRequest, StudentProfile, AlumniProfile, FacultyProfile, MentorshipSession
from .models import Conversation , Message
from django.utils import timezone
from .forms import StudentProfileForm, FacultyProfileForm,AlumniProfileForm,FacultyNotificationForm,VerificationRequestForm
from django.contrib.auth.decorators import login_required
from .notifications import notify
from .models import User, Institution, MentorshipRequest, Notification
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q
from django.db import models
from datetime import datetime
from .forms import AlumniRegisterForm   

# Max number of PENDING mentorship requests a student may have open at once
MAX_PENDING_MENTORSHIP_REQUESTS = 5


def _annotate_mentorship_status(alumni_iterable, student):
    """
    Attaches `my_request_status` ('PENDING' / 'ACCEPTED' / None) and
    `my_request_id` onto each alumni object, based on this student's
    existing MentorshipRequest with them. REJECTED requests are treated
    as None so the student can send a fresh request.
    """
    alumni_list = list(alumni_iterable)
    alumni_ids = [a.id for a in alumni_list]

    live_requests = MentorshipRequest.objects.filter(
        student=student,
        alumni_id__in=alumni_ids,
        status__in=["PENDING", "ACCEPTED"]
    )
    status_map = {r.alumni_id: r for r in live_requests}

    for alumni in alumni_list:
        req = status_map.get(alumni.id)
        alumni.my_request_status = req.status if req else None
        alumni.my_request_id = req.id if req else None

    return alumni_list


# ---------------------- LOGIN VIEW ----------------------
def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            if getattr(user, 'is_suspended', False): # Safely check attribute
                messages.error(request, "Your account is suspended.")
                return redirect("accounts:login")

            login(request, user)
            # --- ADD THIS PRINT STATEMENT ---
            print(f"DEBUG: User logged in. Raw role field value is: '{user.role}'")
            # -------------------------------

            # Redirect based on role
            next_url = request.GET.get('next')

            # 1. Prioritize where the user was trying to go (?next=)
            next_url = request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)

            # 2. Fallback to Role-based redirect if no next parameter (using .upper() to prevent typos)
            user_role = str(user.role).upper() if user.role else ""
            
            if user_role == "STUDENT":
                return redirect("accounts:student_dashboard")
            elif user_role == "ALUMNI":
                return redirect("accounts:alumni_dashboard")
            elif user_role == "FACULTY":
                return redirect("accounts:faculty_dashboard")
            else:
                messages.error(request, f"Role '{user.role}' not recognized.")
                return redirect("accounts:login")
        else:
            messages.error(request, "Invalid username or password")
            return redirect("accounts:login")

    return render(request, "auth/login.html")

# ---------------------- LOGOUT VIEW ----------------------
def user_logout(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("accounts:login")


# ---------------------- DASHBOARDS ----------------------
def student_dashboard(request):
    if not request.user.is_authenticated or str(request.user.role).upper() != "STUDENT":
        return HttpResponseForbidden("Access denied. This dashboard is for students only.")

    student = request.user
    
    # 1. Mentorship Status Trackers
    accepted_request = MentorshipRequest.objects.filter(
        student=student,
        status='ACCEPTED'
    ).select_related('alumni', 'alumni__alumni_profile').first()

    pending_requests = MentorshipRequest.objects.filter(
        student=student,
        status='PENDING'
    )

    completed_mentorship_count = MentorshipRequest.objects.filter(
        student=student,
        status='COMPLETED'
    ).count()

    # 2. CROSS-INSTITUTION ALUMNI QUERY WITH 3 ITEMS LIMIT
    suggested_qs = User.objects.select_related(
        "alumni_profile", "institution"
    ).filter(
        role="ALUMNI",
        is_suspended=False,
        is_verified=True,  # Taaki sirf verified professional profiles hi show ho
        alumni_profile__mentorship_available=True
    ).order_by('?')[:6]

    suggested_alumni = _annotate_mentorship_status(suggested_qs, student)

    # 3. 5-Request Limitation Budget Tracker for Action Buttons Synchronization
    total_sent_count = pending_requests.count()
    can_send_request = total_sent_count < MAX_PENDING_MENTORSHIP_REQUESTS and not accepted_request

    if accepted_request:
        send_blocked_message = "You already have a mentor. You can only mentor with one alumni at a time."
    elif total_sent_count >= MAX_PENDING_MENTORSHIP_REQUESTS:
        send_blocked_message = f"You have already sent {MAX_PENDING_MENTORSHIP_REQUESTS} requests. Wait for a response before sending more."
    else:
        send_blocked_message = ""

    context = {
        'accepted_request': accepted_request,
        'pending_requests': pending_requests,
        'suggested_alumni': suggested_alumni,
        'total_sent_count': total_sent_count,
        'completed_mentorship_count': completed_mentorship_count,
        'has_accepted_mentor': accepted_request is not None,
        'can_send_request': can_send_request,
        'send_blocked_message': send_blocked_message,
        'max_pending_requests': MAX_PENDING_MENTORSHIP_REQUESTS,
    }

    return render(request, 'dashboards/student_dashboard.html', context)


@login_required(login_url='accounts:login') # Make sure user is logged in
def alumni_dashboard(request):
    if not request.user.is_authenticated or str(request.user.role).upper() != "ALUMNI":
        return HttpResponseForbidden("Access denied. This dashboard is for alumni only.")

    alumni = request.user

    # 1. Mentorship requests tracking context (Students who requested this alumnus)
    incoming_requests = MentorshipRequest.objects.filter(alumni=alumni).select_related('student', 'student__student_profile', 'student__institution')
    
    pending_requests = incoming_requests.filter(status='PENDING')
    accepted_requests = incoming_requests.filter(status='ACCEPTED')
    rejected_requests = incoming_requests.filter(status='REJECTED')

    # 2. Verification request status tracking for banner alerts
    verification_status = "NOT_SUBMITTED"
    latest_verification = VerificationRequest.objects.filter(user=alumni).order_by('-created_at').first()
    if latest_verification:
        verification_status = latest_verification.status

    # 3. Scheduled/active/completed sessions this alumni is part of
    planned_sessions = MentorshipSession.objects.filter(
        Q(creator=alumni) | Q(participant=alumni),
        status='SCHEDULED'
    ).select_related(
        'creator', 'participant',
        'creator__student_profile', 'creator__alumni_profile',
        'participant__student_profile', 'participant__alumni_profile',
    ).order_by('-created_at')

    for s in planned_sessions:
        other = s.participant if s.creator_id == alumni.id else s.creator
        s.other_user = other
        s.other_profile = getattr(other, 'student_profile', None) or getattr(other, 'alumni_profile', None)

    context = {
        'incoming_requests': incoming_requests, 
        'pending_requests': pending_requests,
        'accepted_requests': accepted_requests,
        'received_requests_count': incoming_requests.count(), # Top Card 1
        'pending_requests_count': pending_requests.count(),   # Top Card 2
        'active_mentees_count': accepted_requests.count(),    # Top Card 3
        'verification_status': verification_status,
        'latest_verification': latest_verification,
        'planned_sessions': planned_sessions,
    }

    return render(request, 'dashboards/alumni_dashboard.html', context)

@login_required(login_url='accounts:login')
def faculty_dashboard(request):
    if not request.user.is_authenticated or request.user.role != "FACULTY":
        return HttpResponseForbidden("Access denied.")

    # 1. Sabse pehle URL check karo ki kya notification se click karke aaye hain
    just_requests = request.GET.get('just_requests') == 'true'

    # MAIN LIST LOGIC: Is section me hum fully verified log (ADMIN_APPROVED, VERIFIED) ko exclude kar rahe hain
    verification_requests = VerificationRequest.objects.filter(
        user__institution=request.user.institution
    ).exclude(
        status__in=['ADMIN_APPROVED', 'VERIFIED']
    ).select_related('user').order_by('-created_at')

    total_alumni = User.objects.filter(
        role='ALUMNI', institution=request.user.institution
    ).count()

    verified_alumni = User.objects.filter(
        role='ALUMNI', institution=request.user.institution, is_verified=True
    ).count()

    stats = {
        'total_students': User.objects.filter(
            role='STUDENT', institution=request.user.institution
        ).count(),

        'total_alumni': total_alumni,

        'verified_alumni': verified_alumni,

        'announcements_sent': Notification.objects.filter(
            sender=request.user, notification_type='FACULTY_ANNOUNCEMENT'
        ).count(),

        'verification_rate': round((verified_alumni / total_alumni) * 100) if total_alumni else 0,
    }

    # RIGHT SIDE PANEL LOGIC: Yahan hum explicitly unko fetch kar rahe hain jo admin panel/shell se full verify ho chuke hain
    recently_verified = VerificationRequest.objects.filter(
        user__institution=request.user.institution,
        status__in=['ADMIN_APPROVED', 'VERIFIED']
    ).order_by('-updated_at')[:5]

    # 2. Context ke andar "just_requests" bhej do taaki HTML isko read kar sake
    return render(request, "dashboards/faculty_dashboard.html", {
        "verification_requests": verification_requests,
        "stats": stats,
        "recently_verified": recently_verified,
        "just_requests": just_requests,  
    })
# ---------------------- ALUMNI LIST (STUDENTS ONLY) ----------------------
@login_required
def alumni_list(request):
    if request.user.role != "STUDENT":
        return HttpResponseForbidden("Only students can view alumni.")

    if request.user.is_suspended:
        return HttpResponseForbidden("Your account is suspended.")

    # Cross-institution view: pulls all active, verified alumni globally across the network
    available_alumni = User.objects.select_related(
        "alumni_profile", "institution"
    ).filter(
        role="ALUMNI",
        is_suspended=False,
        is_verified=True,  
        alumni_profile__mentorship_available=True
    ).order_by('username')

    # Optional filter: Only triggers if student explicitly selects a specific college from a search dropdown
    institution_id = request.GET.get("institution")
    if institution_id and Institution.objects.filter(id=institution_id).exists():
        available_alumni = available_alumni.filter(institution_id=institution_id)

    available_alumni = _annotate_mentorship_status(available_alumni, request.user)

    # 5-request limitation budget tracker calculation logic
    total_sent_count = MentorshipRequest.objects.filter(
        student=request.user,
        status="PENDING"
    ).count()

    # If this student already has an accepted mentor, they cannot send any new
    # requests (to this alumni or any other) until that mentorship ends.
    has_accepted_mentor = MentorshipRequest.objects.filter(
        student=request.user,
        status="ACCEPTED"
    ).exists()

    can_send_request = total_sent_count < MAX_PENDING_MENTORSHIP_REQUESTS and not has_accepted_mentor

    if has_accepted_mentor:
        send_blocked_message = "You already have a mentor. You can only mentor with one alumni at a time."
    elif total_sent_count >= MAX_PENDING_MENTORSHIP_REQUESTS:
        send_blocked_message = f"You have already sent {MAX_PENDING_MENTORSHIP_REQUESTS} requests. Wait for a response before sending more."
    else:
        send_blocked_message = ""

    context = {
        "available_alumni": available_alumni, 
        "total_sent_count": total_sent_count,
        "has_accepted_mentor": has_accepted_mentor,
        "can_send_request": can_send_request,
        "send_blocked_message": send_blocked_message,
        "max_pending_requests": MAX_PENDING_MENTORSHIP_REQUESTS,
    }

    return render(request, "mentorship/alumni_list.html", context)


# ---------------------- MENTORSHIP ACTIONS ----------------------
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

    pending_count = MentorshipRequest.objects.filter(
        student=request.user,
        status="PENDING"
    ).count()

    if pending_count >= MAX_PENDING_MENTORSHIP_REQUESTS:
        messages.error(
            request,
            f"You have already sent {MAX_PENDING_MENTORSHIP_REQUESTS} requests. "
            f"Wait for a response before sending more."
        )
        next_url = request.GET.get('next')
        return redirect(next_url) if next_url else redirect("accounts:alumni_list")

    existing = MentorshipRequest.objects.filter(
        student=request.user,
        alumni=alumni,
        status="PENDING"
    ).exists()

    if existing:
        messages.warning(request, "Request already sent.")
        return redirect("accounts:alumni_list")
    
    try:
        req = MentorshipRequest.objects.create(
            student=request.user,
            alumni=alumni
        )
        notify(
            recipient=alumni,
            sender=request.user,
            title="New Mentorship Request",
            message=f"{request.user.get_full_name() or request.user.username} has requested you as a mentor.",
            notification_type='MENTORSHIP_REQUEST',
            link_url=reverse('accounts:alumni_requests'),
        )
        messages.success(request, "Mentorship request sent successfully.")
    except Exception as e:
        messages.error(request, str(e))

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect("accounts:alumni_list")


# Cancel a pending mentorship request (student-initiated)
def cancel_request(request, request_id):

    if not request.user.is_authenticated or request.user.role != "STUDENT":
        return HttpResponseForbidden("Only students can cancel requests.")

    req = get_object_or_404(MentorshipRequest, id=request_id, student=request.user)

    if req.status != "PENDING":
        messages.error(request, "Only pending requests can be cancelled.")
    else:
        alumni = req.alumni
        req.delete()
        notify(
            recipient=alumni,
            sender=request.user,
            title="Mentorship Request Cancelled",
            message=f"{request.user.get_full_name() or request.user.username} cancelled their mentorship request.",
            notification_type='GENERAL',
        )
        messages.success(request, "Mentorship request cancelled.")

    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect("accounts:student_dashboard")

    
def my_requests(request):
    if not request.user.is_authenticated or request.user.role != "STUDENT":
        return HttpResponseForbidden("Access denied.")

    all_requests = MentorshipRequest.objects.filter(
        student=request.user
    ).select_related('alumni', 'alumni__alumni_profile').order_by('-created_at')

    accepted_request = all_requests.filter(status="ACCEPTED").first()
    pending_requests = all_requests.filter(status="PENDING")
    past_requests = all_requests.exclude(status="PENDING").exclude(status="ACCEPTED")

    mentor_skills = []
    if accepted_request and hasattr(accepted_request.alumni, 'alumni_profile'):
        skills_str = accepted_request.alumni.alumni_profile.skills
        if skills_str:
            mentor_skills = [s.strip() for s in skills_str.split(',') if s.strip()]

    return render(request, "mentorship/your_mentor.html", {
        "accepted_request": accepted_request,
        "pending_requests": pending_requests,
        "past_requests": past_requests,
        "mentor_skills": mentor_skills,
    })


# ---------------------- YOUR MENTEES (ALUMNI ONLY) ----------------------
@login_required(login_url='accounts:login')
def your_mentees(request):
    # Ensure only Alumni can view this dashboard target mapping
    if str(request.user.role).upper() != "ALUMNI":
        return HttpResponseForbidden("Access denied. This page is optimized for alumni accounts only.")

    alumni = request.user

    # Fetching all requests linked to this alumnus with ACCEPTED status or any completed tracking
    # select_related avoids N+1 queries for profile rendering (Profile pic, bio, university)
    mentees_queryset = MentorshipRequest.objects.filter(
        alumni=alumni,
        status__in=['ACCEPTED', 'COMPLETED']  # Handles both active and past/completed mentorship tracks
    ).select_related(
        'student', 
        'student__student_profile',
        'student__institution'
    ).order_by('-created_at')

    # Adding a clean runtime attribute to differentiate past records dynamically inside template
    for relation in mentees_queryset:
        relation.is_past_mentorship = (relation.status.upper() == 'COMPLETED')

    context = {
        'mentees': mentees_queryset,
    }

    
    return render(request, 'mentorship/your_mentees.html', context)



def alumni_requests(request):
    if not request.user.is_authenticated or request.user.role != "ALUMNI":
        return HttpResponseForbidden("Only alumni can view requests.")

    # Sabhi incoming requests fetch karein select_related ke sath taaki database queries load na badhayein
    incoming_requests = MentorshipRequest.objects.filter(
        alumni=request.user
    ).select_related('student', 'student__student_profile', 'student__institution').order_by('-created_at')

    # Status wise separate kar dete hain taaki template me filter karna easy ho
    pending_requests = incoming_requests.filter(status='PENDING')
    processed_requests = incoming_requests.exclude(status='PENDING')

    context = {
        "incoming_requests": incoming_requests,
        "pending_requests": pending_requests,
        "processed_requests": processed_requests,
    }

    
    return render(request, "mentorship/incoming_requests.html", context)

def accept_request(request, request_id):
    if not request.user.is_authenticated or request.user.role != "ALUMNI":
        return HttpResponseForbidden("Access denied.")

    req = get_object_or_404(MentorshipRequest, id=request_id, alumni=request.user)

    if req.alumni != request.user:
        return HttpResponseForbidden("Not your request.")

    if req.status != "PENDING":
        return HttpResponse("Request already processed.")

    if MentorshipRequest.objects.filter(student=req.student, status="ACCEPTED").exists():
        return HttpResponse("Student already has a mentor.")
    
    req.status = "ACCEPTED"
    req.save()

    notify(
        recipient=req.student,
        sender=req.alumni,
        title="Mentorship Request Accepted",
        message=f"{req.alumni.get_full_name() or req.alumni.username} accepted your mentorship request.",
        notification_type='MENTORSHIP_ACCEPTED',
        link_url=reverse('accounts:my_requests'),
    )

    auto_rejected = MentorshipRequest.objects.filter(
        student=req.student, status="PENDING"
    ).exclude(id=req.id)

    for other_req in auto_rejected:
        notify(
            recipient=other_req.student,
            sender=other_req.alumni,
            title="Mentorship Request Rejected",
            message=f"{other_req.alumni.get_full_name() or other_req.alumni.username}'s request was auto-closed because you accepted another mentor.",
            notification_type='MENTORSHIP_REJECTED',
        )

    auto_rejected.update(status="REJECTED") 
    
    return redirect("accounts:alumni_requests")


def reject_request(request, request_id):
    if not request.user.is_authenticated or request.user.role != "ALUMNI":
        return HttpResponseForbidden("Access denied.")

    req = get_object_or_404(MentorshipRequest, id=request_id, alumni=request.user)

    if req.alumni != request.user:
        return HttpResponseForbidden("Not your request.")

    if req.status != "PENDING":
        return HttpResponse("Request already processed.")

    req.status = "REJECTED"
    req.save()
   
    notify(
        recipient=req.student,
        sender=req.alumni,
        title="Mentorship Request Rejected",
        message=f"{req.alumni.get_full_name() or req.alumni.username} declined your mentorship request.",
        notification_type='MENTORSHIP_REJECTED',
     )
   
    return redirect("accounts:alumni_requests")


# Ends an ACCEPTED mentorship (marks it COMPLETED). Either the student or the
# alumni involved in that specific mentorship can trigger this. Once
# COMPLETED, the student is free to send fresh requests to (up to 5) alumni again.
def end_mentorship(request, request_id):
    if not request.user.is_authenticated or request.user.role not in ("STUDENT", "ALUMNI"):
        return HttpResponseForbidden("Access denied.")

    req = get_object_or_404(MentorshipRequest, id=request_id)

    # Only the two people involved in this mentorship may end it
    if request.user != req.student and request.user != req.alumni:
        return HttpResponseForbidden("Not your mentorship.")

    if req.status != "ACCEPTED":
        messages.error(request, "Only an active mentorship can be marked as completed.")
    else:
        req.status = "COMPLETED"
        req.ended_at = timezone.now()
        req.save()

        other_party = req.alumni if request.user == req.student else req.student
        notify(
            recipient=other_party,
            sender=request.user,
            title="Mentorship Ended",
            message=f"{request.user.get_full_name() or request.user.username} marked your mentorship as completed.",
            notification_type='GENERAL',
        )
        messages.success(request, "Mentorship marked as completed. You can now connect with a new mentor.")

    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)

    if request.user.role == "STUDENT":
        return redirect("accounts:my_requests")
    return redirect("accounts:your_mentees")


#------------------------------ VERIFICATION FLOW -----------------------------------------
@login_required(login_url='accounts:login')
def submit_verification_request(request):
    if request.user.role != "ALUMNI":
        return HttpResponseForbidden("Only alumni can request verification.")

    if request.method == "POST":
        form = VerificationRequestForm(request.POST, request.FILES)
        form.instance.user = request.user   
        if form.is_valid():
            v = form.save(commit=False)
            v.user = request.user
            v.save()                   

            faculty_members = User.objects.filter(
                role="FACULTY",
                institution=request.user.institution
            )
            for faculty in faculty_members:
                notify(
                    recipient=faculty,
                    sender=request.user,
                    title="New Verification Request",
                    message=f"{request.user.get_full_name() or request.user.username} submitted a verification request for review.",
                    notification_type='VERIFICATION_UPDATE',
                    link_url=reverse('accounts:faculty_dashboard'),
                )

            messages.success(request, "Verification request submitted. Faculty will review it shortly.")
        else:
            messages.error(request, "Please fix the errors and try again.")
    else:
        form = VerificationRequestForm()

    return redirect('accounts:alumni_dashboard')


def faculty_approve(request, request_id):
    if request.user.role != "FACULTY":
        return HttpResponseForbidden("Only faculty allowed.")

    v = get_object_or_404(VerificationRequest, id=request_id)

    if v.status != "PENDING":
        return HttpResponse("Already processed.")

    v.faculty_approved_by = request.user
    v.status = "FACULTY_APPROVED"
    v.save()
    
    admins = User.objects.filter(role="ADMIN", institution=v.user.institution)
    for admin_user in admins:
        notify(
            recipient=admin_user,
            sender=request.user,
            title="Verification Awaiting Admin Approval",
            message=f"{v.user.get_full_name() or v.user.username}'s verification was approved by faculty and now needs admin sign-off.",
            notification_type='VERIFICATION_UPDATE',
        )
    return redirect("accounts:faculty_dashboard")


def faculty_reject(request, request_id):
    if request.user.role != "FACULTY":
        return HttpResponseForbidden("Only faculty allowed.")

    v = get_object_or_404(VerificationRequest, id=request_id)

    if v.status != "PENDING":
        return HttpResponse("Already processed.")

    reason = request.POST.get("reason") or request.GET.get("reason") or "No reason provided."
    v.status = "REJECTED"
    v.rejection_reason = reason
    v.save()
    
    notify(
        recipient=v.user,
        title="Verification Request Rejected",
        message=f"Your verification request was rejected. Reason: {reason}",
        notification_type='VERIFICATION_UPDATE',
    )
    
    return redirect("accounts:faculty_dashboard")


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

    notify(
        recipient=req.user,
        sender=request.user,
        title="You're Verified!",
        message="Your alumni account has been fully verified.",
        notification_type='VERIFICATION_UPDATE',
    )

    return redirect("admin:index")


#-------------------------- CHAT VIEWS --------------------------------   
def inbox(request):
    conversations = Conversation.objects.filter(
        participants=request.user
    ).order_by('-updated_at')

    query = request.GET.get('q', '').strip()
    users = User.objects.none()  

    if request.user.role == 'FACULTY':
        if query:
            users = User.objects.filter(
                Q(username__icontains=query) | 
                Q(first_name__icontains=query) | 
                Q(last_name__icontains=query),
                institution=request.user.institution
            ).exclude(id=request.user.id)[:10] 
        else:
            users = User.objects.filter(institution=request.user.institution).exclude(id=request.user.id)[:20]
    else:
        sent_requests = MentorshipRequest.objects.filter(
            student=request.user,
            status__in=['PENDING', 'ACCEPTED']
        )
        base_users = User.objects.filter(id__in=sent_requests.values_list('alumni_id', flat=True))
        
        if query:
            users = base_users.filter(
                Q(username__icontains=query) | Q(first_name__icontains=query)
            )
        else:
            users = base_users

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
        "users": users,
        "query": query  
    })


def chat_view(request, convo_id):
    convo = get_object_or_404(Conversation, id=convo_id, participants=request.user)
    chat_messages = convo.messages.all()

    chat_messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    conversations = Conversation.objects.filter(participants=request.user).order_by('-updated_at')

    has_faculty = convo.participants.filter(role='FACULTY').exists()
    is_pending = not convo.is_accepted if not has_faculty else False

    return render(request, "chat/chat.html", {
        "conversation": convo,
        "chat_messages": chat_messages,
        "conversations": conversations, 
        "is_pending": is_pending 
    })


def send_message(request, convo_id):
    convo = get_object_or_404(Conversation, id=convo_id, participants=request.user)
    has_faculty = convo.participants.filter(role='FACULTY').exists()
    
    if not convo.is_accepted and not has_faculty:
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

            receiver = convo.participants.exclude(id=request.user.id).first()

            if receiver:
                chat_url = reverse("accounts:chat_view", kwargs={"convo_id": convo.id})
                sender_name = request.user.get_full_name() or request.user.username
                msg_preview = content[:50] + "..." if len(content) > 50 else content

                notify(
                    recipient=receiver,
                    sender=request.user,
                    title=f"New Message from {sender_name}",
                    message=msg_preview,
                    notification_type='FACULTY_ANNOUNCEMENT', 
                    link_url=chat_url 
                )

    return redirect("accounts:chat_view", convo_id=convo.id)


def start_chat(request, user_id):
    other_user = get_object_or_404(User, id=user_id)

    if request.user.institution != other_user.institution:
        return HttpResponseForbidden("You can only message members of your own institution.")

    convo = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    ).first()

    is_mentor = MentorshipRequest.objects.filter(
        student=request.user,
        alumni=other_user,
        status="ACCEPTED"
    ).exists()

    is_faculty_involved = (request.user.role == 'FACULTY' or other_user.role == 'FACULTY')

    if not convo:
        convo = Conversation.objects.create(
            is_accepted=True if is_faculty_involved else is_mentor
        )
        convo.participants.add(request.user, other_user)
    elif is_faculty_involved and not convo.is_accepted:
        convo.is_accepted = True
        convo.save()

    return redirect("accounts:chat_view", convo_id=convo.id)


def accept_message_request(request, convo_id):
    convo = get_object_or_404(Conversation, id=convo_id)

    if request.user not in convo.participants.all():
        return HttpResponseForbidden("Not allowed")

    if request.user.role != 'ALUMNI':
        return HttpResponseForbidden("Only alumni can accept message requests")

    convo.is_accepted = True
    convo.save()

    return redirect("accounts:chat_view", convo_id=convo.id)


# ---------------------- PROFILES ----------------------
@login_required(login_url='accounts:login')  
def view_profile(request):
    user = request.user
    role = None  
    profile_obj = None

    if hasattr(user, 'faculty_profile'):
        role = 'faculty'
        profile_obj = user.faculty_profile
    elif hasattr(user, 'alumni_profile'):
        role = 'alumni'
        profile_obj = user.alumni_profile
    elif hasattr(user, 'student_profile'):
        role = 'student'
        profile_obj = user.student_profile
    else:
        messages.error(request, "Sorry! You don't have a profile to view.")
        return redirect('accounts:login')    
    
    context = {
        "role": role,
        "profile": profile_obj,  
        role: profile_obj        
    }

    template_name = "profiles/student_profile.html"
    return render(request, template_name, context)


@login_required(login_url='accounts:login')
def edit_profile(request):
    user = request.user
    role = None
    profile_obj = None
    FormClass = None

    if hasattr(user, 'faculty_profile'):
        role = 'faculty'
        profile_obj = user.faculty_profile
        FormClass = FacultyProfileForm
    elif hasattr(user, 'alumni_profile'):
        role = 'alumni'
        profile_obj = user.alumni_profile
        FormClass = AlumniProfileForm
    elif hasattr(user, 'student_profile'):
        role = 'student'
        profile_obj = user.student_profile
        FormClass = StudentProfileForm
    else:
        messages.error(request, "Sorry! You don't have access to this page.")
        return redirect('accounts:login')
    
    if request.method == 'POST':
        profile_obj.bio = request.POST.get('bio', profile_obj.bio)
        profile_obj.about = request.POST.get('about', profile_obj.about)
        
        if request.FILES.get('profile_pic'):
            profile_obj.profile_pic = request.FILES.get('profile_pic')
        if request.FILES.get('cover_photo'):
            profile_obj.cover_photo = request.FILES.get('cover_photo')

        if role == 'student':
            profile_obj.department = request.POST.get('department', profile_obj.department)
            profile_obj.batch_year = request.POST.get('batch_year', profile_obj.batch_year)
            profile_obj.skills = request.POST.get('skills', getattr(profile_obj, 'skills', ''))
            
        elif role == 'alumni':
            profile_obj.current_company = request.POST.get('current_company', profile_obj.current_company)
            profile_obj.job_title = request.POST.get('job_title', profile_obj.job_title)
            profile_obj.current_join_year = request.POST.get('current_join_year', profile_obj.current_join_year)
            profile_obj.skills = request.POST.get('skills', getattr(profile_obj, 'skills', ''))
            
            profile_obj.recent_degree = request.POST.get('recent_degree', profile_obj.recent_degree)
            profile_obj.batch = request.POST.get('batch', profile_obj.batch)
            profile_obj.past_university1 = request.POST.get('past_university1', profile_obj.past_university1)
            profile_obj.past_degree_course1 = request.POST.get('past_degree_course1', profile_obj.past_degree_course1)
            profile_obj.batch1 = request.POST.get('batch1', profile_obj.batch1)

        elif role == 'faculty':
            profile_obj.department = request.POST.get('department', profile_obj.department)
            profile_obj.current_designation = request.POST.get('current_designation', profile_obj.current_designation)
            profile_obj.current_join_year = request.POST.get('current_join_year', profile_obj.current_join_year)
            profile_obj.research_publications = request.POST.get('research_publications', profile_obj.research_publications)

        if role in ['faculty', 'alumni']:
            profile_obj.past_company_1 = request.POST.get('past_company_1', profile_obj.past_company_1)
            profile_obj.past_designation_1 = request.POST.get('past_designation_1', profile_obj.past_designation_1)
            profile_obj.past_timeline_1 = request.POST.get('past_timeline_1', profile_obj.past_timeline_1)
            
            profile_obj.past_company_2 = request.POST.get('past_company_2', profile_obj.past_company_2)
            profile_obj.past_designation_2 = request.POST.get('past_designation_2', profile_obj.past_designation_2)
            profile_obj.past_timeline_2 = request.POST.get('past_timeline_2', profile_obj.past_timeline_2)

        profile_obj.save()
        
        try:
            return redirect('view_profile')
        except:
            return redirect('accounts:view_profile')
            
    else:
        form = FormClass(instance=profile_obj)

    template_name = "profiles/edit_profile.html"
    
    context = {
        'form': form,
        'role': role,
        'profile': profile_obj,
        'student': profile_obj if role == 'student' else None,
        'alumni': profile_obj if role == 'alumni' else None,
        'faculty': profile_obj if role == 'faculty' else None,
        role: profile_obj  
    }

    return render(request, template_name, context)

# ---------------------- NOTIFICATIONS ----------------------
def faculty_send_notification(request):
    if not request.user.is_authenticated or request.user.role != "FACULTY":
        return HttpResponseForbidden("Only faculty can send notifications.")

    if request.method == "POST":
        form = FacultyNotificationForm(request.POST)
        if form.is_valid():
            audience = form.cleaned_data.get('audience')
            specific_username = form.cleaned_data.get('specific_username')
            title = form.cleaned_data['title']
            message_text = form.cleaned_data['message']

            if specific_username:
                recipients = User.objects.filter(
                    username=specific_username,
                    institution=request.user.institution,
                    role__in=['STUDENT', 'ALUMNI']
                )
                if not recipients.exists():
                    messages.error(
                        request,
                        f"No student or alumni with username '{specific_username}' "
                        "found in your institution."
                    )
                    return render(request, 'notifications/send_notification.html', {'form': form})
                recipient_label = specific_username
            elif audience == 'BOTH':
                recipients = User.objects.filter(
                    role__in=['STUDENT', 'ALUMNI'],
                    institution=request.user.institution
                )
                recipient_label = "student(s) & alumni"
            else:
                recipients = User.objects.filter(
                    role=audience,
                    institution=request.user.institution
                )
                recipient_label = f"{audience.lower()}(s)"

            for recipient in recipients:
                notify(
                    recipient=recipient,
                    sender=request.user,
                    title=title,
                    message=message_text,
                    notification_type='FACULTY_ANNOUNCEMENT',
                )

            messages.success(request, f"Notification sent to {recipients.count()} {recipient_label}.")
            return redirect('accounts:faculty_dashboard')
    else:
        form = FacultyNotificationForm()

    return render(request, 'notifications/send_notification.html', {'form': form})

@login_required(login_url='accounts:login')
def notifications_list(request):
    notifications = Notification.objects.filter(recipient=request.user)
    unread_ids = set(notifications.filter(is_read=False).values_list('id', flat=True))
    notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'notifications/list.html', {
        'notifications': notifications,
        'unread_ids': unread_ids,
    })

@login_required
def faculty_verification_list(request):
    if str(request.user.role).upper() != "FACULTY":
        return HttpResponseForbidden("Access denied.")
        
    verification_requests = VerificationRequest.objects.filter(
        user__institution=request.user.institution
    ).select_related('user').order_by('-created_at')

    context = {
        "verification_requests": verification_requests,
        "just_requests": True, # <--- THIS FLAG IS THE GATEKEEPER
    }
    return render(request, "dashboards/faculty_dashboard.html", context)


@login_required(login_url='accounts:login')
def sessions_dashboard(request):
    user = request.user
    all_sessions = MentorshipSession.objects.filter(
        Q(creator=user) | Q(participant=user)
    ).order_by('-created_at')

    if request.method == 'POST':
        actiontype = request.POST.get('action_type')
        
        # 1. CANCEL SESSION ACTION
        if actiontype == 'CANCEL':
            session_id = request.POST.get('session_id')
            session_to_cancel = get_object_or_404(MentorshipSession, id=session_id)
            if user == session_to_cancel.creator or user == session_to_cancel.participant:
                if session_to_cancel.status == 'SCHEDULED':
                    session_to_cancel.status = 'CANCELLED'
                    session_to_cancel.save()
                    messages.success(request, "Session successfully cancelled.")
                else:
                    messages.error(request, "Sirf scheduled sessions ko cancel kiya ja sakta hai.")
            return redirect('accounts:sessions_dashboard')

        # 2. JOIN VIA ROOM CODE ACTION
        if actiontype == 'JOIN_CODE':
            entered_code = request.POST.get('room_code', '').strip()
            session_obj = MentorshipSession.objects.filter(session_code=entered_code).first()
            
            if not session_obj:
                messages.error(request, "Invalid Room Code.")
                return redirect('accounts:sessions_dashboard')
                
            if user != session_obj.creator and user != session_obj.participant:
                messages.error(request, "You are not authorized for this session.")
                return redirect('accounts:sessions_dashboard')
                
            if session_obj.status in ['COMPLETED', 'CANCELLED']:
                messages.error(request, "This session has already ended or been cancelled.")
                return redirect('accounts:sessions_dashboard')
                
            # Date & Timing Check for Scheduled meets
            if session_obj.status == 'SCHEDULED' and session_obj.date and session_obj.timings:
                now = timezone.localtime(timezone.now())
                session_datetime = datetime.combine(session_obj.date, session_obj.timings)
                session_datetime = timezone.make_aware(session_datetime, timezone.get_current_timezone())
                if now < session_datetime:
                    messages.error(request, f"You cannot join yet. This session is scheduled for {session_obj.date} at {session_obj.timings}.")
                    return redirect('accounts:sessions_dashboard')
            
            return redirect('accounts:session_room', room_code=session_obj.session_code)

        # 3. SCHEDULE / IMMEDIATE SETUP
        target_username = request.POST.get('target_username')
        try:
            target_user = User.objects.get(username=target_username)
        except User.DoesNotExist:
            messages.error(request, f"User '{target_username}' not found.")
            return redirect('accounts:sessions_dashboard')

        if target_user == user:
            messages.error(request, "You cannot start a session with yourself.")
            return redirect('accounts:sessions_dashboard')

        session = MentorshipSession(creator=user, participant=target_user)

        # English Notification Message Generation & Redirection targeting /notifications/
        if actiontype == 'SCHEDULE':
            session.date = request.POST.get('date')
            session.timings = request.POST.get('timings')
            session.status = 'SCHEDULED'
            title_text = "New Scheduled Mentorship Session"
            msg_text = f"Hello, user @{user.username} has scheduled a mentorship session with you on {session.date} at {session.timings}. Room Code: {session.session_code}."
            notif_type = 'SESSION_SCHEDULED'
            notif_link = reverse('accounts:notifications_list')
        else:
            session.status = 'ACTIVE'
            title_text = "Live Mentorship Session Ongoing!"
            msg_text = f"Attention! A live interactive session has been started by @{user.username}. Room Code: {session.session_code}."
            notif_type = 'SESSION_LIVE'
            notif_link = reverse('accounts:session_room', kwargs={'room_code': session.session_code})

        session.save()

        Notification.objects.create(
            recipient=target_user,
            sender=user,
            title=title_text,
            message=msg_text,
            notification_type=notif_type,
            link_url=notif_link,
        )

        if actiontype == 'IMMEDIATE':
            return redirect('accounts:session_room', room_code=session.session_code)
        
        messages.success(request, f"Session created! Code: {session.session_code}")
        return redirect('accounts:sessions_dashboard')

    context = {'sessions': all_sessions}
    return render(request, 'mentorship/sessions_dashboard.html', context)


@login_required(login_url='accounts:login')
def session_room(request, room_code):
    session = get_object_or_404(MentorshipSession, session_code=room_code)
    
    if request.user != session.creator and request.user != session.participant:
        return HttpResponseForbidden("Unauthorized member.")

    if session.status in ['COMPLETED', 'CANCELLED']:
        messages.error(request, "This session room is closed forever.")
        return redirect('accounts:sessions_dashboard')

    # Status activation on active entry
    if session.status == 'SCHEDULED':
        session.status = 'ACTIVE'

    # User entered: increment active_users_count only once per browser
    # session for this room (prevents refresh/reload from inflating the count)
    session_flag_key = f'joined_session_{room_code}'
    if not request.session.get(session_flag_key):
        session.active_users_count += 1
        request.session[session_flag_key] = True

    session.save()

    context = {
        'session': session,
        'room_code': room_code,
    }
    return render(request, 'mentorship/session_room.html', context)


@login_required
def leave_session_room(request, room_code):
    session = get_object_or_404(MentorshipSession, session_code=room_code)

    if session.status in ['COMPLETED', 'CANCELLED']:
        return JsonResponse({'status': 'already_closed', 'current_status': session.status})

    session_flag_key = f'joined_session_{room_code}'
    if request.session.get(session_flag_key):
        if session.active_users_count > 0:
            session.active_users_count -= 1
        del request.session[session_flag_key]

    if session.active_users_count <= 0:
        session.active_users_count = 0
        session.status = 'COMPLETED'

    session.save()
    return JsonResponse({'status': 'left', 'current_status': session.status})



def landing_page(request):
    """
    Public home page. Logged-in users skip straight past it, to their own dashboard.
    """
    if request.user.is_authenticated:
        role = (request.user.role or '').upper()
        if role == 'STUDENT':
            return redirect('accounts:student_dashboard')
        elif role == 'ALUMNI':
            return redirect('accounts:alumni_dashboard')
        elif role == 'FACULTY':
            return redirect('accounts:faculty_dashboard')
        return redirect('accounts:login')
 
    return render(request, 'home.html', {
        'university_count': Institution.objects.count(),
        'verified_alumni_count': User.objects.filter(role='ALUMNI', is_verified=True).count(),
        'completed_mentorship_count': MentorshipRequest.objects.filter(status='COMPLETED').count(),
    })
 
 
def register_alumni(request):
    """
    Public sign-up — alumni only. Account is created unverified.
    Verification itself happens through your existing VerificationRequest flow
    (degree certificate upload -> faculty/admin approval -> is_verified=True).
    The 30-day verify / 30-day ban / delete clock is enforced by the
    enforce_alumni_verification management command (run it daily via cron/Celery beat).
    """
    if request.user.is_authenticated:
        return redirect('accounts:login')
 
    if request.method == "POST":
        form = AlumniRegisterForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data.get('email') or '',
                password=form.cleaned_data['password1'],
                first_name=form.cleaned_data['full_name'],
                role='ALUMNI',
                institution=form.cleaned_data['institution'],
                is_verified=False,
            )
            messages.success(
                request,
                "Account created. Verify your degree certificate within 30 days to keep it active."
            )
            return redirect('accounts:login')
    else:
        form = AlumniRegisterForm()
 
    return render(request, 'auth/register.html', {'form': form})