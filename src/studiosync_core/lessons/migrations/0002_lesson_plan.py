from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('lessons', '0001_initial'),
        ('resources', '0002_resource_file_upload'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LessonPlan',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('content', models.TextField(help_text='Markdown content describing the plan structure')),
                ('difficulty_level', models.CharField(choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')], default='beginner', max_length=20)),
                ('estimated_duration_minutes', models.IntegerField(default=30)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('is_public', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_lesson_plans', to='core.teacher')),
                ('resources', models.ManyToManyField(blank=True, related_name='lesson_plans', to='resources.resource')),
            ],
            options={
                'db_table': 'lesson_plans',
                'ordering': ['-created_at'],
            },
        ),
    ]
