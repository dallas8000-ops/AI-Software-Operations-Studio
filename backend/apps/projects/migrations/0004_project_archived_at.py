from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("projects", "0003_project_organization_projectapikey")]

    operations = [
        migrations.AddField(
            model_name="project",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
