# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2017-09-18 15:50
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seed', '0071_auto_20170721_1203'),
    ]

    operations = [
        migrations.AlterField(
            model_name='noncanonicalprojectbuildings',
            name='projectbuilding',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='seed.ProjectBuilding'),
        ),
    ]