# Generated by Django 3.0.7 on 2021-03-31 09:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0026_auto_20210331_0117'),
    ]

    operations = [
        migrations.AlterField(
            model_name='atomiccoordinate',
            name='coord_1',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='atomiccoordinate',
            name='coord_2',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='atomiccoordinate',
            name='coord_3',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
