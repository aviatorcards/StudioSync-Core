# Generated migration for adding lesson_plan field to Lesson model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('lessons', '0005_lesson_room'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='lesson_plan',
            field=models.ForeignKey(
                blank=True,
                help_text='Optional lesson plan template used for this lesson',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='lessons',
                to='lessons.lessonplan'
            ),
        ),
    ]
