from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse, NoReverseMatch  # 添加NoReverseMatch异常
from django.db import transaction
from django.contrib import messages
from django.contrib.admin.models import LogEntry  # 导入LogEntry模型
from django.utils.html import format_html  # 用于格式化HTML内容
from .models import Activity, Registration, ATCRegistration, ATCPermissionGrant

admin.site.site_header = "Xiamen Airlines Admin"
admin.site.site_title = "Xiamen Airlines Admin Portal"
admin.site.index_title = "Welcome to Xiamen Airlines Admin"

def add_to_atc_group(modeladmin, request, queryset):
    atc_group, created = Group.objects.get_or_create(name='ATC')
    for user in queryset:
        user.groups.add(atc_group)
    modeladmin.message_user(request, f'成功将选中的用户添加到ATC组')
add_to_atc_group.short_description = '添加选中用户到ATC组'

def edit_atc_permissions(modeladmin, request, queryset):
    if request.POST.get('post') == 'yes':
        # 处理权限更新
        selected_users = list(queryset.all())  # 保存查询集中的用户，转换为列表以避免懒加载
        n = 0  # 更新计数
        success = True  # 操作是否成功的标志
        
        try:
            with transaction.atomic():  # 使用事务包裹所有数据库操作
                for user in selected_users:
                    for position, position_label in ATCPermissionGrant.POSITION_CHOICES:
                        permission = request.POST.get(f'permission_{position}')
                        
                        # 如果选择了"保持不变"，跳过此席位的更新
                        if permission == 'unchanged':
                            continue
                            
                        # 如果选择了无权限,则删除记录
                        if permission == '':
                            deleted_count = ATCPermissionGrant.objects.filter(
                                user=user,
                                position=position
                            ).delete()[0]
                            if deleted_count > 0:
                                n += 1
                        elif permission in ['TRN', 'RLD']:
                            # 检查是否存在现有权限记录
                            try:
                                existing = ATCPermissionGrant.objects.get(user=user, position=position)
                                if existing.permission != permission:  # 只有在值改变时才更新
                                    print(f" - 权限从 {existing.permission} 更改为 {permission}")
                                    existing.permission = permission
                                    existing.save()
                                    n += 1
                                else:
                                    pass
                            except ATCPermissionGrant.DoesNotExist:
                                # 创建新记录
                                ATCPermissionGrant.objects.create(
                                    user=user,
                                    position=position,
                                    permission=permission
                                )
                                n += 1
                                
                print(f"权限更新完成，共更新 {n} 条记录")
        except Exception as e:
            success = False
            print(f"更新权限时出错: {str(e)}")
            messages.error(request, f'更新权限时出错: {str(e)}')
            
        if success:
            messages.success(request, f'成功更新 {n} 条权限记录')
        
        # 确保正确重定向到用户列表页面
        return HttpResponseRedirect(reverse('admin:auth_user_changelist'))
    
    # 显示权限编辑表单
    # 获取第一个用户的权限作为初始值(多用户编辑时默认使用第一个用户的权限)
    first_user = queryset.first()
    initial_permissions = {}
    if first_user:
        for grant in ATCPermissionGrant.objects.filter(user=first_user):
            initial_permissions[grant.position] = grant.permission
    
    context = {
        'title': '编辑管制权限',
        'queryset': queryset,
        'users': [user.username for user in queryset],
        'user_ids': [str(user.id) for user in queryset],
        'initial_permissions': initial_permissions,
        'positions': ATCPermissionGrant.POSITION_CHOICES,
        'permissions': ATCPermissionGrant.PERMISSION_CHOICES,
        'opts': modeladmin.model._meta,
    }
    return render(request, 'admin/atc_permissions_form.html', context)
edit_atc_permissions.short_description = '编辑选中用户的管制权限'

class CustomUserAdmin(UserAdmin):
    actions = [add_to_atc_group, edit_atc_permissions]

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['name', 'truncated_description', 'date', 'time', 'end_time', 'departure', 'arrival', 'capacity', 'get_registered_count']
    list_filter = ['date', 'departure', 'arrival']
    search_fields = ['name', 'description', 'departure', 'arrival']
    ordering = ['-date', '-time']
    list_per_page = 20
    date_hierarchy = 'date'
    
    def get_registered_count(self, obj):
        return obj.registration_set.count()
    get_registered_count.short_description = '已报名人数'

    def truncated_description(self, obj):
        return obj.description[:100] + '...' if len(obj.description) > 100 else obj.description
    truncated_description.short_description = '活动描述'

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'description', 'date', 'time', 'end_time')
        }),
        ('活动详情', {
            'fields': ('departure', 'arrival', 'capacity'),
        }),
    )

@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ['user', 'activity', 'register_time', 'aircraft', 'flt_nbr']
    list_filter = ['activity', 'register_time']
    search_fields = ['user__username', 'activity__name']
    ordering = ['-register_time']

@admin.register(ATCRegistration)
class ATCRegistrationAdmin(admin.ModelAdmin):
    list_display = ['user', 'activity', 'register_time']
    list_filter = ['activity', 'register_time']
    search_fields = ['user__username', 'activity__name']
    ordering = ['-register_time']

@admin.register(ATCPermissionGrant)
class ATCPermissionGrantAdmin(admin.ModelAdmin):
    list_display = ['user', 'position', 'permission', 'granted_time', 'last_modified']
    list_filter = ['position', 'permission']
    search_fields = ['user__username']
    ordering = ['user__username', 'position']

@admin.register(LogEntry)  # 注册LogEntry模型到管理界面
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'content_type', 'object_id_link', 'action_flag_display', 'change_message_truncated', 'action_time']
    list_filter = ['action_flag', 'action_time', 'content_type']
    search_fields = ['user__username', 'content_type__model', 'object_id', 'change_message']
    ordering = ['-action_time']
    readonly_fields = ['user', 'content_type', 'object_id', 'object_repr', 'action_flag', 'change_message', 'action_time']
    date_hierarchy = 'action_time'
    list_per_page = 20
    
    def object_id_link(self, obj):
        # 为object_id字段添加链接
        try:
            url = reverse(f'admin:{obj.content_type.app_label}_{obj.content_type.model}_change', args=[obj.object_id])
            return format_html('<a href="{}">{}</a>', url, obj.object_id)
        except NoReverseMatch:
            # 如果URL无法解析，则只返回object_id
            return obj.object_id
    object_id_link.short_description = '对象ID'
    object_id_link.admin_order_field = 'object_id'  # 允许根据链接排序
        
    def action_flag_display(self, obj):
        flags = {
            1: '添加',
            2: '修改',
            3: '删除'
        }
        return flags.get(obj.action_flag, '未知')
    action_flag_display.short_description = '操作类型'

    def change_message_truncated(self, obj):
        # 截断change_message以适应列表显示
        return obj.change_message[:50] + '...' if len(obj.change_message) > 50 else obj.change_message
    change_message_truncated.short_description = '更改信息'