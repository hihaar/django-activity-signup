# Generated by Django 4.2.20 on 2025-05-18 11:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activityui', '0012_alter_atcpermissiongrant_permission'),
    ]

    operations = [
        migrations.AlterField(
            model_name='atcpermissiongrant',
            name='position',
            field=models.CharField(choices=[('DEL', '放行'), ('GND', '地面'), ('TWR', '塔台'), ('APP', '进近'), ('CTR', '区调'), ('FIS', '飞服'), ('PTW', '程序塔台')], max_length=3, verbose_name='席位'),
        ),
    ]
