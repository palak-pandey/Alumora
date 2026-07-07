from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from .models import User, Institution, MentorshipRequest
from django.shortcuts import get_object_or_404 
from django.urls import reverse
from .models import VerificationRequest, StudentProfile, AlumniProfile, FacultyProfile
from .models import Conversation , Message
from django.utils import timezone
from .forms import StudentProfileForm, FacultyProfileForm,AlumniProfileForm,FacultyNotificationForm,VerificationRequestForm
from django.contrib.auth.decorators import login_required
from .notifications import notify
from .models import User, Institution, MentorshipRequest, Notification
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q

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

    return render(request, 'dashboards/student_dashboard.html', context)


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

    # Verification (this alumni's own request status/progress)
    verification_requests = VerificationRequest.objects.filter(
        user=user
    ).select_related('user')

    context = {
        'mentorship_pending': mentorship_pending,
        'mentorship_accepted': mentorship_accepted,
        'verification_requests': verification_requests
    }

    return render(request, 'dashboards/alumni_dashboard.html', context)

#------------------------------------------------------------------------------------------------------------------------------------

def faculty_dashboard(request):
    if not request.user.is_authenticated or request.user.role != "FACULTY":
        return HttpResponseForbidden("Access denied.")

    # 1. Sabse pehle URL check karo ki kya notification se click karke aaye hain
    just_requests = request.GET.get('just_requests') == 'true'

    verification_requests = VerificationRequest.objects.filter(
        user__institution=request.user.institution
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

    recently_verified = verification_requests.filter(
        status='VERIFIED'
    ).order_by('-updated_at')[:5]

    # 2. Context ke andar "just_requests" bhej do taaki HTML isko read kar sake
    return render(request, "dashboards/faculty_dashboard.html", {
        "verification_requests": verification_requests,
        "stats": stats,
        "recently_verified": recently_verified,
        "just_requests": just_requests,  # <--- Yeh line zaroor check kar lena!
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

    notify(
        recipient=req.student,
        sender=req.alumni,
        title="Mentorship Request Accepted",
        message=f"{req.alumni.get_full_name() or req.alumni.username} accepted your mentorship request.",
        notification_type='MENTORSHIP_ACCEPTED',
        link_url=reverse('accounts:my_requests'),
    )

    # Capture who's about to get auto-rejected BEFORE the bulk update
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
   
    notify(
        recipient=req.student,
        sender=req.alumni,
        title="Mentorship Request Rejected",
        message=f"{req.alumni.get_full_name() or req.alumni.username} declined your mentorship request.",
        notification_type='MENTORSHIP_REJECTED',
     )
   
   
   
    return redirect("accounts:alumni_requests")


#------------------------------ verification flow ------------------------------------------------------------------
@login_required(login_url='accounts:login')
def submit_verification_request(request):
    if request.user.role != "ALUMNI":
        return HttpResponseForbidden("Only alumni can request verification.")

    if request.method == "POST":
        form = VerificationRequestForm(request.POST, request.FILES)
        form.instance.user = request.user   # set BEFORE is_valid(), since clean() reads self.user
        if form.is_valid():
            v = form.save(commit=False)
            v.user = request.user
            v.save()                   # this is what enforces "no duplicate pending request" for you

            # Notify every faculty member at this alumni's institution
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




#-------------------------- chat view --------------------------------   

def inbox(request):
    conversations = Conversation.objects.filter(
        participants=request.user
    ).order_by('-updated_at')

    # Search query capture kar rahe hain (Form ka name='q' ya 'search' ho sakta hai)
    query = request.GET.get('q', '').strip()
    users = User.objects.none()  # Default empty queryset

    if request.user.role == 'FACULTY':
        if query:
            # Agar faculty search bar mein kuch type kare, toh username, first_name, ya last_name se search ho
            users = User.objects.filter(
                Q(username__icontains=query) | 
                Q(first_name__icontains=query) | 
                Q(last_name__icontains=query),
                institution=request.user.institution
            ).exclude(id=request.user.id)[:10] # Top 10 results limit kiye hain taaki heavy load na ho
        else:
            # Agar search query nahi hai, toh aap chahein toh empty rakh sakte hain ya saare users dikha sakte hain
            # Abhi ke liye safe side saare users bhej rahe hain (bina filter ke)
            users = User.objects.filter(institution=request.user.institution).exclude(id=request.user.id)[:20]
    else:
        # Student/Alumni ke liye purana system (sirf accepted/pending mentors search ya list honge)
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
        "query": query  # Template mein value="" fill rakhne ke liye
    })

def chat_view(request, convo_id):
    convo = get_object_or_404(Conversation, id=convo_id, participants=request.user)
    chat_messages = convo.messages.all()

    # Seen system
    chat_messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    # Conversations for sidebar
    conversations = Conversation.objects.filter(participants=request.user).order_by('-updated_at')

    # FEATURE: Agar chat mein koi bhi participant FACULTY hai, toh pending automatic False ho jayega
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

    # Faculty conversation ko ignore karega restriction check se
    has_faculty = convo.participants.filter(role='FACULTY').exists()
    
    if not convo.is_accepted and not has_faculty:
        return redirect("accounts:chat_view", convo_id=convo.id)

    if request.method == "POST":
        content = request.POST.get("content")

        if content and content.strip():
            # 1. Message Create kijiye
            Message.objects.create(
                conversation=convo,
                sender=request.user,
                content=content
            )

            convo.updated_at = timezone.now()
            convo.save()

            # 2. Recipient nikalo jisko notify karna hai
            receiver = convo.participants.exclude(id=request.user.id).first()

            if receiver:
                # Chat window ka proper url generator
                chat_url = reverse("accounts:chat_view", kwargs={"convo_id": convo.id})
                
                # Sender ka display name taiyar karo
                sender_name = request.user.get_full_name() or request.user.username
                
                # Content ka ek chota preview snippet notification text ke liye
                msg_preview = content[:50] + "..." if len(content) > 50 else content

                # Aapka exact notify helper function
                notify(
                    recipient=receiver,
                    sender=request.user,
                    title=f"New Message from {sender_name}",
                    message=msg_preview,
                    notification_type='FACULTY_ANNOUNCEMENT', # Aapke templates mein yeh already styled hai!
                    link_url=chat_url # Notification click karte hi user seedhe chat par land karega
                )

    return redirect("accounts:chat_view", convo_id=convo.id)
def start_chat(request, user_id):
    other_user = get_object_or_404(User, id=user_id)

    # Strict Check: Faculty ya koi bhi user sirf apni university ke logon ko message kar sakta hai
    if request.user.institution != other_user.institution:
        return HttpResponseForbidden("You can only message members of your own institution.")

    convo = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    ).first()

    # Mentorship check strictly students/alumni ke liye hai
    is_mentor = MentorshipRequest.objects.filter(
        student=request.user,
        alumni=other_user,
        status="ACCEPTED"
    ).exists()

    # FEATURE: Agar message karne wala ya paane wala FACULTY hai, toh conversation dynamic auto-accept ho jayegi
    is_faculty_involved = (request.user.role == 'FACULTY' or other_user.role == 'FACULTY')

    if not convo:
        convo = Conversation.objects.create(
            is_accepted=True if is_faculty_involved else is_mentor
        )
        convo.participants.add(request.user, other_user)
    elif is_faculty_involved and not convo.is_accepted:
        # Agar purani chat galti se blocked thi, toh use khol do
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

@login_required(login_url='accounts:login')  # Agar login nahi hai toh login page par bhejega
def view_profile(request):
    user = request.user
    role = None  
    profile_obj = None

    # 1. Strict Role Detection (No assumptions, zero fallback)
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
        # Agar Admin ya koi bina profile wala user profile dekhne aaye
        messages.error(request, "Sorry! You don't have a profile to view.")
        return redirect('accounts:login')    
    
    # 2. Context taiyaar karo (Fixing the context_key bug)
    context = {
        "role": role,
        "profile": profile_obj,  # Ek generic name jo har template mein kaam aaye
        role: profile_obj        # Dynamic key (jaise 'student', 'faculty', ya 'alumni')
    }

    # 3. Dynamic Template Path
    template_name = "profiles/student_profile.html"
    return render(request, template_name, context)



@login_required(login_url='accounts:login')
def edit_profile(request):
    user = request.user
    role = None
    profile_obj = None
    FormClass = None

    # 1. Strict Role Detection
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
    
    # 2. POST Request Handling (Data Save karne ke liye)
    if request.method == 'POST':
        # Custom Manual Mapping: Direct HTML input names se data uthayenge
        profile_obj.bio = request.POST.get('bio', profile_obj.bio)
        profile_obj.about = request.POST.get('about', profile_obj.about)
        
        # Files (Photos) Update Handle karne ke liye
        if request.FILES.get('profile_pic'):
            profile_obj.profile_pic = request.FILES.get('profile_pic')
        if request.FILES.get('cover_photo'):
            profile_obj.cover_photo = request.FILES.get('cover_photo')

        # ─── STUDENT SPECIFIC FIELDS ───
        if role == 'student':
            profile_obj.department = request.POST.get('department', profile_obj.department)
            profile_obj.batch_year = request.POST.get('batch_year', profile_obj.batch_year)
            profile_obj.skills = request.POST.get('skills', getattr(profile_obj, 'skills', ''))
            
        # ─── ALUMNI SPECIFIC FIELDS ───
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

        # ─── FACULTY SPECIFIC FIELDS ───
        elif role == 'faculty':
            profile_obj.department = request.POST.get('department', profile_obj.department)
            profile_obj.current_designation = request.POST.get('current_designation', profile_obj.current_designation)
            profile_obj.current_join_year = request.POST.get('current_join_year', profile_obj.current_join_year)
            profile_obj.research_publications = request.POST.get('research_publications', profile_obj.research_publications)

        # ─── COMMON PAST EXPERIENCES (Faculty & Alumni Ke Liye Exact Fields) ───
        if role in ['faculty', 'alumni']:
            profile_obj.past_company_1 = request.POST.get('past_company_1', profile_obj.past_company_1)
            profile_obj.past_designation_1 = request.POST.get('past_designation_1', profile_obj.past_designation_1)
            profile_obj.past_timeline_1 = request.POST.get('past_timeline_1', profile_obj.past_timeline_1)
            
            profile_obj.past_company_2 = request.POST.get('past_company_2', profile_obj.past_company_2)
            profile_obj.past_designation_2 = request.POST.get('past_designation_2', profile_obj.past_designation_2)
            profile_obj.past_timeline_2 = request.POST.get('past_timeline_2', profile_obj.past_timeline_2)

        # Database me finalize save karo
        profile_obj.save()
        
        # URL pattern ke safety wrapper ke sath view page par bhejo
        try:
            return redirect('view_profile')
        except:
            return redirect('accounts:view_profile')
            
    # 3. GET Request Handling (Normal form layout render)
    else:
        form = FormClass(instance=profile_obj)

    # 4. Context & Rendering
    # 4. Context & Rendering (Safe Fallback Context)
    template_name = "profiles/edit_profile.html"
    
    # Teeno ko explicitly None ya object de rahe hain taaki template crash na kare
    context = {
        'form': form,
        'role': role,
        'profile': profile_obj,
        'student': profile_obj if role == 'student' else None,
        'alumni': profile_obj if role == 'alumni' else None,
        'faculty': profile_obj if role == 'faculty' else None,
        role: profile_obj  # dynamic key safe-keeping
    }

    return render(request, template_name, context)

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