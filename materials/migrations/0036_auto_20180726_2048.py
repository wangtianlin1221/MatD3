# Generated by Django 2.0.1 on 2018-07-26 20:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0035_auto_20180726_1539'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaterialProperty',
            fields=[
                ('idinfo_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='materials.IDInfo')),
                ('value', models.CharField(max_length=500)),
            ],
            options={
                'verbose_name_plural': 'material properties',
            },
            bases=('materials.idinfo',),
        ),
        migrations.CreateModel(
            name='Property',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('property', models.CharField(max_length=500)),
            ],
            options={
                'verbose_name_plural': 'properties',
            },
        ),
        migrations.AlterModelOptions(
            name='atomicpositions',
            options={'verbose_name_plural': 'atomic positions'},
        ),
        migrations.AddField(
            model_name='materialproperty',
            name='property',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='materials.Property'),
        ),
        migrations.AddField(
            model_name='materialproperty',
            name='system',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='materials.System'),
        ),
    ]
