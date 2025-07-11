from django.db import models
from django.contrib.auth.models import User

class Activity(models.Model):
    name = models.CharField(max_length=255, verbose_name='活动名称')
    date = models.DateField(verbose_name='活动日期')
    time = models.TimeField(verbose_name='活动时间')
    end_time = models.TimeField(verbose_name='结束时间', null=True)
    description = models.TextField(verbose_name='活动描述')
    capacity = models.IntegerField(verbose_name='活动容量', default=999)
    departure = models.CharField(max_length=4, verbose_name='始发')
    arrival = models.CharField(max_length=4, verbose_name='目的')

    class Meta:
        verbose_name = '活动'
        verbose_name_plural = '活动'

    def __str__(self):
        return f'{self.name} - {self.date}'

    @property
    def duration_minutes(self):
        import datetime
        
        if not self.end_time:
            # 如果没有设置结束时间，默认为1小时
            return 60
            
        # 转换为datetime以便计算时间差
        start_dt = datetime.datetime.combine(datetime.date.today(), self.time)
        end_dt = datetime.datetime.combine(datetime.date.today(), self.end_time)
        
        # 处理跨日的情况
        if end_dt < start_dt:
            end_dt += datetime.timedelta(days=1)
            
        duration = end_dt - start_dt
        return int(duration.total_seconds() / 60)

    def get_status(self):
        import datetime
        
        # 由于 USE_TZ = False，我们直接使用 datetime.now()
        now = datetime.datetime.now()
        activity_datetime = datetime.datetime.combine(self.date, self.time)
        
        # 如果没有设置结束时间，默认为开始时间后一小时
        if not self.end_time:
            end_datetime = activity_datetime + datetime.timedelta(hours=1)
        else:
            end_datetime = datetime.datetime.combine(self.date, self.end_time)
            # 处理跨日的情况
            if end_datetime < activity_datetime:
                end_datetime += datetime.timedelta(days=1)
        
        # 计算距离活动开始和结束的时间差
        time_until_start = activity_datetime - now
        time_until_end = end_datetime - now
        
        if time_until_end.total_seconds() < 0:
            return 'ended'  # 活动已结束
        elif time_until_start.total_seconds() <= 600:  # 10分钟 = 600秒
            return 'starting_soon'  # 活动即将开始（10分钟内）
        else:
            return 'upcoming'  # 即将举行的活动

    def can_register(self):
        return self.get_status() == 'upcoming'

class Registration(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, verbose_name='活动')
    register_time = models.DateTimeField(auto_now_add=True, verbose_name='报名时间')
    aircraft = models.TextField(max_length=255, verbose_name="机型")
    flt_nbr = models.TextField(max_length=8, verbose_name="航班号")

    class Meta:
        verbose_name = '报名记录'
        verbose_name_plural = '报名记录'
        # 确保用户不能重复报名同一个活动
        unique_together = ['user', 'activity']

    def __str__(self):
        return f'{self.user.username} - {self.activity.name}'

class ATCRegistration(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, verbose_name='活动')
    register_time = models.DateTimeField(auto_now_add=True, verbose_name='报名时间')
    seat = models.CharField(max_length=16, verbose_name='席位')

    class Meta:
        verbose_name = '管制员报名记录'
        verbose_name_plural = '管制员报名记录'
        # 确保用户不能重复报名同一个活动，且同一席位不能被多人报名
        unique_together = [
            ['user', 'activity'],  # 一个用户不能重复报名同一活动
            ['activity', 'seat'],  # 一个活动的同一席位只能被一人报名
        ]

    def __str__(self):
        return f'{self.user.username} - {self.activity.name}'

class ATCPermissionGrant(models.Model):
    POSITION_CHOICES = [
        ('DEL', '放行'),
        ('GND', '地面'),
        ('TWR', '塔台'),
        ('APP', '进近'),
        ('CTR', '区调'),
        ('FSS', '飞服'),
        ('PTW', '程序塔台'),
        ('APN', '机坪')
    ]
    
    PERMISSION_CHOICES = [
        ('TRN', '实习中'),
        ('RLD', '已放单')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    position = models.CharField(max_length=3, choices=POSITION_CHOICES, verbose_name='席位')
    permission = models.CharField(max_length=3, choices=PERMISSION_CHOICES, default='TRN', verbose_name='权限级别')
    granted_time = models.DateTimeField(auto_now_add=True, verbose_name='授权时间')
    last_modified = models.DateTimeField(auto_now=True, verbose_name='最后修改')

    class Meta:
        verbose_name = '管制权限'
        verbose_name_plural = '管制权限'
        unique_together = ['user', 'position']
        
    def __str__(self):
        return f'{self.user.username} - {self.get_position_display()} - {self.get_permission_display()}'
        
    def can_control(self):
        """判断是否有权限管制该席位"""
        return self.permission in ['TRN', 'RLD']
        
    @classmethod
    def get_user_position_permission(cls, user, position):
        """获取用户在特定席位的权限级别"""
        try:
            grant = cls.objects.get(user=user, position=position)
            return grant.permission
        except cls.DoesNotExist:
            return None  # 没有权限记录
    
    @classmethod
    def can_control_position(cls, user, position):
        """检查用户是否有权限管制特定席位"""
        permission = cls.get_user_position_permission(user, position)
        return permission in ['TRN', 'RLD']
    
    @classmethod
    def get_available_positions(cls, user):
        """获取用户可以管制的所有席位"""
        available_positions = []
        for position, _ in cls.POSITION_CHOICES:
            if cls.can_control_position(user, position):
                available_positions.append(position)
        return available_positions