# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-09-24 22:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0005_message'),
    ]

    operations = [
        migrations.AlterField(
            model_name='message',
            name='text',
            field=models.TextField(),
        ),
    ]
