# Generated by Django 2.0.1 on 2018-03-20 18:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0020_excitonemission_plotted'),
    ]

    operations = [
        migrations.AddField(
            model_name='atomicpositions',
            name='plotted',
            field=models.BooleanField(default=False),
        ),
    ]
