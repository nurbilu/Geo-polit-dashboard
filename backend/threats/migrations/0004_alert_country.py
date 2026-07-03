from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("threats", "0003_alert_clustering"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="country",
            field=models.CharField(
                choices=[
                    ("israel", "Israel"),
                    ("lebanon", "Lebanon"),
                    ("syria", "Syria"),
                    ("jordan", "Jordan"),
                    ("egypt", "Egypt"),
                    ("iraq", "Iraq"),
                    ("arabian_peninsula", "Arabian Peninsula"),
                    ("gulf_states", "Persian Gulf States"),
                    ("iran", "Iran"),
                    ("turkey", "Turkey"),
                    ("mediterranean", "Mediterranean Region"),
                    ("unknown", "Unknown"),
                ],
                default="unknown",
                help_text="Country / macro-area the item concerns (Middle East coverage).",
                max_length=32,
            ),
        ),
    ]
