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

    def test_list_filter_preserves_search_and_offers_reset(self):
        GardenJournal.objects.create(
            user=self.user,
            title="Catatan Melati",
            date=date.today(),
            notes="Tes catatan",
            plant_condition="flowering",
            plant_name="Melati",
            ecopatch_name="Balkon",
        )
        self.client.login(username="azizah", password="password123")
        response = self.client.get(
            reverse("garden_journal:list"),
            {"ecopatch_name": "Teras", "plant_name": "Cabai"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Buka buku Cabai")
        self.assertNotContains(response, "Buka buku Melati")
        self.assertContains(response, "journal-filter--active")
        # Reset clears dropdown filters but keeps the typed search.
        self.assertContains(response, 'href="/journal/?plant_name=Cabai"')
        # Clearing the search keeps the dropdown filters.
        self.assertContains(response, 'href="/journal/?ecopatch_name=Teras"')

    def test_plant_history_view(self):
        self.client.login(username="azizah", password="password123")
        response = self.client.get(reverse("garden_journal:plant_history", args=["Cabai"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Buku Jurnal: Cabai")
        self.assertContains(response, "Catatan Azizah")

    def test_create_journal_without_ecopatch_shows_warning(self):
        self.client.login(username="azizah", password="password123")
        response = self.client.get(reverse("garden_journal:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kamu Belum Punya EcoPatch")

    def test_create_journal_existing_plant_starts_at_step_2(self):
        from my_ecopatch.models import EcoPatch
        EcoPatch.objects.create(owner=self.user, name="Balkon", space_type="balcony", city="Jakarta")
        self.client.login(username="azizah", password="password123")
        response = self.client.get(reverse("garden_journal:create"), {"plant_name": "Cabai"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["start_at_step_2"])

    def test_edit_journal_starts_at_step_2(self):
        self.client.login(username="azizah", password="password123")
        response = self.client.get(reverse("garden_journal:edit", args=[self.journal.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["start_at_step_2"])
        # Pastikan tidak ada wizard bar dan setup section pada edit
        self.assertNotContains(response, 'id="wizardStepsBar"')
        self.assertNotContains(response, 'id="sectionSetup"')
        self.assertNotContains(response, 'Ubah Setup / Sampul')
        self.assertNotContains(response, 'Kembali ke Setup')

    def test_quick_upload_photo(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.login(username="azizah", password="password123")
        # 1x1 GIF dummy
        dummy_gif = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00"
            b"\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
            b"\x44\x01\x00\x3b"
        )
        photo = SimpleUploadedFile("tanaman.gif", dummy_gif, content_type="image/gif")
        response = self.client.post(
            reverse("garden_journal:upload_photo", args=[self.journal.pk]),
            {"image": photo},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("image_url"))
        self.journal.refresh_from_db()
        self.assertTrue(self.journal.image)

class EcoPatchCascadeJournalTests(TestCase):
    def setUp(self):
        from my_ecopatch.models import EcoPatch

        # User 1 & User 2
        self.user1 = User.objects.create_user(username="haikal", password="password123")
        self.user2 = User.objects.create_user(username="rheina", password="password123")

        # EcoPatches for user 1
        self.patch1 = EcoPatch.objects.create(
            owner=self.user1, name="Kebun Balkon", space_type="balcony", city="Jakarta"
        )
        self.patch2 = EcoPatch.objects.create(
            owner=self.user1, name="Teras Depan", space_type="terrace", city="Bandung"
        )

        # EcoPatch for user 2 with identical name
        self.patch_user2 = EcoPatch.objects.create(
            owner=self.user2, name="Kebun Balkon", space_type="balcony", city="Surabaya"
        )

        # Journals for user 1 on patch 1 (Tanaman Tomat)
        self.journal_p1_1 = GardenJournal.objects.create(
            user=self.user1,
            ecopatch=self.patch1,
            ecopatch_name=self.patch1.name,
            plant_name="Tomat Ceri",
            title="Tomat Semai",
            date=date.today(),
            notes="Mulai tumbuh",
            plant_condition="healthy",
        )
        self.journal_p1_2 = GardenJournal.objects.create(
            user=self.user1,
            ecopatch=self.patch1,
            ecopatch_name=self.patch1.name,
            plant_name="Tomat Ceri",
            title="Tomat Berdaun 4",
            date=date.today(),
            notes="Daun bertambah",
            plant_condition="healthy",
        )

        # Journal for user 1 on patch 2 (Tanaman Cabai)
        self.journal_p2 = GardenJournal.objects.create(
            user=self.user1,
            ecopatch=self.patch2,
            ecopatch_name=self.patch2.name,
            plant_name="Cabai Rawit",
            title="Cabai Mulai Berbunga",
            date=date.today(),
            notes="Bunga putih muncul",
            plant_condition="flowering",
        )

        # Journal for user 2 on user 2's patch (Tanaman Tomat Ceri milik user 2)
        self.journal_user2 = GardenJournal.objects.create(
            user=self.user2,
            ecopatch=self.patch_user2,
            ecopatch_name=self.patch_user2.name,
            plant_name="Tomat Ceri",
            title="Tomat User 2",
            date=date.today(),
            notes="Catatan milik user lain",
            plant_condition="healthy",
        )

    def test_delete_ecopatch_deletes_associated_journals(self):
        """Hapus EcoPatch => jurnal patch itu hilang."""
        self.patch1.delete()
        self.assertFalse(GardenJournal.objects.filter(pk=self.journal_p1_1.pk).exists())
        self.assertFalse(GardenJournal.objects.filter(pk=self.journal_p1_2.pk).exists())

    def test_other_patches_journals_for_same_user_remain(self):
        """Jurnal patch lain milik user yang sama tetap ada."""
        self.patch1.delete()
        self.assertTrue(GardenJournal.objects.filter(pk=self.journal_p2.pk).exists())
        self.journal_p2.refresh_from_db()
        self.assertEqual(self.journal_p2.plant_name, "Cabai Rawit")

    def test_other_users_journals_remain(self):
        """Jurnal milik user lain tetap ada."""
        self.patch1.delete()
        self.assertTrue(GardenJournal.objects.filter(pk=self.journal_user2.pk).exists())
        self.journal_user2.refresh_from_db()
        self.assertEqual(self.journal_user2.user, self.user2)

    def test_deleted_book_does_not_appear_in_journal_list(self):
        """Buku yang semua catatannya hilang tidak muncul lagi di journal_list."""
        self.client.login(username="haikal", password="password123")
        # Sebelum hapus patch1, Tomat Ceri ada di rak buku
        res_before = self.client.get(reverse("garden_journal:list"))
        self.assertEqual(res_before.status_code, 200)
        self.assertContains(res_before, "Tomat Ceri")
        self.assertContains(res_before, "Cabai Rawit")

        # Hapus patch1
        self.patch1.delete()

        # Setelah hapus patch1, Tomat Ceri (semua catatannya terhapus) hilang dari rak buku
        res_after = self.client.get(reverse("garden_journal:list"))
        self.assertEqual(res_after.status_code, 200)
        self.assertNotContains(res_after, "Tomat Ceri")
        # Cabai Rawit (dari patch2) masih tetap ada
        self.assertContains(res_after, "Cabai Rawit")

    def test_photo_deleted_from_storage_on_journal_delete(self):
        """Hapus file foto saat jurnal terhapus, lewat post_delete signal."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        import os

        dummy_img = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00"
            b"\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
            b"\x44\x01\x00\x3b"
        )
        photo = SimpleUploadedFile("test_cascade_del.gif", dummy_img, content_type="image/gif")
        self.journal_p1_1.image = photo
        self.journal_p1_1.save()

        file_path = self.journal_p1_1.image.path
        self.assertTrue(os.path.exists(file_path))

        # Hapus patch1 -> cascade delete journal_p1_1 -> post_delete signal fires
        self.patch1.delete()

        self.assertFalse(os.path.exists(file_path))
