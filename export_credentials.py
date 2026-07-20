import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Alumora.settings')
django.setup()

from accounts.models import User
import csv

# Password known sirf isliye ki humne khud fix rakha tha 'testpassword123' seed script mein.
# Agar tune manually koi user alag password se banaya hai, uski row mein password column
# blank chhod dena padega ya khud edit karna padega, kyunki hash se plaintext nikal nahi sakte.
KNOWN_PASSWORD = "testpassword123"

users = User.objects.filter(
    role__in=["FACULTY", "STUDENT", "ALUMNI"]
).select_related("institution").order_by("role", "username")

out_path = os.path.join(os.path.expanduser("~"), "Desktop", "dummy_credentials_full.csv")

with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["username", "first_name", "last_name", "role", "institution", "password"])
    for u in users:
        writer.writerow([
            u.username,
            u.first_name,
            u.last_name,
            u.role,
            u.institution.name if u.institution else "",
            KNOWN_PASSWORD,
        ])

print(f"✅ Done! {users.count()} users export ho gaye: {out_path}")