# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-10-03 05:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0018_auto_20171002_1953'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='msg_type',
            field=models.TextField(default='text'),
        ),
    ]