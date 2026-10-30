import io
import tempfile
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from my_ecopatch.models import EcoPatch, PatchPlant
from .forms import GardenJournalForm
from .models import GardenJournal
from .views import _filter_date, _get_user_patch_plants


class JournalWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('journal_audit')
        cls.other = get_user_model().objects.create_user('journal_other')
        cls.patch = EcoPatch.objects.create(owner=cls.user, name='Balkon', space_type='balcony', city='Depok')
        cls.foreign = EcoPatch.objects.create(owner=cls.other, name='Kebun lain', space_type='indoor', city='Bogor')
        cls.today = timezone.localdate()
        cls.old = GardenJournal.objects.create(user=cls.user, ecopatch=cls.patch, plant_name='Bayam',
            title='Awal', notes='Mulai', date=cls.today-timedelta(days=2), plant_height=5, plant_condition='healthy')
        cls.new = GardenJournal.objects.create(user=cls.user, ecopatch=cls.patch, plant_name='Bayam',
            title='Tumbuh', notes='Makin tinggi', date=cls.today, plant_height=12, image='journal_photos/audit.png',
            plant_condition='flowering', cover_pattern='solid', cover_color='#167a38')
        cls.basil = GardenJournal.objects.create(user=cls.user, ecopatch=cls.patch, plant_name='Basil',
            title='Basil sehat', notes='Segar', date=cls.today-timedelta(days=1), plant_condition='healthy')
        GardenJournal.objects.create(user=cls.other, ecopatch=cls.foreign, plant_name='Rahasia',
            title='Pribadi', notes='Bukan milik audit', date=cls.today)

    def setUp(self):
        self.client.force_login(self.user)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        setting = override_settings(MEDIA_ROOT=temp.name)
        setting.enable()
        self.addCleanup(setting.disable)

    def payload(self, **changes):
        data = {'plant_name':'Bayam', 'ecopatch':self.patch.pk, 'date':self.today.isoformat(),
                'title':'Baru', 'notes':'Sehat', 'plant_condition':'healthy', 'cover_pattern':'flowers'}
        data.update(changes)
        return data

    def test_date_condition_patch_and_photo_filters_return_only_matching_entries(self):
        checks = [
            ({'ecopatch':str(self.patch.pk)}, 3), ({'ecopatch':'Balkon'}, 3),
            ({'condition':'flowering'}, 1), ({'date_from':self.today.isoformat()}, 1),
            ({'date_to':(self.today-timedelta(days=2)).isoformat()}, 1),
            ({'has_photo':'yes'}, 1), ({'has_photo':'no'}, 2),
            ({'ecopatch':'9'*5000}, 0), ({'ecopatch':'²'}, 0),
        ]
        for params, count in checks:
            with self.subTest(params=str(params)[:80]):
                response = self.client.get(reverse('garden_journal:filter_ajax'), params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(sum(book['count'] for book in response.context['books']), count)
                self.assertNotContains(response, 'Rahasia')

    def test_each_sort_orders_books_by_the_requested_rule(self):
        for sort, expected in [('a_z',['Basil','Bayam']), ('z_a',['Bayam','Basil']),
                               ('oldest',['Basil','Bayam']), ('newest',['Bayam','Basil'])]:
            with self.subTest(sort=sort):
                response = self.client.get(reverse('garden_journal:list'), {'sort':sort})
                self.assertEqual([b['plant_name'] for b in response.context['books']], expected)

    def test_history_filters_and_growth_are_consistent(self):
        url = reverse('garden_journal:plant_history', args=['Bayam'])
        response = self.client.get(url)
        self.assertEqual(response.context['growth'], 7)
        self.assertEqual(len(response.context['chart_data']), 2)
        self.assertEqual(response.context['cover_color'], '#167a38')
        self.assertEqual(self.client.get(url, {'condition':'healthy'}).context['total_entries'], 1)
        self.assertEqual(self.client.get(url, {'date':self.today.isoformat()}).context['total_entries'], 1)
        self.assertEqual(self.client.get(url, HTTP_HX_REQUEST='true').status_code, 200)

    def test_history_of_an_empty_book_is_safe(self):
        response = self.client.get(reverse('garden_journal:plant_history', args=['Tidak ada']))
        self.assertEqual(response.context['total_entries'], 0)
        self.assertIsNone(response.context['growth'])

    def test_owned_plants_are_deduplicated_and_removed_plants_are_hidden(self):
        for name, status, patch_obj in [('Bayam','planned',self.patch), ('Bayam','planted',self.patch),
                                        ('','planned',self.patch), ('Cabai','removed',self.patch),
                                        ('Rahasia','growing',self.foreign)]:
            PatchPlant.objects.create(patch=patch_obj, plant_name=name, status=status)
        self.assertEqual(_get_user_patch_plants(self.user), ['Bayam'])
        response = self.client.get(reverse('garden_journal:list'))
        self.assertTrue(response.context['has_planned_plants'])

    def test_setup_preserves_existing_book_and_plants(self):
        PatchPlant.objects.create(patch=self.patch, plant_name='Bayam', status='growing')
        PatchPlant.objects.create(patch=self.patch, plant_name='Bayam', status='planned')
        response = self.client.get(reverse('garden_journal:create'), {'plant_name':'Bayam'})
        self.assertTrue(response.context['is_adding_to_existing_book'])
        self.assertTrue(response.context['start_at_step_2'])
        self.assertEqual(response.context['form'].initial['cover_color'], '#167a38')
        self.assertIn('Bayam', response.context['patch_plants_json'])

    def test_validation_returns_to_the_correct_wizard_step(self):
        for plant, title, step2 in [('', 'Baru', False), ('Mint','',True), ('Bayam','',True)]:
            with self.subTest(plant=plant):
                response = self.client.post(reverse('garden_journal:create'), self.payload(plant_name=plant,title=title))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['start_at_step_2'], step2)

    def test_edit_rejects_invalid_data_without_modifying_the_entry(self):
        response = self.client.post(reverse('garden_journal:edit', args=[self.new.pk]), self.payload(title=''))
        self.assertEqual(response.status_code, 200)
        self.new.refresh_from_db()
        self.assertEqual(self.new.title, 'Tumbuh')

    def test_edit_can_resolve_owned_patch_by_name(self):
        response = self.client.post(reverse('garden_journal:edit', args=[self.new.pk]),
                                    self.payload(ecopatch='',ecopatch_name='Balkon'))
        self.assertEqual(response.status_code, 302)
        self.new.refresh_from_db()
        self.assertEqual(self.new.ecopatch_id, self.patch.pk)

    def test_form_rejects_another_users_patch_and_negative_height(self):
        for changes, field in [({'ecopatch':self.foreign.pk},'ecopatch'), ({'plant_height':'-1'},'plant_height')]:
            form = GardenJournalForm(self.payload(**changes), user=self.user)
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)

    def test_optional_form_owner_and_no_patch_are_safe(self):
        form = GardenJournalForm(self.payload(ecopatch=''))
        self.assertTrue(form.is_valid(), form.errors)
        form = GardenJournalForm(self.payload(ecopatch='',ecopatch_name='Balkon'), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['ecopatch'],self.patch)

    def test_model_updates_patch_snapshot_after_rename(self):
        self.patch.name='Balkon Baru'
        self.patch.save()
        self.new.save()
        self.assertEqual(self.new.ecopatch_name,'Balkon Baru')
        legacy=GardenJournal.objects.create(user=self.user,plant_name='Cabai',ecopatch_name='Balkon Baru',
            date=self.today,title='Lama',notes='Teks')
        self.assertEqual(legacy.ecopatch_id,self.patch.pk)

    def test_delete_redirects_to_book_while_another_entry_remains(self):
        response = self.client.post(reverse('garden_journal:delete',args=[self.old.pk]))
        self.assertRedirects(response, reverse('garden_journal:plant_history',args=['Bayam']))
        self.assertTrue(GardenJournal.objects.filter(pk=self.new.pk).exists())

    def test_upload_rejects_missing_wrong_type_and_oversized_files(self):
        url=reverse('garden_journal:upload_photo',args=[self.old.pk])
        for data in [{}, {'image':SimpleUploadedFile('x.txt',b'plain',content_type='text/plain')},
                     {'image':SimpleUploadedFile('x.png',b'x'*(5*1024*1024+1),content_type='image/png')}]:
            with self.subTest(case=list(data)):
                self.assertEqual(self.client.post(url,data).status_code,400)

    def test_date_parser_handles_absent_and_nonstring_input(self):
        for value in (None, '', 123):
            self.assertIsNone(_filter_date(value))


class JournalSeedCommandTests(TestCase):
    def test_no_users_does_not_create_sample_entries(self):
        stderr=io.StringIO()
        call_command('seed_journal',count=2,stderr=stderr,stdout=io.StringIO())
        self.assertIn('Tidak ada user',stderr.getvalue())
        self.assertEqual(GardenJournal.objects.count(),0)

    def test_unknown_username_is_reported(self):
        stderr=io.StringIO()
        call_command('seed_journal',username='missing',count=2,stderr=stderr,stdout=io.StringIO())
        self.assertIn('tidak ditemukan',stderr.getvalue())

    def test_explicit_user_gets_the_requested_number_of_entries(self):
        user=get_user_model().objects.create_user('seed')
        with patch('garden_journal.management.commands.seed_journal.random.random',return_value=0.8):
            call_command('seed_journal',username='seed',count=2,stdout=io.StringIO())
        self.assertEqual(GardenJournal.objects.filter(user=user).count(),2)
        self.assertFalse(GardenJournal.objects.filter(plant_height__isnull=True).exists())

    def test_default_user_and_optional_height(self):
        user=get_user_model().objects.create_user('seed')
        with patch('garden_journal.management.commands.seed_journal.random.random',return_value=0.1):
            call_command('seed_journal',count=1,stdout=io.StringIO())
        self.assertEqual(GardenJournal.objects.get().user,user)
        self.assertIsNone(GardenJournal.objects.get().plant_height)

    def test_superuser_is_used_only_when_no_regular_user_exists(self):
        user=get_user_model().objects.create_superuser('admin','admin@example.com','example-pass')
        call_command('seed_journal',count=1,stdout=io.StringIO())
        self.assertEqual(GardenJournal.objects.get().user,user)
