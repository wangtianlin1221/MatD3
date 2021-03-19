# Generated by Django 3.0.7 on 2021-03-19 03:51

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('materials', '0009_auto_20210311_1936'),
    ]

    operations = [
        migrations.AddField(
            model_name='bondlength',
            name='compound',
            field=models.ForeignKey(default=-1, on_delete=django.db.models.deletion.CASCADE, related_name='bond_length', to='materials.Compound'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='bondlength',
            name='data_source',
            field=models.PositiveSmallIntegerField(choices=[(0, 'Experimental'), (1, 'Averaged')], default=0),
        ),
        migrations.AddField(
            model_name='bondlength',
            name='r_label',
            field=models.PositiveSmallIntegerField(choices=[(0, 'I-X'), (1, "II,I'-X"), (2, 'IV,V-X')], default=0),
        ),
        migrations.AddField(
            model_name='tolerancefactor',
            name='compound',
            field=models.ForeignKey(default=-1, on_delete=django.db.models.deletion.CASCADE, related_name='tolerance_factors', to='materials.Compound'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='tolerancefactor',
            name='t_IV_V',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ShannonIonicRadii',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now)),
                ('element_label', models.PositiveSmallIntegerField(choices=[(0, 'element I'), (1, 'element II'), (2, 'element IV'), (3, 'element X')], default=0)),
                ('charge', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('coordination', models.CharField(blank=True, max_length=20)),
                ('ionic_radius', models.FloatField(blank=True, null=True)),
                ('key', models.CharField(blank=True, max_length=20)),
                ('compound', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shannon_ionic_radiis', to='materials.Compound')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='materials_shannonionicradii_created_by', to=settings.AUTH_USER_MODEL)),
                ('subset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shannon_ionic_radiis', to='materials.Subset')),
                ('updated_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='materials_shannonionicradii_updated_by', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
