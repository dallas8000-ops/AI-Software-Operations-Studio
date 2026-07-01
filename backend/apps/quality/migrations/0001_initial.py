from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [("projects", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="QualityProjectLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("specwright_project_id", models.PositiveBigIntegerField(unique=True)),
                ("specwright_project_name", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="quality_link", to="projects.project")),
            ],
        )
    ]
