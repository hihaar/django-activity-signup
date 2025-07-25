# Generated by Django 4.2.20 on 2025-05-10 15:17

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('activityui', '0002_alter_activity_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('register_time', models.DateTimeField(auto_now_add=True, verbose_name='报名时间')),
                ('activity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='activityui.activity', verbose_name='活动')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '报名记录',
                'verbose_name_plural': '报名记录',
                'unique_together': {('user', 'activity')},
            },
        ),
    ]
