from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='resource',
            name='file_path',
        ),
        migrations.AddField(
            model_name='resource',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='resources/%Y/%m/'),
        ),
    ]
