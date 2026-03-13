# Generated manually to remove feature_flags tables

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_alter_student_instrument'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DROP TABLE IF EXISTS feature_flags_featureflagoverride;
                DROP TABLE IF EXISTS feature_flags_featureflag;
                DROP TABLE IF EXISTS feature_flags;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
