from django.db import models


class QualityProjectLink(models.Model):
    project = models.OneToOneField(
        "projects.Project", on_delete=models.CASCADE, related_name="quality_link"
    )
    specwright_project_id = models.PositiveBigIntegerField(unique=True)
    specwright_project_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.project.slug} -> Specwright {self.specwright_project_id}"
