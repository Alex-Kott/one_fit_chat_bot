# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-09-27 15:59
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0012_auto_20170926_1341'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trainer',
            name='id',
            field=models.IntegerField(primary_key=True, serialize=False),
        ),
    ]