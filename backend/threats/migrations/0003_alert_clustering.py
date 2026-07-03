import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("threats", "0002_alert_summary_hebrew"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="parent_alert",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="clustered_updates",
                to="threats.alert",
                help_text="Primary alert this item was clustered under, if a duplicate.",
            ),
        ),
        migrations.AddField(
            model_name="alert",
            name="cluster_count",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Number of messages grouped under this primary alert (incl. itself).",
            ),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(
                fields=["region", "analyzed_at"], name="alert_region_analyzed_idx"
            ),
        ),
    ]
