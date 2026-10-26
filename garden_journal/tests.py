from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import GardenJournal


class GardenJournalModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.journal = GardenJournal.objects.create(
            user=self.user,
            title="Tanaman Tumbuh Subur",
            date=date.today(),
            notes="Catatan harian tanaman",
            plant_condition="healthy",
            plant_height=12.5,
            plant_name="Tomat",
            ecopatch_name="Balkon",
            cover_pattern="brushes",
        )

    def test_journal_str(self):
        self.assertIn("Tanaman Tumbuh Subur", str(self.journal))

    def test_badge_color_property(self):
        self.assertEqual(self.journal.get_condition_display_badge, "success")


class GardenJournalViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="azizah", password="password123")
        self.other_user = User.objects.create_user(username="other", password="password123")
        self.journal = GardenJournal.objects.create(
            user=self.user,
            title="Catatan Azizah",
            date=date.today(),
            notes="Tes catatan",
            plant_condition="healthy",
            plant_name="Cabai",
            ecopatch_name="Teras",
            cover_pattern="seeds",
        )

    def test_guest_redirected_to_login(self):
        response = self.client.get(reverse("garden_journal:list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_user_can_view_own_journals(self):
        self.client.login(username="azizah", password="password123")
        response = self.client.get(reverse("garden_journal:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cabai")

    def test_user_cannot_view_others_journal(self):
        self.client.login(username="other", password="password123")
        response = self.client.get(reverse("garden_journal:detail", args=[self.journal.pk]))
        self.assertEqual(response.status_code, 404)

    def test_create_journal(self):
        self.client.login(username="azizah", password="password123")
        response = self.client.post(
            reverse("garden_journal:create"),
            {
                "title": "Catatan Baru",
                "date": str(date.today()),
                "plant_condition": "flowering",
                "notes": "Bunga mulai mekar",
                "plant_name": "Melati",
                "ecopatch_name": "Teras Depan",
                "plant_height": "15.0",
                "cover_pattern": "flowers",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(GardenJournal.objects.filter(title="Catatan Baru", user=self.user).exists())

    def test_edit_journal(self):
        self.client.login(username="azizah", password="password123")
        response = self.client.post(
            reverse("garden_journal:edit", args=[self.journal.pk]),
            {
                "title": "Catatan Azizah Update",
                "date": str(self.journal.date),
                "plant_condition": "fruiting",
                "notes": "Sudah berbuah!",
                "plant_name": "Cabai",
                "ecopatch_name": "Teras",
                "plant_height": "20.0",
                "cover_pattern": "dots",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.journal.refresh_from_db()
        self.assertEqual(self.journal.title, "Catatan Azizah Update")
        self.assertEqual(self.journal.plant_condition, "fruiting")

    def test_delete_journal(self):
        self.client.login(username="azizah", password="password123")
        response = self.client.post(reverse("garden_journal:delete", args=[self.journal.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GardenJournal.objects.filter(pk=self.journal.pk).exists())

    def test_filter_ajax(self):
        self.client.login(username="azizah", password="password123")
        response = self.client.get(reverse("garden_journal:filter_ajax"), {"plant_name": "Cabai"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cabai")

        response_empty = self.client.get(reverse("garden_journal:filter_ajax"), {"plant_name": "NonExistent"})
        self.assertEqual(response_empty.status_code, 200)
        self.assertNotContains(response_empty, "Cabai")

    def test_plant_history_view(self):
        self.client.login(username="azizah", password="password123")
        response = self.client.get(reverse("garden_journal:plant_history", args=["Cabai"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Buku Jurnal: Cabai")
        self.assertContains(response, "Catatan Azizah")
