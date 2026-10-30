from django import forms
from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from .models import EcoPatch, PatchPlant
from .templatetags.patch_extras import is_select, select_data
from .views import _scene_plots


class DropdownDataTests(SimpleTestCase):
    def form(self, required=True, value=None):
        class Options(forms.Form):
            room=forms.ChoiceField(label='Ruang',required=required,
                choices=[('', 'Pilih ruang'), ('balcony','Balkon'), ('indoor','Dalam ruangan')])
            name=forms.CharField()
        return Options(initial={'room':value})

    def test_select_detection(self):
        form=self.form()
        self.assertTrue(is_select(form['room']))
        self.assertFalse(is_select(form['name']))

    def test_required_dropdown_uses_empty_choice_only_as_placeholder(self):
        data=select_data(self.form(value='balcony')['room'])
        self.assertEqual(data['display'],'Balkon')
        self.assertEqual(data['placeholder'],'Pilih ruang')
        self.assertEqual([o['value'] for o in data['options']],['balcony','indoor'])

    def test_optional_dropdown_can_be_cleared(self):
        data=select_data(self.form(required=False,value='')['room'])
        self.assertTrue(data['options'][0]['selected'])
        self.assertEqual(data['value'],'')

    def test_unknown_saved_choice_is_not_resubmitted(self):
        self.assertEqual(select_data(self.form(value='removed-choice')['room'])['value'],'')
        self.assertEqual(select_data(self.form()['room'])['display'],'')


class GardenEdgeFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=get_user_model().objects.create_user('garden')
        cls.patch=EcoPatch.objects.create(owner=cls.user,name='Balkon',space_type='balcony',city='Depok')

    def setUp(self):
        self.client.force_login(self.user)

    def test_hero_reflects_each_real_growing_stage(self):
        for status,expected in [('planned','seed'),('planted','sprout'),('growing','grow'),
                                ('harvested','harvest'),('removed','bare')]:
            plant=PatchPlant.objects.create(patch=self.patch,plant_name='Legacy',status=status)
            self.assertEqual(_scene_plots(EcoPatch.objects.filter(owner=self.user))[0]['stage'],expected)
            plant.delete()

    def test_invalid_update_does_not_change_patch(self):
        response=self.client.post(reverse('my_ecopatch:update',args=[self.patch.pk]),{'name':'','space_type':'invalid'})
        self.assertEqual(response.status_code,200)
        self.patch.refresh_from_db()
        self.assertEqual(self.patch.name,'Balkon')

    def test_plain_status_post_redirects_and_plain_delete_preserves_patch(self):
        plant=PatchPlant.objects.create(patch=self.patch,plant_name='Legacy')
        self.assertIn('Legacy',str(plant))
        self.assertEqual(str(self.patch),'Balkon')
        response=self.client.post(reverse('my_ecopatch:plant_status',args=[plant.pk]),{'status':'growing'})
        self.assertEqual(response.status_code,302)
        plant.refresh_from_db()
        self.assertEqual(plant.status,'growing')
        self.assertEqual(self.client.post(reverse('my_ecopatch:plant_delete',args=[plant.pk])).status_code,302)
        self.assertTrue(EcoPatch.objects.filter(pk=self.patch.pk).exists())
