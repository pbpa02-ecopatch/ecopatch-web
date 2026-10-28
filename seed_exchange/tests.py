import re
import tempfile
from io import BytesIO
from unittest import mock
from urllib.parse import quote

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image as PILImage

from main.models import Profile

from .models import SeedExchange


def make_image_upload(name='bibit.png'):
    """Small in-memory PNG for upload tests."""
    buffer = BytesIO()
    PILImage.new('RGB', (24, 24), '#4a7c59').save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def make_user(username='rheina', password='test123'):
    return User.objects.create_user(username=username, password=password)


def make_listing(owner, **kwargs):
    defaults = {
        'title': 'Bibit Cabai Rawit',
        'item_type': SeedExchange.ItemType.SEEDLING,
        'plant_name': 'Cabai Rawit',
        'city': 'Depok',
        'contact': '0812-0000-0000',
        'transaction_type': SeedExchange.TransactionType.GIVEAWAY,
        'status': SeedExchange.Status.AVAILABLE,
        'description': 'Punya bibit cabai berlebih dari semai kemarin.',
    }
    defaults.update(kwargs)
    return SeedExchange.objects.create(user=owner, **defaults)


def fill_profile(user, **fields):
    """A profile with a city and a WhatsApp number: what a listing now takes its location and contact from."""
    values = {'city': 'Depok', 'whatsapp': '6281234567890'}
    values.update(fields)
    profile, _ = Profile.objects.update_or_create(user=user, defaults=values)
    return profile


class SeedExchangeModelTests(TestCase):
    def test_str_returns_title(self):
        owner = make_user()
        listing = make_listing(owner, title='Stek Monstera')
        self.assertEqual(str(listing), 'Stek Monstera')

    def test_default_status_available(self):
        owner = make_user()
        listing = SeedExchange.objects.create(
            user=owner, title='Biji Kemangi', item_type='seed',
            city='Tangerang', transaction_type='giveaway',
        )
        self.assertEqual(listing.status, 'available')


class SeedExchangeViewTests(TestCase):
    def setUp(self):
        self.owner = make_user('rheina')
        self.other = make_user('teman', 'test123')
        self.listing = make_listing(self.owner)
        fill_profile(self.owner)
        fill_profile(self.other)

    def test_the_form_shows_the_profile_city_and_contact_and_asks_for_neither(self):
        fill_profile(self.other, city='Bandung', whatsapp='6281234567890', instagram='kebunku')
        self.client.login(username='teman', password='test123')
        response = self.client.get(reverse('seed_exchange:create'))
        self.assertContains(response, 'WhatsApp +62 812-3456-7890 / Instagram @kebunku')
        self.assertContains(response, 'Bandung')
        self.assertNotContains(response, 'name="city"')
        self.assertNotContains(response, 'name="contact"')
        self.assertNotIn('city', response.context['form'].fields)
        self.assertNotIn('contact', response.context['form'].fields)

    def test_a_profile_without_contact_points_to_the_profile_page(self):
        fill_profile(self.other, whatsapp='', instagram='')
        self.client.login(username='teman', password='test123')
        response = self.client.get(reverse('seed_exchange:create'))
        self.assertFalse(response.context['location_ready'])
        self.assertContains(response, 'Lengkapi kota &amp; kontak di profil dulu')

    def test_a_listing_takes_its_city_and_contact_from_the_profile_not_from_the_post(self):
        fill_profile(self.other, city='Bandung', whatsapp='6281234567890', instagram='')
        self.client.login(username='teman', password='test123')
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            self.client.post(reverse('seed_exchange:create'), {
                'title': 'Tanpa isian lokasi', 'item_type': 'seed', 'plant_name': '', 'transaction_type': 'giveaway',
                'description': '', 'image': make_image_upload(),
                'city': 'Medan', 'contact': 'nomor-palsu-0000',  # a hand-made post cannot choose its own
            })
        listing = SeedExchange.objects.get(title='Tanpa isian lokasi')
        self.assertEqual(listing.city, 'Bandung')
        self.assertEqual(listing.contact, 'WhatsApp +62 812-3456-7890')

    def test_editing_a_listing_picks_up_the_current_profile(self):
        fill_profile(self.owner, city='Malang', whatsapp='6289999999999')
        self.client.login(username='rheina', password='test123')
        self.assertContains(self.client.get(reverse('seed_exchange:update', args=[self.listing.pk])), '+62 899-9999-9999')
        self._edit_post()
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.city, 'Malang')
        self.assertEqual(self.listing.contact, 'WhatsApp +62 899-9999-9999')

    def test_changing_the_profile_updates_the_members_listings(self):
        fill_profile(self.owner, city='Surabaya', whatsapp='6285555555555', instagram='baru')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.city, 'Surabaya')
        self.assertEqual(self.listing.contact, 'WhatsApp +62 855-5555-5555 / Instagram @baru')

    def test_emptying_the_profile_does_not_blank_the_listings(self):
        fill_profile(self.owner, city='', whatsapp='', instagram='')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.city, 'Depok')
        self.assertEqual(self.listing.contact, 'WhatsApp +62 812-3456-7890')

    def test_the_contact_a_requester_sees_is_the_profile_one(self):
        # a queryset update sends no signal, so the listing's own copy is left stale on purpose
        SeedExchange.objects.filter(pk=self.listing.pk).update(
            status=SeedExchange.Status.RESERVED, reserved_by=self.other, contact='0812-0000-0000')
        Profile.objects.filter(user=self.owner).update(whatsapp='6285555555555')
        self.client.login(username='teman', password='test123')
        content = self.client.get(reverse('seed_exchange:detail', args=[self.listing.pk])).content.decode()
        self.assertIn('WhatsApp +62 855-5555-5555', content)
        self.assertNotIn('0812-0000-0000', content)

    def test_guest_list_redirects_to_login(self):
        url = reverse('seed_exchange:list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/login/?next={quote(url)}')

    def test_guest_htmx_list_redirects_to_login(self):
        url = reverse('seed_exchange:list')
        response = self.client.get(url, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/login/?next={quote(url)}')

    def test_guest_detail_redirects_to_login(self):
        url = reverse('seed_exchange:detail', args=[self.listing.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/login/?next={quote(url)}')

    def test_guest_cannot_access_create(self):
        response = self.client.get(reverse('seed_exchange:create'))
        self.assertNotEqual(response.status_code, 200)

    def test_create_sets_owner(self):
        self.client.login(username='rheina', password='test123')
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(reverse('seed_exchange:create'), {
                'title': 'Stek Sirih Gading',
                'item_type': 'cutting',
                'plant_name': 'Sirih Gading',
                'city': 'Jakarta',
                'contact': '0812-1111-2222',
                'transaction_type': 'swap',
                'status': 'available',
                'description': 'Mau tukar dengan stek tanaman indoor lain.',
                'image': make_image_upload(),
            })
            listing = SeedExchange.objects.get(title='Stek Sirih Gading')
            self.assertEqual(listing.user, self.owner)
            self.assertRedirects(response, reverse('seed_exchange:detail', args=[listing.pk]))

    def test_create_requires_image(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.post(reverse('seed_exchange:create'), {
            'title': 'Tanpa foto',
            'item_type': 'seed',
            'plant_name': '',
            'city': 'Depok',
            'contact': '0812-0000-0000',
            'transaction_type': 'giveaway',
            'status': 'available',
            'description': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Foto listing wajib diunggah.')
        self.assertFalse(SeedExchange.objects.filter(title='Tanpa foto').exists())

    def _create_post(self, title):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            return self.client.post(reverse('seed_exchange:create'), {
                'title': title, 'item_type': 'seed', 'plant_name': '', 'transaction_type': 'giveaway',
                'description': '', 'image': make_image_upload(),
                'city': 'Depok', 'contact': '0812-0000-0000',  # ignored: both come from the profile
            })

    def test_create_needs_a_contact_on_the_profile(self):
        fill_profile(self.owner, whatsapp='', instagram='')
        self.client.login(username='rheina', password='test123')
        response = self._create_post('Tanpa kontak')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lengkapi kota dan kontak di profil dulu')
        self.assertNotContains(response, 'This field is required')
        self.assertFalse(SeedExchange.objects.filter(title='Tanpa kontak').exists())

    def test_create_needs_a_city_on_the_profile(self):
        fill_profile(self.owner, city='')
        self.client.login(username='rheina', password='test123')
        response = self._create_post('Tanpa kota')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lengkapi kota dan kontak di profil dulu')
        self.assertFalse(SeedExchange.objects.filter(title='Tanpa kota').exists())

    def test_create_form_uses_custom_dropdowns(self):
        self.client.login(username='rheina', password='test123')
        content = self.client.get(reverse('seed_exchange:create')).content.decode()
        self.assertIn('data-seed-select', content)
        self.assertNotIn('---------', content)
        self.assertIn('wajib diisi', content)
        self.assertIn('enctype="multipart/form-data"', content)
        self.assertIn('seed-upload-zone', content)

    def test_create_accepts_image_upload(self):
        self.client.login(username='rheina', password='test123')
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(reverse('seed_exchange:create'), {
                'title': 'Bibit dengan foto',
                'item_type': 'seedling',
                'plant_name': 'Tomat',
                'city': 'Depok',
                'contact': '0812-3333-4444',
                'transaction_type': 'giveaway',
                'status': 'available',
                'description': 'Bibit tomat siap tanam.',
                'image': make_image_upload(),
            })
            listing = SeedExchange.objects.get(title='Bibit dengan foto')
            self.assertTrue(listing.image.name.startswith('seed_exchange/'))
            self.assertRedirects(response, reverse('seed_exchange:detail', args=[listing.pk]))

    def test_update_keeps_existing_image(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            self.listing.image = make_image_upload()
            self.listing.save()
            original_name = self.listing.image.name
            self.client.login(username='rheina', password='test123')
            response = self.client.post(reverse('seed_exchange:update', args=[self.listing.pk]), {
                'title': 'Judul baru',
                'item_type': self.listing.item_type,
                'plant_name': self.listing.plant_name,
                'city': self.listing.city,
                'contact': self.listing.contact,
                'transaction_type': self.listing.transaction_type,
                'status': self.listing.status,
                'description': 'Deskripsi baru.',
            })
            self.assertRedirects(response, reverse('seed_exchange:detail', args=[self.listing.pk]))
            self.listing.refresh_from_db()
            self.assertEqual(self.listing.title, 'Judul baru')
            self.assertEqual(self.listing.image.name, original_name)

    def test_update_replaces_image(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            self.listing.image = make_image_upload('lama.png')
            self.listing.save()
            self.client.login(username='rheina', password='test123')
            response = self.client.post(reverse('seed_exchange:update', args=[self.listing.pk]), {
                'title': self.listing.title,
                'item_type': self.listing.item_type,
                'plant_name': self.listing.plant_name,
                'city': self.listing.city,
                'contact': self.listing.contact,
                'transaction_type': self.listing.transaction_type,
                'status': self.listing.status,
                'description': self.listing.description,
                'image': make_image_upload('baru.png'),
            })
            self.assertRedirects(response, reverse('seed_exchange:detail', args=[self.listing.pk]))
            self.listing.refresh_from_db()
            self.assertTrue(self.listing.image.name.endswith('baru.png'))

    def _edit_post(self, **overrides):
        data = {
            'title': self.listing.title, 'item_type': self.listing.item_type,
            'plant_name': self.listing.plant_name, 'city': self.listing.city,
            'contact': self.listing.contact, 'transaction_type': self.listing.transaction_type,
            'status': 'available', 'description': self.listing.description,
            'image': make_image_upload(),
        }
        data.update(overrides)
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            return self.client.post(reverse('seed_exchange:update', args=[self.listing.pk]), data)

    def test_edit_form_offers_only_available_and_completed(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.get(reverse('seed_exchange:update', args=[self.listing.pk]))
        choices = [value for value, _ in response.context['form'].fields['status'].choices]
        self.assertEqual(choices, ['available', 'completed'])

    def test_edit_cannot_force_a_listing_into_a_booking_state(self):
        self.client.login(username='rheina', password='test123')
        for forced in ('requested', 'reserved'):
            response = self._edit_post(status=forced)
            self.assertEqual(response.status_code, 200)
            self.listing.refresh_from_db()
            self.assertEqual(self.listing.status, SeedExchange.Status.AVAILABLE)

    def test_owner_can_close_a_listing_nobody_booked(self):
        self.client.login(username='rheina', password='test123')
        self._edit_post(status='completed')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, SeedExchange.Status.COMPLETED)

    def test_edit_cannot_free_a_listing_someone_holds(self):
        self.listing.status = SeedExchange.Status.RESERVED
        self.listing.reserved_by = self.other
        self.listing.save()
        self.client.login(username='rheina', password='test123')
        response = self.client.get(reverse('seed_exchange:update', args=[self.listing.pk]))
        self.assertNotIn('status', response.context['form'].fields)
        self._edit_post(title='Judul diubah', status='available')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, 'Judul diubah')
        self.assertEqual(self.listing.status, SeedExchange.Status.RESERVED)
        self.assertEqual(self.listing.reserved_by, self.other)

    def test_non_owner_cannot_edit(self):
        self.client.login(username='teman', password='test123')
        url = reverse('seed_exchange:update', args=[self.listing.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        response = self.client.post(url, {
            'title': 'Diubah orang', 'item_type': 'seed', 'plant_name': '',
            'city': 'Depok', 'transaction_type': 'giveaway',
            'status': 'available', 'description': '',
        })
        self.assertEqual(response.status_code, 404)
        self.listing.refresh_from_db()
        self.assertNotEqual(self.listing.title, 'Diubah orang')

    def test_non_owner_cannot_delete(self):
        self.client.login(username='teman', password='test123')
        response = self.client.post(reverse('seed_exchange:delete', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(SeedExchange.objects.filter(pk=self.listing.pk).exists())

    def test_owner_can_delete(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.post(reverse('seed_exchange:delete', args=[self.listing.pk]))
        self.assertRedirects(response, f"{reverse('seed_exchange:list')}?tab=mine")
        self.assertFalse(SeedExchange.objects.filter(pk=self.listing.pk).exists())

    def test_filter_by_city_and_status(self):
        self.client.login(username='rheina', password='test123')
        make_listing(self.owner, title='Bibit Tomat Ceri', city='Bandung', status='available')
        make_listing(self.owner, title='Bibit Tomat Habis', city='Bandung', status='completed')
        url = reverse('seed_exchange:list') + '?tab=mine&city=Bandung&status=available'
        response = self.client.get(url)
        self.assertContains(response, 'Bibit Tomat Ceri')
        self.assertNotContains(response, 'Bibit Tomat Habis')

    def test_status_filter_is_ignored_on_browse(self):
        self.client.login(username='teman', password='test123')
        # Browse only ever contains available listings, so a status from the URL
        # must not turn the page empty (or pretend the dropdown works there).
        url = reverse('seed_exchange:list') + '?tab=browse&status=requested'
        response = self.client.get(url)
        self.assertEqual(response.context['active']['status'], '')
        self.assertContains(response, 'Bibit Cabai Rawit')
        self.assertNotIn('status', [dd['name'] for dd in response.context['dropdowns']])
        # Listing Saya keeps the status filter.
        mine = self.client.get(reverse('seed_exchange:list') + '?tab=mine')
        self.assertIn('status', [dd['name'] for dd in mine.context['dropdowns']])

    def test_custom_dropdowns_render_with_labels(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.get(reverse('seed_exchange:list'))
        self.assertContains(response, 'seed-menu')
        self.assertContains(response, 'Semua kota')
        # City filter keeps other params in URL.
        response = self.client.get(reverse('seed_exchange:list') + '?transaction_type=swap')
        self.assertContains(response, 'transaction_type=swap')

    def test_htmx_returns_partial(self):
        self.client.login(username='teman', password='test123')
        response = self.client.get(
            reverse('seed_exchange:list'),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('seed-card', response.content.decode())

    def test_create_ignores_posted_status(self):
        self.client.login(username='rheina', password='test123')
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            self.client.post(reverse('seed_exchange:create'), {
                'title': 'Status diselundupkan',
                'item_type': 'seed',
                'plant_name': '',
                'city': 'Depok',
                'contact': '0812-0000-0000',
                'transaction_type': 'giveaway',
                'status': 'completed',
                'description': '',
                'image': make_image_upload(),
            })
        listing = SeedExchange.objects.get(title='Status diselundupkan')
        self.assertEqual(listing.status, SeedExchange.Status.AVAILABLE)

    def test_create_form_hides_status_field(self):
        self.client.login(username='rheina', password='test123')
        content = self.client.get(reverse('seed_exchange:create')).content.decode()
        self.assertNotIn('id_status', content)

    def test_detail_back_link_returns_to_previous_tab(self):
        self.client.login(username='rheina', password='test123')
        url = reverse('seed_exchange:detail', args=[self.listing.pk]) + '?tab=mine'
        response = self.client.get(url)
        self.assertContains(response, 'href="/seed-exchange/?tab=mine"')

    def test_detail_back_link_uses_last_visited_tab(self):
        self.client.login(username='rheina', password='test123')
        self.client.get(reverse('seed_exchange:list') + '?tab=mine')
        response = self.client.get(reverse('seed_exchange:detail', args=[self.listing.pk]))
        self.assertContains(response, 'href="/seed-exchange/?tab=mine"')

    def test_card_links_keep_current_tab(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.get(reverse('seed_exchange:list') + '?tab=mine')
        self.assertContains(response, f'href="/seed-exchange/{self.listing.pk}/?tab=mine"')

    def test_after_creating_the_back_link_goes_to_my_listings(self):
        self.client.login(username='teman', password='test123')
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            self.client.post(reverse('seed_exchange:create'), {
                'title': 'Bibit baru', 'item_type': 'seed', 'plant_name': '', 'city': 'Depok',
                'contact': '0812-0000-0000', 'transaction_type': 'giveaway', 'description': '',
                'image': make_image_upload(),
            })
        listing = SeedExchange.objects.get(title='Bibit baru')
        response = self.client.get(reverse('seed_exchange:detail', args=[listing.pk]))
        self.assertContains(response, 'href="/seed-exchange/?tab=mine"')

    def test_after_editing_the_back_link_goes_to_my_listings(self):
        self.client.login(username='rheina', password='test123')
        self.client.get(reverse('seed_exchange:list'))  # last visited: Jelajahi
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(reverse('seed_exchange:update', args=[self.listing.pk]), {
                'title': 'Judul baru', 'item_type': 'seed', 'plant_name': '', 'city': 'Depok',
                'contact': '0812-0000-0000', 'transaction_type': 'giveaway', 'status': 'available',
                'description': '', 'image': make_image_upload(),
            })
        self.assertRedirects(response, reverse('seed_exchange:detail', args=[self.listing.pk]))
        self.assertEqual(self.client.session['seed_exchange_last_list'], '/seed-exchange/?tab=mine')

    def test_empty_browse_points_to_my_listings_when_the_user_has_some(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.get(reverse('seed_exchange:list'))
        self.assertEqual(len(response.context['listings']), 0)
        self.assertContains(response, 'seed-empty-hint')
        self.assertContains(response, 'Listing Saya')

    def test_empty_browse_has_no_hint_without_own_listings(self):
        self.client.login(username='teman', password='test123')
        self.client.post(reverse('seed_exchange:reserve', args=[self.listing.pk]))
        response = self.client.get(reverse('seed_exchange:list'))
        self.assertNotContains(response, 'seed-empty-hint')


class SeedExchangeFlowTests(TestCase):
    """Alur booking: minta -> nunggu konfirmasi -> diterima/ditolak -> selesai."""

    def setUp(self):
        self.owner = make_user('rheina')
        self.other = make_user('teman', 'test123')
        self.listing = make_listing(self.owner)

    def _request_booking(self):
        self.listing.status = 'requested'
        self.listing.reserved_by = self.other
        self.listing.save()

    def test_my_section_separates_own_listings(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.get(reverse('seed_exchange:list'))
        # Tab navigation present
        self.assertContains(response, 'Listing Saya')
        self.assertContains(response, 'Booking Saya')
        self.assertContains(response, 'Jelajahi')
        # Default tab is 'browse' (Jelajahi) - own listing should NOT appear there
        content = response.content.decode()
        self.assertEqual(content.count('Bibit Cabai Rawit'), 0)
        # Own listing appears in 'mine' tab via HTMX
        response_mine = self.client.get(reverse('seed_exchange:list') + '?tab=mine', HTTP_HX_REQUEST='true')
        self.assertContains(response_mine, 'Bibit Cabai Rawit')

    def test_other_can_reserve_available(self):
        self.client.login(username='teman', password='test123')
        response = self.client.post(reverse('seed_exchange:reserve', args=[self.listing.pk]))
        self.assertRedirects(response, reverse('seed_exchange:detail', args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'requested')
        self.assertEqual(self.listing.reserved_by, self.other)

    def test_owner_accepts_booking(self):
        self._request_booking()
        self.client.login(username='rheina', password='test123')
        response = self.client.post(reverse('seed_exchange:accept', args=[self.listing.pk]))
        self.assertRedirects(response, reverse('seed_exchange:detail', args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'reserved')

    def test_non_owner_cannot_accept(self):
        self._request_booking()
        self.client.login(username='teman', password='test123')
        response = self.client.post(reverse('seed_exchange:accept', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 404)

    def test_requester_sees_waiting_box_without_contact(self):
        self._request_booking()
        self.client.login(username='teman', password='test123')
        content = self.client.get(reverse('seed_exchange:detail', args=[self.listing.pk])).content.decode()
        self.assertIn('menunggu konfirmasi', content)
        self.assertNotIn('@rheina', content)
        self.assertNotIn('0812-0000-0000', content)
        self.assertIn('Batalkan booking saya', content)

    def test_accepted_requester_sees_contact_no_cancel(self):
        self._request_booking()
        self.listing.status = 'reserved'
        self.listing.save()
        self.client.login(username='teman', password='test123')
        content = self.client.get(reverse('seed_exchange:detail', args=[self.listing.pk])).content.decode()
        self.assertIn('Diterima!', content)
        self.assertIn('0812-0000-0000', content)
        self.assertNotIn('Batalkan booking saya', content)

    def test_owner_sees_requester_name(self):
        self._request_booking()
        self.client.login(username='rheina', password='test123')
        content = self.client.get(reverse('seed_exchange:detail', args=[self.listing.pk])).content.decode()
        self.assertIn('@teman', content)
        self.assertIn('Terima', content)

    def test_owner_still_sees_who_received_a_completed_listing(self):
        self._request_booking()
        self.listing.status = 'completed'
        self.listing.save()
        self.client.login(username='rheina', password='test123')
        content = self.client.get(reverse('seed_exchange:detail', args=[self.listing.pk])).content.decode()
        self.assertIn('Selesai dengan', content)
        self.assertIn('@teman', content)

    def test_reserver_can_cancel(self):
        self._request_booking()
        self.client.login(username='teman', password='test123')
        response = self.client.post(reverse('seed_exchange:cancel_reserve', args=[self.listing.pk]))
        self.assertRedirects(response, reverse('seed_exchange:detail', args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'available')
        self.assertIsNone(self.listing.reserved_by)

    def test_requester_cannot_cancel_after_accepted(self):
        self._request_booking()
        self.listing.status = 'reserved'
        self.listing.save()
        self.client.login(username='teman', password='test123')
        response = self.client.post(reverse('seed_exchange:cancel_reserve', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 404)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'reserved')

    def test_non_reserver_cannot_cancel(self):
        self._request_booking()
        make_user('asing', 'test123')
        self.client.login(username='asing', password='test123')
        response = self.client.post(reverse('seed_exchange:cancel_reserve', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 404)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'requested')

    def test_action_ignores_htmx_header_and_redirects(self):
        # The detail page posts these actions as plain forms, so an HX-Request
        # header must not turn the response into a card partial.
        self.client.login(username='teman', password='test123')
        response = self.client.post(
            reverse('seed_exchange:reserve', args=[self.listing.pk]),
            HTTP_HX_REQUEST='true',
        )
        self.assertRedirects(response, reverse('seed_exchange:detail', args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, SeedExchange.Status.REQUESTED)
        self.assertEqual(self.listing.reserved_by, self.other)

    def test_owner_cannot_reserve_own(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.post(reverse('seed_exchange:reserve', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 403)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'available')

    def test_reserve_unavailable_returns_400(self):
        self._request_booking()
        make_user('ketiga', 'test123')
        self.client.login(username='ketiga', password='test123')
        response = self.client.post(reverse('seed_exchange:reserve', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 400)

    def test_second_requester_does_not_take_over_the_first(self):
        self._request_booking()
        make_user('ketiga', 'test123')
        self.client.login(username='ketiga', password='test123')
        self.client.post(reverse('seed_exchange:reserve', args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'requested')
        self.assertEqual(self.listing.reserved_by, self.other)

    def test_reserve_does_not_trust_a_stale_read(self):
        # Simulates the race window: the view read the listing while it was still
        # available, but another requester claimed it before this POST writes.
        # The conditional UPDATE must refuse instead of overwriting the first
        # requester with whoever read last.
        self._request_booking()
        make_user('ketiga', 'test123')
        self.client.login(username='ketiga', password='test123')
        stale = SeedExchange.objects.get(pk=self.listing.pk)
        stale.status = SeedExchange.Status.AVAILABLE
        stale.reserved_by = None
        with mock.patch('seed_exchange.views.get_object_or_404', return_value=stale):
            response = self.client.post(
                reverse('seed_exchange:reserve', args=[self.listing.pk])
            )
        self.assertEqual(response.status_code, 400)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, SeedExchange.Status.REQUESTED)
        self.assertEqual(self.listing.reserved_by, self.other)

    def test_reserving_bumps_updated_at(self):
        before = self.listing.updated_at
        self.client.login(username='teman', password='test123')
        self.client.post(reverse('seed_exchange:reserve', args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertGreater(self.listing.updated_at, before)

    def test_guest_reserve_redirects_to_login(self):
        response = self.client.post(reverse('seed_exchange:reserve', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_full_flow_to_completed_and_reopen(self):
        self.client.login(username='teman', password='test123')
        self.client.post(reverse('seed_exchange:reserve', args=[self.listing.pk]))
        self.client.login(username='rheina', password='test123')
        self.client.post(reverse('seed_exchange:accept', args=[self.listing.pk]))
        response = self.client.post(reverse('seed_exchange:complete', args=[self.listing.pk]))
        self.assertRedirects(response, reverse('seed_exchange:detail', args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'completed')

        response = self.client.post(reverse('seed_exchange:reopen', args=[self.listing.pk]))
        self.assertRedirects(response, reverse('seed_exchange:detail', args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'available')
        self.assertIsNone(self.listing.reserved_by)

    def test_completed_booking_stays_in_my_bookings(self):
        self.client.login(username='teman', password='test123')
        self.client.post(reverse('seed_exchange:reserve', args=[self.listing.pk]))
        self.client.login(username='rheina', password='test123')
        self.client.post(reverse('seed_exchange:accept', args=[self.listing.pk]))
        self.client.post(reverse('seed_exchange:complete', args=[self.listing.pk]))

        # The requester keeps the finished exchange as history instead of the
        # booking vanishing from Booking Saya.
        self.client.login(username='teman', password='test123')
        response = self.client.get(reverse('seed_exchange:list') + '?tab=bookings')
        self.assertEqual([item.pk for item in response.context['my_bookings']], [self.listing.pk])
        self.assertContains(response, 'Bibit Cabai Rawit')
        self.assertContains(response, 'Completed')

        # Opening the finished booking still shows the owner's contact.
        detail = self.client.get(reverse('seed_exchange:detail', args=[self.listing.pk])).content.decode()
        self.assertIn('Selesai', detail)
        self.assertIn('0812-0000-0000', detail)

    def test_non_owner_cannot_complete(self):
        self._request_booking()
        self.listing.status = 'reserved'
        self.listing.save()
        self.client.login(username='teman', password='test123')
        response = self.client.post(reverse('seed_exchange:complete', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 404)

    def test_my_section_has_add_card_and_clean_cards(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.get(reverse('seed_exchange:list') + '?tab=mine')
        content = response.content.decode()
        # Dashed "New Listing" card at end of My Listings grid.
        self.assertIn('seed-card-add', content)
        self.assertContains(response, 'Buat Listing Baru')
        # Clean cards: no quick actions, manage via detail page.
        self.assertNotContains(response, 'Tandai selesai')
        self.assertNotContains(response, 'Buka kembali')
        self.assertNotContains(response, '>Reserve<')
        self.assertNotContains(response, '>Ubah<')


class SeedExchangeTabAndFilterTests(TestCase):
    """Section tabs + filters must not fight each other."""

    def setUp(self):
        self.owner = make_user('rheina')
        self.other = make_user('teman', 'test123')
        self.mine = make_listing(self.owner, title='Bibit Cabai Rawit', city='Depok')
        self.other_bandung = make_listing(self.other, title='Stek Monstera', city='Bandung')
        self.other_jakarta = make_listing(self.other, title='Biji Kemangi', city='Jakarta')

    def test_tab_links_contain_a_single_tab_param(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.get(reverse('seed_exchange:list') + '?tab=mine&city=Depok')
        content = response.content.decode()
        # Regression: `active` used to leak `tab` into every link, producing
        # ?tab=mine&...&tab=browse and Django read the LAST value (browse).
        urls = re.findall(r'\?tab=[^"\s]+', content)
        self.assertTrue(urls)
        for url in urls:
            self.assertEqual(url.count('tab='), 1, url)
        self.assertIn('?tab=mine&city=Depok', content)

    def test_tab_switch_keeps_filters(self):
        self.client.login(username='rheina', password='test123')
        for tab in ('bookings', 'browse', 'mine'):
            response = self.client.get(
                reverse('seed_exchange:list') + f'?tab={tab}&city=Bandung',
                HTTP_HX_REQUEST='true',
            )
            self.assertContains(response, 'seed-filter--active')
            self.assertContains(response, f'value="{tab}"')
            self.assertContains(response, f'id="panel-{tab}"')
            self.assertContains(response, f'aria-selected="true"', count=1)

    def test_filter_link_keeps_current_tab(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.get(reverse('seed_exchange:list') + '?tab=mine')
        self.assertContains(response, 'tab=mine&amp;item_type=seedling')

    def test_reset_link_drops_filters_and_filter_form_does_not_inherit_include(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.get(reverse('seed_exchange:list') + '?tab=mine&city=Bandung')
        content = response.content.decode()
        # Reset must point at a clean URL (keeping only the current tab).
        reset_urls = re.findall(r'class="seed-filter-reset" href="([^"]+)"', content)
        self.assertEqual(reset_urls, ['/seed-exchange/?tab=mine'])
        # Regression: hx-include on the form was inherited by filter/reset links,
        # appending the old values after the new URL (so both seemed dead).
        form_tag = re.search(r'<form id="seed-filter-form".*?>', content, re.S).group(0)
        self.assertNotIn('hx-include', form_tag)

    def test_two_filters_do_not_collapse(self):
        self.client.login(username='rheina', password='test123')
        url = reverse('seed_exchange:list') + '?tab=browse&city=Bandung&transaction_type=giveaway'
        response = self.client.get(url, HTTP_HX_REQUEST='true')
        content = response.content.decode()
        self.assertIn('city=Bandung&amp;transaction_type=giveaway', content)
        self.assertContains(response, 'Stek Monstera')
        self.assertNotContains(response, 'Biji Kemangi')

    def test_guest_cannot_view_sections_or_my_tab(self):
        # The whole page (including HTMX swaps) is behind login now.
        response = self.client.get(reverse('seed_exchange:list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
        guest_mine = self.client.get(reverse('seed_exchange:list') + '?tab=mine', HTTP_HX_REQUEST='true')
        self.assertEqual(guest_mine.status_code, 302)
        self.assertIn('/login/', guest_mine.url)

    def test_booked_listing_not_in_browse(self):
        self.mine.status = SeedExchange.Status.REQUESTED
        self.mine.reserved_by = self.other
        self.mine.save()
        self.client.login(username='teman', password='test123')
        response = self.client.get(reverse('seed_exchange:list') + '?tab=browse', HTTP_HX_REQUEST='true')
        self.assertNotContains(response, 'Bibit Cabai Rawit')
        bookings = self.client.get(reverse('seed_exchange:list') + '?tab=bookings', HTTP_HX_REQUEST='true')
        self.assertContains(bookings, 'Bibit Cabai Rawit')

    def test_filtered_empty_browse_does_not_claim_only_others_listings_exist(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.get(reverse('seed_exchange:list') + '?q=tidak-ada-yang-cocok')
        self.assertEqual(len(response.context['listings']), 0)
        self.assertContains(response, 'Belum ada listing yang cocok.')
        self.assertNotContains(response, 'seed-empty-hint')


class SeedExchangeEdgeCaseTests(TestCase):
    """Odd input, odd states and people who should not see or touch something."""

    def setUp(self):
        self.owner = make_user('rheina')
        self.other = make_user('teman', 'test123')
        self.stranger = make_user('asing', 'test123')
        self.listing = make_listing(self.owner)
        fill_profile(self.owner)

    def _book_and_accept(self):
        self.listing.status = SeedExchange.Status.RESERVED
        self.listing.reserved_by = self.other
        self.listing.save()

    def test_garbage_query_params_do_not_break_the_list(self):
        self.client.login(username='teman', password='test123')
        url = reverse('seed_exchange:list')
        query = '?tab=zzz&item_type=hack&status=x&city=Atlantis&transaction_type=%00&q=' + 'a' * 5000
        for extra in ('', '&page=abc', '&q=%27%3B+DROP+TABLE+seed_exchange%3B--'):
            self.assertEqual(self.client.get(url + query + extra).status_code, 200)
            self.assertEqual(self.client.get(url + query + extra, HTTP_HX_REQUEST='true').status_code, 200)

    def test_unknown_tab_falls_back_to_browse(self):
        self.client.login(username='teman', password='test123')
        response = self.client.get(reverse('seed_exchange:list') + '?tab=zzz')
        self.assertEqual(response.context['active_tab'], 'browse')

    def test_html_in_a_title_is_escaped_on_cards_and_detail(self):
        make_listing(self.owner, title='<script>alert(1)</script>')
        self.client.login(username='teman', password='test123')
        listing = SeedExchange.objects.get(title='<script>alert(1)</script>')
        for url in (reverse('seed_exchange:list'), reverse('seed_exchange:detail', args=[listing.pk])):
            self.assertNotContains(self.client.get(url), '<script>alert(1)</script>')

    def test_a_third_person_never_sees_the_contact_of_a_booked_listing(self):
        self._book_and_accept()
        self.client.login(username='asing', password='test123')
        content = self.client.get(reverse('seed_exchange:detail', args=[self.listing.pk])).content.decode()
        self.assertNotIn('812-3456-7890', content)

    def test_accept_refuses_a_request_without_a_requester(self):
        self.listing.status = SeedExchange.Status.REQUESTED
        self.listing.reserved_by = None
        self.listing.save()
        self.client.login(username='rheina', password='test123')
        response = self.client.post(reverse('seed_exchange:accept', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 400)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, SeedExchange.Status.REQUESTED)

    def test_detail_of_a_missing_listing_is_404(self):
        self.client.login(username='teman', password='test123')
        self.assertEqual(self.client.get(reverse('seed_exchange:detail', args=[99999])).status_code, 404)

    def test_actions_by_get_change_nothing(self):
        self.client.login(username='teman', password='test123')
        self.client.get(reverse('seed_exchange:reserve', args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, SeedExchange.Status.AVAILABLE)
        self.assertIsNone(self.listing.reserved_by)

    def test_deleting_a_booked_listing_leaves_the_requester_with_no_dangling_booking(self):
        self._book_and_accept()
        self.client.login(username='rheina', password='test123')
        self.client.post(reverse('seed_exchange:delete', args=[self.listing.pk]))
        self.client.login(username='teman', password='test123')
        response = self.client.get(reverse('seed_exchange:list') + '?tab=bookings')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['my_bookings']), 0)

    def test_rejecting_a_request_frees_the_listing_for_the_next_person(self):
        self.listing.status = SeedExchange.Status.REQUESTED
        self.listing.reserved_by = self.other
        self.listing.save()
        self.client.login(username='rheina', password='test123')
        self.client.post(reverse('seed_exchange:reopen', args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, SeedExchange.Status.AVAILABLE)
        self.assertIsNone(self.listing.reserved_by)
        self.client.login(username='asing', password='test123')
        self.client.post(reverse('seed_exchange:reserve', args=[self.listing.pk]))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.reserved_by, self.stranger)

    def test_an_upload_that_is_not_an_image_is_rejected(self):
        self.client.login(username='rheina', password='test123')
        fake = SimpleUploadedFile('bibit.png', b'bukan gambar sungguhan', content_type='image/png')
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(reverse('seed_exchange:create'), {
                'title': 'Foto palsu', 'item_type': 'seed', 'plant_name': '', 'city': 'Depok',
                'contact': '0812-0000-0000', 'transaction_type': 'giveaway', 'description': '',
                'image': fake,
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'File harus berupa gambar')
        self.assertFalse(SeedExchange.objects.filter(title='Foto palsu').exists())

    def test_an_image_over_5_mb_is_rejected(self):
        self.client.login(username='rheina', password='test123')
        buffer = BytesIO()
        PILImage.new('RGB', (4, 4), '#4a7c59').save(buffer, format='PNG')
        too_big = SimpleUploadedFile('besar.png', buffer.getvalue() + b'0' * (5 * 1024 * 1024), content_type='image/png')
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(reverse('seed_exchange:create'), {
                'title': 'Foto besar', 'item_type': 'seed', 'plant_name': '', 'city': 'Depok',
                'contact': '0812-0000-0000', 'transaction_type': 'giveaway', 'description': '',
                'image': too_big,
            })
        self.assertContains(response, 'Ukuran foto maksimal 5 MB.')
        self.assertFalse(SeedExchange.objects.filter(title='Foto besar').exists())

    def test_a_description_longer_than_the_limit_is_rejected(self):
        self.client.login(username='rheina', password='test123')
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(reverse('seed_exchange:create'), {
                'title': 'Deskripsi panjang', 'item_type': 'seed', 'plant_name': '',
                'transaction_type': 'giveaway', 'description': 'x' * 2001,
                'image': make_image_upload(),
            })
        self.assertContains(response, 'Deskripsi maksimal 2000 karakter.')
        self.assertFalse(SeedExchange.objects.filter(title='Deskripsi panjang').exists())

    def test_search_text_is_cleaned_and_capped(self):
        self.client.login(username='teman', password='test123')
        response = self.client.get(
            reverse('seed_exchange:list'), {'q': '\x00\x01  ' + 'a' * 500}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active']['q'], 'a' * 100)

    def test_a_user_without_a_profile_row_can_open_every_page(self):
        Profile.objects.filter(user=self.other).delete()
        self.client.login(username='teman', password='test123')
        for url in (
            reverse('seed_exchange:list'), reverse('seed_exchange:create'),
            reverse('seed_exchange:detail', args=[self.listing.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)
