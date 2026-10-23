import io
import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Profile

TEMP_MEDIA = tempfile.mkdtemp()


def make_image(name='foto.png', size=(20, 20)):
    buf = io.BytesIO()
    Image.new('RGB', size, 'green').save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ProfileViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = get_user_model().objects.create_user('tanam', 'lama@example.com', 'pass12345')
        self.url = reverse('main:profile')
        self.client.force_login(self.user)

    def post_profile(self, **overrides):
        data = {
            'action': 'profile',
            'first_name': 'Siti',
            'last_name': 'Aminah',
            'email': 'lama@example.com',
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('main:login')}?next={self.url}")

    def test_get_creates_profile_and_prefills(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Profile.objects.filter(user=self.user).exists())
        self.assertContains(response, 'name="email" value="lama@example.com"')
        self.assertContains(response, 'lama@example.com')

    def test_card_shows_stats_and_logout_button(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'class="profile-stats"')
        self.assertContains(response, 'class="profile-logout"')
        self.assertEqual(response.context['stats'], {'patches': 0, 'journals': 0, 'listings': 0})

    def test_member_since_uses_indonesian_month(self):
        self.user.date_joined = self.user.date_joined.replace(year=2026, month=10, day=5)
        self.user.save()
        response = self.client.get(self.url)
        self.assertContains(response, 'Anggota sejak Oktober 2026')

    def test_logged_in_pages_use_the_sidebar_layout(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'has-sidebar')
        self.assertContains(response, 'site-navbar--side')
        self.assertContains(response, 'class="sidebar-user')

    def test_sidebar_user_row_has_tooltip(self):
        self.assertContains(self.client.get(self.url), 'title="tanam - lama@example.com"')

    def test_sidebar_has_collapse_toggle(self):
        self.assertContains(self.client.get(self.url), 'id="sidebar-toggle"')

    def test_guest_pages_keep_the_top_navbar(self):
        self.client.logout()
        response = self.client.get(reverse('main:home'))
        self.assertNotContains(response, 'has-sidebar')
        self.assertNotContains(response, 'site-navbar site-navbar--side')  # kelas pada <nav>, bukan selector JS
        self.assertNotContains(response, 'id="sidebar-toggle"')

    def test_each_section_has_its_own_form(self):
        response = self.client.get(self.url)
        for action in ('profile', 'bio'):
            self.assertContains(response, f'name="action" value="{action}"')

    def test_profile_updates_names_and_email(self):
        response = self.post_profile(email='baru@example.com')
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), 'Siti Aminah')
        self.assertEqual(self.user.email, 'baru@example.com')

    def test_bio_updates_only_bio(self):
        response = self.client.post(self.url, {'action': 'bio', 'bio': 'Suka cabai di balkon.'})
        self.assertRedirects(response, self.url)
        self.assertEqual(Profile.objects.get(user=self.user).bio, 'Suka cabai di balkon.')
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'tanam')

    def test_city_saved_with_bio_and_shown_on_card(self):
        response = self.client.post(self.url, {'action': 'bio', 'city': 'Bandung', 'bio': ''})
        self.assertRedirects(response, self.url)
        self.assertEqual(Profile.objects.get(user=self.user).city, 'Bandung')
        self.assertContains(self.client.get(self.url), 'class="profile-city">Bandung')

    def test_city_outside_supported_list_rejected(self):
        response = self.client.post(self.url, {'action': 'bio', 'city': 'Atlantis', 'bio': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Profile.objects.get(user=self.user).city, '')

    def test_city_is_optional(self):
        response = self.client.post(self.url, {'action': 'bio', 'city': '', 'bio': 'Halo'})
        self.assertRedirects(response, self.url)

    def test_remove_button_only_when_avatar_exists(self):
        self.assertContains(self.client.get(self.url), 'id="avatar-remove-btn" aria-label="Hapus foto profil" hidden')
        self.post_profile(avatar=make_image())
        self.assertNotContains(self.client.get(self.url), 'aria-label="Hapus foto profil" hidden')

    def test_saving_info_keeps_bio_and_avatar(self):
        self.client.post(self.url, {'action': 'bio', 'bio': 'Tetap ada.'})
        self.post_profile(avatar=make_image())
        self.post_profile()
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.bio, 'Tetap ada.')
        self.assertTrue(profile.avatar)

    def test_upload_avatar(self):
        response = self.post_profile(avatar=make_image())
        self.assertRedirects(response, self.url)
        self.assertTrue(Profile.objects.get(user=self.user).avatar.name.startswith('avatars/'))

    def test_non_image_avatar_rejected(self):
        fake = SimpleUploadedFile('x.png', b'bukan gambar', content_type='image/png')
        response = self.post_profile(avatar=fake)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Profile.objects.get(user=self.user).avatar)

    def test_oversized_avatar_rejected(self):
        buf = io.BytesIO()
        Image.new('RGB', (20, 20), 'green').save(buf, format='PNG')
        # Data tambahan setelah chunk IEND diabaikan Pillow, jadi tetap gambar valid tapi > 2 MB
        big = SimpleUploadedFile('besar.png', buf.getvalue() + b'0' * (3 * 1024 * 1024), content_type='image/png')
        response = self.post_profile(avatar=big)
        self.assertContains(response, 'maksimal 2 MB')

    def test_remove_avatar(self):
        self.post_profile(avatar=make_image())
        response = self.post_profile(remove_avatar='on')
        self.assertRedirects(response, self.url)
        self.assertFalse(Profile.objects.get(user=self.user).avatar)

    def test_username_cannot_be_changed(self):
        response = self.post_profile(username='petani')
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'tanam')

    def test_username_not_in_edit_form(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, 'name="username"')
        self.assertNotContains(response, 'username-readonly')
        self.assertContains(response, '@tanam')  # tetap terlihat di card profil

    def test_post_without_action_changes_nothing(self):
        response = self.client.post(self.url, {'username': 'diam-diam', 'bio': 'x'})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'tanam')
        self.assertEqual(Profile.objects.get(user=self.user).bio, '')


class ChangePasswordTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('tanam', 'a@example.com', 'lama-12345')
        self.client.force_login(self.user)
        self.url = reverse('main:profile')

    def post_password(self, **overrides):
        data = {
            'action': 'password',
            'old_password': 'lama-12345',
            'new_password1': 'baru-Sangat-Aman-987',
            'new_password2': 'baru-Sangat-Aman-987',
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_change_password_keeps_user_logged_in(self):
        response = self.post_password()
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('baru-Sangat-Aman-987'))
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_wrong_current_password_rejected(self):
        response = self.post_password(old_password='salah')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('lama-12345'))

    def test_mismatched_confirmation_rejected(self):
        response = self.post_password(new_password2='beda-12345-xyz')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('lama-12345'))

    def test_weak_password_rejected(self):
        response = self.post_password(new_password1='12345678', new_password2='12345678')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('lama-12345'))

    def test_password_form_is_inside_modal(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'id="password-modal"')
        self.assertContains(response, 'data-bs-target="#password-modal"')

    def test_modal_reopens_on_error(self):
        errored = self.post_password(old_password='salah')
        self.assertContains(errored, "getOrCreateInstance(document.getElementById('password-modal')).show()")
        clean = self.client.get(self.url)
        self.assertNotContains(clean, "getOrCreateInstance(document.getElementById('password-modal')).show()")

    def test_password_post_does_not_touch_profile(self):
        self.post_password()
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'tanam')

    def test_settings_page_is_gone(self):
        self.assertEqual(self.client.get('/settings/').status_code, 404)

    def test_navbar_has_no_settings_item(self):
        self.assertNotContains(self.client.get(self.url), 'Pengaturan')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class DeleteAccountTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('tanam', 'a@example.com', 'lama-12345')
        self.client.force_login(self.user)
        self.url = reverse('main:profile')

    def test_delete_with_correct_password(self):
        response = self.client.post(self.url, {'action': 'delete', 'password': 'lama-12345'})
        self.assertRedirects(response, reverse('main:home'))
        self.assertFalse(get_user_model().objects.filter(username='tanam').exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_wrong_password_keeps_account(self):
        response = self.client.post(self.url, {'action': 'delete', 'password': 'salah'})
        self.assertContains(response, 'Password salah.')
        self.assertTrue(get_user_model().objects.filter(username='tanam').exists())
        self.assertContains(response, "getElementById('delete-modal')")

    def test_missing_password_keeps_account(self):
        self.client.post(self.url, {'action': 'delete'})
        self.assertTrue(get_user_model().objects.filter(username='tanam').exists())

    def test_avatar_file_removed(self):
        profile = Profile.objects.create(user=self.user, avatar=make_image())
        path = profile.avatar.path
        self.assertTrue(os.path.exists(path))
        self.client.post(self.url, {'action': 'delete', 'password': 'lama-12345'})
        self.assertFalse(os.path.exists(path))
