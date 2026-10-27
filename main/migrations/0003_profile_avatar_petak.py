from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_profile_contact'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='avatar_petak',
            field=models.CharField(
                blank=True,
                choices=[('happy', 'Senang'), ('cheer', 'Semangat'), ('curious', 'Penasaran'), ('proud', 'Bangga')],
                max_length=10,
            ),
        ),
    ]
