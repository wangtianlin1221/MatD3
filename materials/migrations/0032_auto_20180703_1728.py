# Generated by Django 2.0.1 on 2018-07-03 17:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0031_auto_20180628_1952'),
    ]

    operations = [
        migrations.RenameField(
            model_name='publication',
            old_name='num_authors',
            new_name='author_count',
        ),
        migrations.RemoveField(
            model_name='author',
            name='publication',
        ),
        migrations.AddField(
            model_name='author',
            name='publication',
            field=models.ManyToManyField(to='materials.Publication'),
        ),
    ]
