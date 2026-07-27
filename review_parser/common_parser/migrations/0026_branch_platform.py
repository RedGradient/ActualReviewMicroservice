import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common_parser", "0025_alter_video_preview"),
    ]

    operations = [
        migrations.CreateModel(
            name="BranchPlatform",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("google", "Google"),
                            ("yandex", "Yandex"),
                            ("2gis", "2GIS"),
                            ("vlru", "VL.ru"),
                        ],
                        max_length=20,
                    ),
                ),
                ("url", models.URLField(blank=True, max_length=500, null=True)),
                ("org_id", models.CharField(blank=True, max_length=128, null=True)),
                ("review_count", models.PositiveIntegerField(blank=True, null=True)),
                ("review_avg", models.DecimalField(blank=True, decimal_places=2, max_digits=3, null=True)),
                ("parsed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "branch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="source",
                        to="common_parser.branch",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="branchplatform",
            constraint=models.UniqueConstraint(
                fields=("branch", "provider"),
                name="unique_branch_provider",
            ),
        ),
        migrations.AddField(
            model_name="review",
            name="branch_platform",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reviews",
                to="common_parser.branchplatform",
            ),
        ),
        migrations.RemoveField(
            model_name="review",
            name="branch",
        ),
        migrations.RemoveField(
            model_name="review",
            name="provider",
        ),
        migrations.AlterField(
            model_name="review",
            name="branch_platform",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reviews",
                to="common_parser.branchplatform",
            ),
        ),
        migrations.RemoveField(model_name="branch", name="google_map_url"),
        migrations.RemoveField(model_name="branch", name="google_review_count"),
        migrations.RemoveField(model_name="branch", name="google_review_avg"),
        migrations.RemoveField(model_name="branch", name="google_parse_date"),
        migrations.RemoveField(model_name="branch", name="yandex_map_url"),
        migrations.RemoveField(model_name="branch", name="yandex_review_count"),
        migrations.RemoveField(model_name="branch", name="yandex_review_avg"),
        migrations.RemoveField(model_name="branch", name="yandex_parse_date"),
        migrations.RemoveField(model_name="branch", name="twogis_map_url"),
        migrations.RemoveField(model_name="branch", name="twogis_review_count"),
        migrations.RemoveField(model_name="branch", name="twogis_review_avg"),
        migrations.RemoveField(model_name="branch", name="twogis_parse_date"),
        migrations.RemoveField(model_name="branch", name="vlru_url"),
        migrations.RemoveField(model_name="branch", name="vlru_org_id"),
        migrations.RemoveField(model_name="branch", name="vlru_review_count"),
        migrations.RemoveField(model_name="branch", name="vlru_review_avg"),
        migrations.RemoveField(model_name="branch", name="vlru_parse_date"),
    ]
