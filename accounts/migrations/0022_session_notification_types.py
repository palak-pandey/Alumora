from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0021_mentorshipsession_active_users_count_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('MENTORSHIP_REQUEST', 'Mentorship Request'),
                    ('MENTORSHIP_ACCEPTED', 'Mentorship Accepted'),
                    ('MENTORSHIP_REJECTED', 'Mentorship Rejected'),
                    ('FACULTY_ANNOUNCEMENT', 'Faculty Announcement'),
                    ('VERIFICATION_UPDATE', 'Verification Update'),
                    ('SESSION_SCHEDULED', 'Session Scheduled'),
                    ('SESSION_LIVE', 'Session Live'),
                    ('GENERAL', 'General'),
                ],
                default='GENERAL',
                max_length=30,
            ),
        ),
    ]