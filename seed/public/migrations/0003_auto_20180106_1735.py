# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-01-07 01:35
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('public', '0002_auto_20160411_1139'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sharedbuildingfield',
            name='field',
        ),
        migrations.RemoveField(
            model_name='sharedbuildingfield',
            name='org',
        ),
        migrations.DeleteModel(
            name='SharedBuildingField',
        ),
    ]
