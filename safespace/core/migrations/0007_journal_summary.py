from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_new_stickers"),
    ]

    operations = [
        migrations.AddField(
            model_name="journal",
            name="summary",
            field=models.CharField(
                blank=True,
                help_text="Optional one-line overall message of the entry (used by AI quest suggestions).",
                max_length=150,
            ),
        ),
    ]
