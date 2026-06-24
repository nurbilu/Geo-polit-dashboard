from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("threats", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="summary_hebrew",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Concise Hebrew translation/summary produced by Llama 4 Scout.",
            ),
        ),
    ]
