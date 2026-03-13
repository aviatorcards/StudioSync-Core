from django.db import migrations, models
import studiosync_core.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_remove_student_skill_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="studio",
            name="logo",
            field=models.ImageField(
                blank=True,
                help_text="Studio logo (max 5MB, JPG/PNG/GIF/WebP)",
                null=True,
                upload_to="studio_logos/",
                validators=[studiosync_core.core.validators.validate_image],
            ),
        ),
    ]
