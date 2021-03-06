# Generated by Django 3.0.7 on 2021-04-07 07:47

from django.db import migrations, models
import materials.models


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0027_auto_20210331_0537'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subset',
            name='input_data_file',
            field=models.FileField(blank=True, null=True, upload_to=materials.models.data_file_path),
        ),
        migrations.AlterField(
            model_name='subset',
            name='title',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
