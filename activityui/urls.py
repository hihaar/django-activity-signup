from django.urls import path
from . import views

app_name = 'activityui'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/register/', views.register_view, name='register'),
    path('auth/change-password/', views.change_password, name='change_password'),
    path('activity/<int:activity_id>/', views.activity_detail, name='activity_detail'),
    path('activity/<int:activity_id>/register/', views.register_activity, name='register_activity'),
    path('activity/<int:activity_id>/register-atc/', views.register_atc, name='register_atc'),
    path('activity/<int:activity_id>/boarding-pass/', views.boarding_pass, name='boarding_pass'),
    path('activity/<int:activity_id>/weather/', views.get_weather, name='weather'),
    path('api/weather/<int:activity_id>/departure/', views.departure_weather_api, name='departure_weather_api'),
    path('api/weather/<int:activity_id>/arrival/', views.arrival_weather_api, name='arrival_weather_api'),
    path('user/<str:username>/', views.user_profile, name='user_profile'),
    path('past-activities/', views.past_activities, name='past_activities'),
    path('upcoming-activities/', views.upcoming_activities, name='upcoming_activities'),
    path('atc/controllers/', views.atc_controllers, name='atc_controllers'),
]