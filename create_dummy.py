import os
import django
import random
import string
from django.utils import timezone

# 1. Django Setup Initialize
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Alumora.settings')
django.setup()

from accounts.models import (
    User, Institution, StudentProfile, FacultyProfile, AlumniProfile,
    VerificationRequest, MentorshipRequest, MentorshipSession
)
from faker import Faker

fake = Faker()

def seed_database():
    print("🚀 [START] Custom Seeder running for 100 specific accounts...")

    # ---- 1. EXISTING INSTITUTIONS FETCH (by name, not by admin username — ---
    #         works no matter what username you gave your institution admins) ----
    try:
        inst_gdu = Institution.objects.get(name="G.D University")
        print(f"🏫 Found Institution: {inst_gdu.name}")
    except Institution.DoesNotExist:
        print("❌ Error: Institution 'G.D University' database mein nahi mila! Pehle banao.")
        return

    try:
        inst_mr = Institution.objects.get(name="Manav Rachna University")
        print(f"🏫 Found Institution: {inst_mr.name}")
    except Institution.DoesNotExist:
        print("❌ Error: Institution 'Manav Rachna University' database mein nahi mila! Pehle banao.")
        return

    # Grab whichever ADMIN user belongs to each institution (any username works)
    admin_gdu = User.objects.filter(role="ADMIN", institution=inst_gdu).first()
    admin_mr = User.objects.filter(role="ADMIN", institution=inst_mr).first()

    if not admin_gdu:
        print("❌ Error: G.D University ke liye koi ADMIN user nahi mila! Pehle banao.")
        return
    if not admin_mr:
        print("❌ Error: Manav Rachna University ke liye koi ADMIN user nahi mila! Pehle banao.")
        return

    institutions = [inst_gdu, inst_mr]
    admin_users = [admin_gdu, admin_mr]

    # Shared configurations
    departments = ["Computer Science", "Information Technology", "Electronics", "Mechanical Eng", "Data Science", "MBA"]
    skills_pool = ["Python", "Django", "React", "Cloud Architecture", "SQL", "Machine Learning", "Product Management"]
    companies = ["Google", "Microsoft", "Amazon", "Meta", "TCS", "Infosys"]
    designations = ["Software Engineer", "Senior Developer", "Product Manager", "Tech Lead"]

    # ---- 2. 100 USERS DISTRIBUTION BUDGET ----
    # 50 users per institution (Total = 100)
    # Per institution: 10 Faculty + 20 Students + 20 Alumni = 50 Users
    
    faculties_pool = []
    students_pool = []
    alumni_pool = []
    
    password_for_all = "testpassword123" # <--- Sabka password same rakha hai!

    print(f"🔑 IMPORTANT: Saare 100 accounts ka login password hoga: '{password_for_all}'")

    credentials_log = []  # (username, role, institution_name, password)

    for idx, inst in enumerate(institutions):
        assigned_admin = admin_users[idx]
        inst_suffix = "gdu" if idx == 0 else "mr"
        
        # A. Create Faculty (10 per college = 20 total)
        for i in range(1, 11):
            username = f"faculty_{inst_suffix}_{i}"
            f_name = fake.first_name()
            
            if not User.objects.filter(username=username).exists():
                faculty_user = User.objects.create_user(
                    username=username,
                    first_name=f_name,
                    last_name=fake.last_name(),
                    email=f"{username}@alumora.edu",
                    password=password_for_all,
                    role="FACULTY",
                    institution=inst,
                    is_verified=True
                )
                
                f_profile, _ = FacultyProfile.objects.get_or_create(user=faculty_user)
                f_profile.department = random.choice(departments)
                f_profile.bio = f"Faculty member at senior position."
                f_profile.current_designation = "Assistant Professor"
                f_profile.current_join_year = "2020"
                f_profile.save()
                
                faculties_pool.append(faculty_user)
                credentials_log.append((username, "FACULTY", inst.name, password_for_all))

        # B. Create Students (20 per college = 40 total)
        for i in range(1, 21):
            username = f"student_{inst_suffix}_{i}"
            s_name = fake.first_name()
            
            if not User.objects.filter(username=username).exists():
                student_user = User.objects.create_user(
                    username=username,
                    first_name=s_name,
                    last_name=fake.last_name(),
                    email=f"{username}@student.alumora.edu",
                    password=password_for_all,
                    role="STUDENT",
                    institution=inst,
                    is_verified=False
                )
                
                s_profile, _ = StudentProfile.objects.get_or_create(user=student_user)
                s_profile.enrollment_number = f"ENROLL/{inst_suffix.upper()}/{1000 + i}"
                s_profile.department = random.choice(departments)
                s_profile.batch_year = "2026"
                s_profile.skills = "Python, Django, SQL"
                s_profile.save()
                
                students_pool.append(student_user)
                credentials_log.append((username, "STUDENT", inst.name, password_for_all))

        # C. Create Alumni (20 per college = 40 total -> ALL FULLY VERIFIED)
        for i in range(1, 21):
            username = f"alumni_{inst_suffix}_{i}"
            a_name = fake.first_name()
            
            if not User.objects.filter(username=username).exists():
                alumni_user = User.objects.create_user(
                    username=username,
                    first_name=a_name,
                    last_name=fake.last_name(),
                    email=f"{username}@gmail.com",
                    password=password_for_all,
                    role="ALUMNI",
                    institution=inst,
                    is_verified=True # <--- Directly verified marking
                )
                
                a_profile, _ = AlumniProfile.objects.get_or_create(user=alumni_user)
                a_profile.bio = f"Proud Alumni | Working professional"
                a_profile.skills = "React, Node, Product Strategy"
                a_profile.current_company = random.choice(companies)
                a_profile.job_title = random.choice(designations)
                a_profile.current_join_year = "2024"
                a_profile.mentorship_available = True
                a_profile.save()
                
                alumni_pool.append(alumni_user)
                credentials_log.append((username, "ALUMNI", inst.name, password_for_all))

                # Fetching an institution faculty for creating verified tracking record
                matching_faculties = [f for f in faculties_pool if f.institution == inst]
                chosen_faculty = matching_faculties[0] if matching_faculties else assigned_admin

                # Create Verification Request mapping with full approvals to satisfy dashboard statistics
                v_req = VerificationRequest(
                    user=alumni_user,
                    first_name=alumni_user.first_name,
                    last_name=alumni_user.last_name,
                    father_name=fake.name_male(),
                    degree_course="B.Tech CS",
                    abc_apaar_id=f"ABC-{random.randint(100000,999999)}",
                    status="VERIFIED",
                    faculty_approved_by=chosen_faculty,
                    admin_approved_by=assigned_admin
                )
                super(VerificationRequest, v_req).save()

    print(f"✅ Users Seeded: {len(faculties_pool)} Faculty, {len(students_pool)} Students, {len(alumni_pool)} Alumni.")
    print(f"📊 Total New Dummy Users added = {len(faculties_pool) + len(students_pool) + len(alumni_pool)}")

    # ---- 3. INJECT ACTIVE MENTORSHIP ENTRIES FOR DASHBOARD TESTING ----
    print("📩 Connecting users for large scale simulation...")
    for student in students_pool[:20]:
        # Connect to a random verified alumni
        alumni = random.choice(alumni_pool)
        
        # Bypass clean method duplicate crashes
        if not MentorshipRequest.objects.filter(student=student, status="ACCEPTED").exists():
            try:
                m_req = MentorshipRequest(student=student, alumni=alumni, status="ACCEPTED")
                m_req.full_clean()
                m_req.save()
                
                # Active sessions tracking
                chars = string.ascii_lowercase
                code = f"{''.join(random.choice(chars) for _ in range(3))}-{''.join(random.choice(chars) for _ in range(4))}-{''.join(random.choice(chars) for _ in range(3))}"
                MentorshipSession.objects.create(
                    creator=alumni, participant=student, session_code=code,
                    date=timezone.now().date(), timings=timezone.now().time(), status='SCHEDULED'
                )
            except Exception:
                continue

    # ---- 4. WRITE CREDENTIALS TO CSV FOR EASY LOGIN REFERENCE ----
    import csv
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dummy_credentials.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["username", "role", "institution", "password"])
        writer.writerows(credentials_log)
    print(f"📝 Credentials CSV likhi gayi yaha: {out_path}")

    print("🎉 [SUCCESS] All 100 specific accounts generated and linked cleanly!")

if __name__ == '__main__':
    seed_database()