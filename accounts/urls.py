from django.urls import path
from . import views


app_name = "accounts"

urlpatterns = [
    path('', views.user_login, name='home'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    path('student_dashboard/', views.student_dashboard, name='student_dashboard'),
    path('alumni_dashboard/', views.alumni_dashboard, name='alumni_dashboard'),
    path('faculty_dashboard/', views.faculty_dashboard, name='faculty_dashboard'),
    path('alumni/', views.alumni_list, name='alumni_list'),

    path('send_request/<int:alumni_id>/', views.send_request, name='send_request'),
    path('my_requests/', views.my_requests, name='my_requests'),
    path('alumni_requests/', views.alumni_requests, name='alumni_requests'),
    path('accept_request/<int:request_id>/', views.accept_request, name='accept_request'),
    path('reject_request/<int:request_id>/', views.reject_request, name='reject_request'),

    
    path("faculty_approve/<int:request_id>/", views.faculty_approve, name="faculty_approve"),
    path("admin_approve/<int:req_id>/", views.admin_approve, name="admin_approve"),
    path("faculty_reject/<int:request_id>/", views.faculty_reject, name="faculty_reject"),

    path('messages/', views.inbox, name='inbox'),
    path('chat/<int:convo_id>/', views.chat_view, name='chat_view'),
    path('send-message/<int:convo_id>/', views.send_message, name='send_message'),
    path('start-chat/<int:user_id>/', views.start_chat, name='start_chat'),
    path('accept-message/<int:convo_id>/', views.accept_message_request, name='accept_message_request'),
    path("profile/", views.view_profile, name="view_profile"),
    path('edit-profile/', views.edit_profile, name='edit_profile'),

    path('notifications/', views.notifications_list, name='notifications_list'),
    path('faculty/send-notification/', views.faculty_send_notification, name='faculty_send_notification'),
    path('verification/submit/', views.submit_verification_request, name='submit_verification_request'),
    path('your-mentees/', views.your_mentees, name='your_mentees'),

    path('sessions/', views.sessions_dashboard, name='sessions_dashboard'),
    path('sessions/room/<str:room_code>/', views.session_room, name='session_room'),
    path('sessions/leave/<str:room_code>/', views.leave_session_room, name='leave_session_room'),



]