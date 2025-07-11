from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from django.contrib.auth.models import User, Group
from django.conf import settings
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Sum
from functools import wraps
from typing import Callable, Any, Optional
from .models import Activity, Registration, ATCRegistration, ATCPermissionGrant
import requests

def verify_turnstile(view_func: Callable) -> Callable:
    """
    验证Cloudflare Turnstile响应的装饰器
    """
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.method == 'POST':
            turnstile_response = request.POST.get('cf-turnstile-response')
            if not turnstile_response:
                return render(request, 'auth/register.html', {
                    'error': '请完成人机验证',
                    'turnstile_site_key': settings.TURNSTILE_SITE_KEY
                })

            verification_data = {
                'secret': settings.TURNSTILE_SECRET_KEY,
                'response': turnstile_response
            }
            
            response = requests.post(settings.TURNSTILE_VERIFY_URL, data=verification_data)
            result = response.json()
            
            if not result.get('success', False):
                return render(request, 'auth/register.html', {
                    'error': '人机验证失败，请重试',
                    'turnstile_site_key': settings.TURNSTILE_SITE_KEY
                })
        
        return view_func(request, *args, **kwargs)
    return wrapper

def is_atc(user):
    """检查用户是否是管制员（有任何席位的管制权限）"""
    return len(ATCPermissionGrant.get_available_positions(user)) > 0

# 用户认证相关视图
@verify_turnstile
@login_required
def change_password(request: HttpRequest) -> HttpResponse:
    """处理用户修改密码请求"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # 验证当前密码是否正确
        if not request.user.check_password(current_password):
            return render(request, 'auth/change_password.html', {
                'error': '当前密码不正确',
                'turnstile_site_key': settings.TURNSTILE_SITE_KEY
            })
        
        # 验证两次输入的新密码是否一致
        if new_password != confirm_password:
            return render(request, 'auth/change_password.html', {
                'error': '两次输入的新密码不一致',
                'turnstile_site_key': settings.TURNSTILE_SITE_KEY
            })
            
        try:
            request.user.set_password(new_password)
            request.user.save()
            # 更新用户会话，防止被登出
            login(request, request.user)
            messages.success(request, '密码修改成功！')
            return redirect('activityui:homepage')
        except Exception as e:
            return render(request, 'auth/change_password.html', {
                'error': f'密码修改失败：{str(e)}',
                'turnstile_site_key': settings.TURNSTILE_SITE_KEY
            })
    
    return render(request, 'auth/change_password.html', {
        'turnstile_site_key': settings.TURNSTILE_SITE_KEY
    })

@verify_turnstile
def login_view(request: HttpRequest) -> HttpResponse:
    """处理用户登录请求"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if username:
            username = username.upper()
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('activityui:homepage')
        else:
            return render(request, 'auth/login.html', {'error': '用户名或密码错误','turnstile_site_key': settings.TURNSTILE_SITE_KEY})
    
    return render(request, 'auth/login.html', {
        'turnstile_site_key': settings.TURNSTILE_SITE_KEY
    })

@verify_turnstile
def register_view(request: HttpRequest) -> HttpResponse:
    """处理用户注册请求"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        # 统一处理用户名大小写
        if username:
            username = username.upper()
            
        if password != confirm_password:
            return render(request, 'auth/register.html', {
                'error': '两次输入的密码不一致',
                'turnstile_site_key': settings.TURNSTILE_SITE_KEY
            })
            
        if User.objects.filter(username=username).exists():
            return render(request, 'auth/register.html', {
                'error': '用户名已存在',
                'turnstile_site_key': settings.TURNSTILE_SITE_KEY
            })
            
        try:
            user = User.objects.create_user(username=username, password=password)
            user.save()
            messages.success(request, '注册成功，请登录')
            return redirect('activityui:login')
        except Exception as e:
            return render(request, 'auth/register.html', {
                'error': f'注册失败：{str(e)}',
                'turnstile_site_key': settings.TURNSTILE_SITE_KEY
            })
            
    return render(request, 'auth/register.html', {
        'turnstile_site_key': settings.TURNSTILE_SITE_KEY
    })

def logout_view(request: HttpRequest) -> HttpResponse:
    """处理用户登出请求"""
    logout(request)
    return redirect('activityui:homepage')

# 活动相关视图
def homepage(request: HttpRequest) -> HttpResponse:
    """显示首页，包含已注册和未来的活动列表（限制显示3个）"""
    if not request.user.is_authenticated:
        return render(request, 'anonymousHomepage.html')
    
    current_date = timezone.now().date()
    
    # 获取用户已报名的活动
    registered_activities = Activity.objects.filter(
        registration__user=request.user,
        date__gte=current_date
    ).order_by('date')
    
    registered_activities_with_status = [{
        'activity': activity,
        'is_registered': True,
        'status': activity.get_status()
    } for activity in registered_activities]
    
    # 获取所有未来活动，但只显示最近3个
    upcoming_activities = Activity.objects.filter(
        date__gte=current_date
    ).order_by('date')[:3]
    
    # 获取已结束的活动
    past_activities = Activity.objects.filter(
        date__lt=current_date
    ).order_by('-date')[:10]  # 只显示最近10个已结束的活动
    
    activities_with_status = []
    for activity in upcoming_activities:
        is_registered = Registration.objects.filter(
            user=request.user,
            activity=activity
        ).exists()
        activities_with_status.append({
            'activity': activity,
            'is_registered': is_registered,
            'status': activity.get_status()
        })
    
    past_activities_with_status = [{
        'activity': activity,
        'is_registered': Registration.objects.filter(user=request.user, activity=activity).exists(),
        'status': 'ended'
    } for activity in past_activities]

    # 计算总飞行时长和管制时长
    crew_registrations = Registration.objects.filter(user=request.user).select_related('activity')
    atc_registrations = ATCRegistration.objects.filter(user=request.user).select_related('activity')
    
    total_flight_minutes = sum(reg.activity.duration_minutes for reg in crew_registrations)
    total_atc_minutes = sum(reg.activity.duration_minutes for reg in atc_registrations)
    
    # 将总分钟数转换为小时和分钟
    total_flight_hours = total_flight_minutes // 60
    total_flight_remaining_minutes = total_flight_minutes % 60
    
    total_atc_hours = total_atc_minutes // 60
    total_atc_remaining_minutes = total_atc_minutes % 60
    
    return render(request, 'homepage.html', {
        'registered_activities': registered_activities_with_status,
        'activities': activities_with_status,
        'past_activities': past_activities_with_status,
        'total_flight_time': {
            'hours': total_flight_hours,
            'minutes': total_flight_remaining_minutes
        },
        'total_atc_time': {
            'hours': total_atc_hours,
            'minutes': total_atc_remaining_minutes
        },
        'is_atc': is_atc(request.user)
    })

@login_required
def upcoming_activities(request: HttpRequest) -> HttpResponse:
    """显示所有计划中的活动"""
    current_date = timezone.now().date()
    
    # 获取所有未来活动
    upcoming_activities = Activity.objects.filter(
        date__gte=current_date
    ).order_by('date')
    
    activities_with_status = []
    for activity in upcoming_activities:
        is_registered = Registration.objects.filter(
            user=request.user,
            activity=activity
        ).exists()
        activities_with_status.append({
            'activity': activity,
            'is_registered': is_registered,
            'status': activity.get_status()
        })
    
    return render(request, 'upcoming_activities.html', {
        'activities': activities_with_status,
    })

def activity_detail(request: HttpRequest, activity_id: int) -> HttpResponse:
    """显示活动详情"""
    if not request.user.is_authenticated:
        return redirect('activityui:login')
    
    activity = get_object_or_404(Activity, id=activity_id)
    is_registered = Registration.objects.filter(
        user=request.user,
        activity=activity
    ).exists()
    
    is_atc_registered = ATCRegistration.objects.filter(
        user=request.user,
        activity=activity
    ).exists()

    crew_registers = Registration.objects.filter(activity=activity)
    atc_registers = ATCRegistration.objects.filter(activity=activity)
    
    # 获取用户可用的管制席位
    available_positions = ATCPermissionGrant.get_available_positions(request.user)
    
    return render(request, 'activity_detail.html', {
        'activity': activity,
        'is_registered': is_registered,
        'is_atc_registered': is_atc_registered,
        'has_atc_permission': len(available_positions) > 0,  # 判断是否有管制权限
        'crew_registers': crew_registers,
        'atc_registers': atc_registers,
        'can_register': activity.can_register(),
    })

@login_required
def register_activity(request: HttpRequest, activity_id: int) -> HttpResponse:
    """处理活动报名请求"""
    activity = get_object_or_404(Activity, pk=activity_id)
    
    if not activity.can_register():
        messages.error(request, '该活动已不能报名')
        return redirect('activityui:activity_detail', activity_id=activity_id)
    
    if request.method == 'GET':
        return render(request, 'register_form.html', {'activity': activity})
    
    elif request.method == 'POST':
        try:
            Registration.objects.create(
                user=request.user,
                activity=activity,
                aircraft=request.POST.get('aircraft'),
                flt_nbr=request.POST.get('flt_nbr')
            )
            messages.success(request, '报名成功！')
            return redirect('activityui:activity_detail', activity_id=activity_id)
        except IntegrityError:
            messages.error(request, '您已经报名过这个活动了')
            return redirect('activityui:activity_detail', activity_id=activity_id)
        except Exception as e:
            messages.error(request, f'报名失败：{str(e)}')
            return redirect('activityui:register_activity', activity_id=activity_id)

@login_required
def register_atc(request: HttpRequest, activity_id: int) -> HttpResponse:
    """处理管制员报名请求"""
    activity = get_object_or_404(Activity, pk=activity_id)
    
    if not activity.can_register():
        messages.error(request, '该活动已不能报名')
        return redirect('activityui:activity_detail', activity_id=activity_id)
    
    # 获取用户可用的管制席位
    available_positions = ATCPermissionGrant.get_available_positions(request.user)
    if not available_positions:
        messages.error(request, '您没有任何管制席位的权限')
        return redirect('activityui:activity_detail', activity_id=activity_id)
    
    if request.method == 'GET':
        # 获取该活动已经被报名的席位
        occupied_seats = ATCRegistration.objects.filter(
            activity=activity
        ).values_list('seat', flat=True)
        
        # 获取所有席位及其权限状态
        all_positions = []
        for pos, label in ATCPermissionGrant.POSITION_CHOICES:
            permission = ATCPermissionGrant.get_user_position_permission(request.user, pos)
            is_occupied = pos in occupied_seats
            all_positions.append({
                'code': pos,
                'label': label,
                'enabled': (permission in ['TRN', 'RLD']) and not is_occupied,
                'permission': permission,
                'occupied': is_occupied
            })
        
        return render(request, 'atc_register_form.html', {
            'activity': activity,
            'positions': all_positions
        })
    
    elif request.method == 'POST':
        selected_position = request.POST.get('seat')
        if not selected_position:
            messages.error(request, '请选择管制席位')
            return redirect('activityui:register_atc', activity_id=activity_id)
            
        # 验证用户是否有权限管制该席位
        if selected_position not in available_positions:
            messages.error(request, '您没有该席位的管制权限')
            return redirect('activityui:register_atc', activity_id=activity_id)
        
        # 检查该席位是否已被他人报名
        if ATCRegistration.objects.filter(activity=activity, seat=selected_position).exists():
            messages.error(request, '该席位已被他人报名')
            return redirect('activityui:register_atc', activity_id=activity_id)
            
        try:
            ATCRegistration.objects.create(
                user=request.user,
                activity=activity,
                seat=selected_position
            )
            messages.success(request, '报名成功！')
            return redirect('activityui:activity_detail', activity_id=activity_id)
        except IntegrityError as e:
            if 'activity_id, seat' in str(e):
                messages.error(request, '该席位已被他人报名')
            else:
                messages.error(request, '您已经报名过这个活动了')
            return redirect('activityui:activity_detail', activity_id=activity_id)
        except Exception as e:
            messages.error(request, f'报名失败：{str(e)}')
            return redirect('activityui:register_atc', activity_id=activity_id)

# 特殊功能视图
@login_required
@xframe_options_exempt
def boarding_pass(request: HttpRequest, activity_id: int) -> HttpResponse:
    """生成登机牌页面"""
    activity = get_object_or_404(Activity, id=activity_id)
    registration = get_object_or_404(Registration, user=request.user, activity=activity)
    
    return render(request, 'boarding_pass.html', {
        'activity': activity,
        'registration': registration
    })

def fetch_metar_taf(icao: str) -> dict:
    """获取指定机场的天气数据"""
    try:
        headers = {
            'Authorization': f'Bearer {settings.AVWX_API_TOKEN}'
        }
        
        metar_resp = requests.get(
            f'{settings.AVWX_API_BASE_URL}/metar/{icao}',
            headers=headers
        ).json()
        taf_resp = requests.get(
            f'{settings.AVWX_API_BASE_URL}/taf/{icao}',
            headers=headers
        ).json()
        
        return {
            'success': True,
            'data': {
                'metar': metar_resp.get('raw', '暂无数据'),
                'taf': taf_resp.get('raw', '暂无数据')
            }
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

@login_required
@require_http_methods(["GET"])
def departure_weather_api(request, activity_id):
    """始发站天气数据API端点"""
    activity = get_object_or_404(Activity, pk=activity_id)
    result = fetch_metar_taf(activity.departure)
    return JsonResponse(result)

@login_required
@require_http_methods(["GET"])
def arrival_weather_api(request, activity_id):
    """到达站天气数据API端点"""
    activity = get_object_or_404(Activity, pk=activity_id)
    result = fetch_metar_taf(activity.arrival)
    return JsonResponse(result)

@login_required
def get_weather(request: HttpRequest, activity_id: int) -> HttpResponse:
    """获取活动相关机场的天气信息页面"""
    activity = get_object_or_404(Activity, pk=activity_id)
    return render(request, 'weather.html', {
        'activity': activity
    })

@login_required
def user_profile(request: HttpRequest, username: str) -> HttpResponse:
    """显示用户的个人页面"""
    user = get_object_or_404(User, username=username)
    current_date = timezone.now().date()
    
    # 获取用户的所有报名记录（包括已结束的活动）
    crew_registrations = Registration.objects.filter(user=user).select_related('activity').order_by('-activity__date')
    atc_registrations = ATCRegistration.objects.filter(user=user).select_related('activity').order_by('-activity__date')
    
    # 计算总飞行时长和管制时长（分钟）
    total_flight_minutes = sum(reg.activity.duration_minutes for reg in crew_registrations)
    total_atc_minutes = sum(reg.activity.duration_minutes for reg in atc_registrations)
    
    # 将总分钟数转换为小时和分钟
    total_flight_hours = total_flight_minutes // 60
    total_flight_remaining_minutes = total_flight_minutes % 60
    
    total_atc_hours = total_atc_minutes // 60
    total_atc_remaining_minutes = total_atc_minutes % 60
    
    # 按状态分类活动
    upcoming_activities = []
    past_activities = []
    
    # 处理机组活动
    for reg in crew_registrations:
        activity_info = {
            'activity': reg.activity,
            'role': '机组',
            'detail': f'{reg.aircraft} - {reg.flt_nbr}',
            'status': reg.activity.get_status()
        }
        if reg.activity.date >= current_date:
            upcoming_activities.append(activity_info)
        else:
            past_activities.append(activity_info)
            
    # 处理管制活动
    for reg in atc_registrations:
        activity_info = {
            'activity': reg.activity,
            'role': '管制员',
            'detail': f'席位：{reg.seat}',
            'status': reg.activity.get_status()
        }
        if reg.activity.date >= current_date:
            upcoming_activities.append(activity_info)
        else:
            past_activities.append(activity_info)
    
    # 按日期排序
    upcoming_activities.sort(key=lambda x: (x['activity'].date, x['activity'].time))
    past_activities.sort(key=lambda x: (x['activity'].date, x['activity'].time), reverse=True)
    
    context = {
        'profile_user': user,  # 避免与 request.user 混淆
        'upcoming_activities': upcoming_activities,
        'past_activities': past_activities,
        'total_flight_time': {
            'hours': total_flight_hours,
            'minutes': total_flight_remaining_minutes
        },
        'total_atc_time': {
            'hours': total_atc_hours,
            'minutes': total_atc_remaining_minutes
        },
        'is_self': request.user == user,
        'is_atc': is_atc(user)
    }
    
    return render(request, 'user_profile.html', context)

@login_required
def past_activities(request):
    current_datetime = timezone.now()
    current_date = current_datetime.date()
    
    # 获取所有日期早于今天的活动
    past_date_activities = Activity.objects.filter(date__lt=current_date)
    
    # 获取今天的活动中已结束的
    today_ended_activities = Activity.objects.filter(
        date=current_date,
        end_time__lt=current_datetime.time()
    )
    
    # 合并两个查询集
    past_activities = past_date_activities.union(today_ended_activities).order_by('-date', '-time')
    
    activities_data = []
    for activity in past_activities:
        is_registered = Registration.objects.filter(user=request.user, activity=activity).exists()
        activities_data.append({
            'activity': activity,
            'is_registered': is_registered,
        })
    
    return render(request, 'past_activities.html', {
        'past_activities': activities_data,
    })

@login_required
def atc_controllers(request: HttpRequest) -> HttpResponse:
    # 显示所有管制员的权限列表
    # 获取所有拥有管制权限的用户（通过ATCPermissionGrant）
    # 先找到所有具有管制权限的用户ID
    user_ids = ATCPermissionGrant.objects.values_list('user', flat=True).distinct()
    # 获取所有相关用户并排序
    atc_users = User.objects.filter(id__in=user_ids).order_by('username')
    
    controllers = []
    for user in atc_users:
        # 获取用户在所有席位的权限
        user_permissions = {}
        for position, _ in ATCPermissionGrant.POSITION_CHOICES:
            permission = ATCPermissionGrant.get_user_position_permission(user, position)
            user_permissions[position] = permission
        
        controllers.append({
            'username': user.username,
            'permissions': user_permissions
        })
    
    context = {
        'controllers': controllers,
        'positions': ATCPermissionGrant.POSITION_CHOICES
    }
    return render(request, 'atc_controllers.html', context)