"""
Management command: seed data awal untuk Garden Journal.

Usage:
    python manage.py seed_journal
    python manage.py seed_journal --username azizah
    python manage.py seed_journal --username azizah --count 20
"""

import random
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from garden_journal.models import GardenJournal

SAMPLE_DATA = [
    {"title": "Monstera Daun Baru Merekah", "plant": "Monstera Deliciosa", "ecopatch": "Balkon Timur", "condition": "healthy", "cover": "flowers"},
    {"title": "Cabai Rawit Mulai Berbunga", "plant": "Cabai Rawit", "ecopatch": "Teras Depan", "condition": "flowering", "cover": "seeds"},
    {"title": "Tomat Ceri Perlu Dipangkas", "plant": "Tomat Ceri", "ecopatch": "Balkon Timur", "condition": "needs_attention", "cover": "brushes"},
    {"title": "Kemangi Siap Panen", "plant": "Kemangi", "ecopatch": "Indoor Dapur", "condition": "ready_to_harvest", "cover": "soft"},
    {"title": "Lidah Mertua Tumbuh Anak", "plant": "Lidah Mertua", "ecopatch": "Windowsill Kamar", "condition": "healthy", "cover": "dots"},
    {"title": "Sirih Gading Layu Kekeringan", "plant": "Sirih Gading", "ecopatch": "Indoor Dapur", "condition": "wilting", "cover": "seeds"},
    {"title": "Selada Tumbuh Subur", "plant": "Selada", "ecopatch": "Balkon Timur", "condition": "healthy", "cover": "brushes"},
    {"title": "Bunga Matahari Mekar Sempurna", "plant": "Bunga Matahari", "ecopatch": "Teras Depan", "condition": "flowering", "cover": "flowers"},
]

SAMPLE_NOTES = [
    "Kondisi tanaman terlihat segar setelah disiram pagi tadi. Daun-daun baru bermunculan di ujung batang.",
    "Ada tanda-tanda serangan hama pada beberapa daun. Perlu diberi pestisida organik.",
    "Tanah terasa kering meskipun baru disiram kemarin. Mungkin pot terlalu kecil.",
    "Berhasil memindahkan dari pot lama ke pot baru yang lebih besar. Semoga cepat adaptasi.",
    "Cuaca hari ini sangat terik. Tanaman ditempatkan di tempat yang lebih teduh.",
    "Pemberian pupuk kompos tadi pagi. Berharap dalam seminggu hasilnya terlihat.",
    "Daun bagian bawah mulai menguning — kemungkinan kekurangan nitrogen.",
    "Tinggi tanaman meningkat sekitar 5 cm dalam seminggu terakhir. Pertumbuhannya memuaskan!",
    "Musim hujan membuat tanah terlalu lembab. Pastikan drainase pot berjalan baik.",
    "Hari ini pertama kali bunga mekar! Warnanya cantik sekali, semoga cepat jadi buah.",
]


class Command(BaseCommand):
    help = "Seed contoh data Garden Journal"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            default=None,
            help="Username yang akan di-seed (default: user pertama yang ada)",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=15,
            help="Jumlah entri jurnal yang dibuat (default: 15)",
        )

    def handle(self, *args, **options):
        username = options["username"]
        count = options["count"]

        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stderr.write(f"User '{username}' tidak ditemukan.")
                return
        else:
            user = User.objects.filter(is_superuser=False).first() or User.objects.first()
            if not user:
                self.stderr.write(
                    "Tidak ada user. Buat dulu: python manage.py createsuperuser"
                )
                return

        self.stdout.write(f"Seeding {count} entri Garden Journal untuk user: {user.username} ...")

        today = date.today()
        created = 0

        for i in range(count):
            sample = random.choice(SAMPLE_DATA)
            entry_date = today - timedelta(days=random.randint(0, 90))
            height = round(random.uniform(5.0, 80.0), 1) if random.random() > 0.3 else None

            GardenJournal.objects.create(
                user=user,
                date=entry_date,
                title=sample["title"],
                notes=random.choice(SAMPLE_NOTES),
                plant_condition=sample["condition"],
                plant_height=height,
                cover_pattern=sample.get("cover", "flowers"),
                ecopatch_name=sample["ecopatch"],
                plant_name=sample["plant"],
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(f"✅ Berhasil membuat {created} entri Garden Journal.")
        )
