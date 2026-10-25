import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import SeedExchange


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

    def test_guest_can_view_list(self):
        response = self.client.get(reverse('seed_exchange:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bibit Cabai Rawit')

    def test_guest_can_view_detail(self):
        response = self.client.get(reverse('seed_exchange:detail', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 200)

    def test_guest_cannot_access_create(self):
        response = self.client.get(reverse('seed_exchange:create'))
        self.assertNotEqual(response.status_code, 200)

    def test_create_sets_owner(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.post(reverse('seed_exchange:create'), {
            'title': 'Stek Sirih Gading',
            'item_type': 'cutting',
            'plant_name': 'Sirih Gading',
            'city': 'Jakarta',
            'contact': '0812-1111-2222',
            'transaction_type': 'swap',
            'status': 'available',
            'description': 'Mau tukar dengan stek tanaman indoor lain.',
        })
        listing = SeedExchange.objects.get(title='Stek Sirih Gading')
        self.assertEqual(listing.user, self.owner)
        self.assertRedirects(response, reverse('seed_exchange:detail', args=[listing.pk]))

    def test_create_requires_contact(self):
        self.client.login(username='rheina', password='test123')
        response = self.client.post(reverse('seed_exchange:create'), {
            'title': 'Tanpa kontak',
            'item_type': 'seed',
            'plant_name': '',
            'city': 'Depok',
            'contact': '',
            'transaction_type': 'giveaway',
            'status': 'available',
            'description': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SeedExchange.objects.filter(title='Tanpa kontak').exists())

    def test_create_form_uses_custom_dropdowns(self):
        self.client.login(username='rheina', password='test123')
        content = self.client.get(reverse('seed_exchange:create')).content.decode()
        self.assertIn('data-seed-select', content)
        self.assertNotIn('---------', content)
        self.assertIn('wajib diisi', content)

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
        self.assertRedirects(response, reverse('seed_exchange:list'))
        self.assertFalse(SeedExchange.objects.filter(pk=self.listing.pk).exists())

    def test_filter_by_city_and_status(self):
        make_listing(self.owner, title='Bibit Tomat Ceri', city='Bandung', status='available')
        url = reverse('seed_exchange:list') + '?city=Bandung&status=available'
        response = self.client.get(url)
        self.assertContains(response, 'Bibit Tomat Ceri')
        self.assertNotContains(response, 'Bibit Cabai Rawit')

    def test_custom_dropdowns_render_with_labels(self):
        response = self.client.get(reverse('seed_exchange:list'))
        self.assertContains(response, 'seed-menu')
        self.assertContains(response, 'Semua kota')
        # City filter keeps other params in URL.
        response = self.client.get(reverse('seed_exchange:list') + '?transaction_type=swap')
        self.assertContains(response, 'transaction_type=swap')

    def test_htmx_returns_partial(self):
        response = self.client.get(
            reverse('seed_exchange:list'),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('seed-card', response.content.decode())


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

    def test_reserve_via_htmx_returns_card(self):
        self.client.login(username='teman', password='test123')
        response = self.client.post(
            reverse('seed_exchange:reserve', args=[self.listing.pk]),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(f'seed-card-{self.listing.pk}', content)
        self.assertIn('Menunggu konfirmasi', content)

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

    def test_guest_sees_same_sections_with_login_gate(self):
        response = self.client.get(reverse('seed_exchange:list'))
        self.assertContains(response, 'Listing Saya')
        self.assertContains(response, 'Booking Saya')
        self.assertContains(response, 'Jelajahi')
        # Guest can open a restricted section, but only sees a login prompt.
        guest_mine = self.client.get(reverse('seed_exchange:list') + '?tab=mine', HTTP_HX_REQUEST='true')
        self.assertContains(guest_mine, 'Masuk untuk melihat listingmu.')
        self.assertNotContains(guest_mine, 'seed-card-add')

    def test_booked_listing_not_in_browse(self):
        self.mine.status = SeedExchange.Status.REQUESTED
        self.mine.reserved_by = self.other
        self.mine.save()
        self.client.login(username='teman', password='test123')
        response = self.client.get(reverse('seed_exchange:list') + '?tab=browse', HTTP_HX_REQUEST='true')
        self.assertNotContains(response, 'Bibit Cabai Rawit')
        bookings = self.client.get(reverse('seed_exchange:list') + '?tab=bookings', HTTP_HX_REQUEST='true')
        self.assertContains(bookings, 'Bibit Cabai Rawit')
