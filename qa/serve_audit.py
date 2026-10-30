
import sys, os, json, io
from pathlib import Path
from datetime import date, timedelta
ROOT=Path(__file__).resolve().parent.parent
OUT=Path(os.environ.get('AUDIT_OUTPUT','/tmp/ecopatch-predeploy-20261030'))
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0,str(ROOT))
os.environ['DJANGO_SETTINGS_MODULE']='ecopatch_project.settings'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
from django.conf import settings
settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':str(OUT/'audit.sqlite3')}}
settings.MEDIA_ROOT=OUT/'media'
settings.ALLOWED_HOSTS=['127.0.0.1','localhost','testserver']
settings.DEBUG=True
settings.SECURE_COOKIES=False
settings.SESSION_COOKIE_SECURE=False
settings.CSRF_COOKIE_SECURE=False
settings.EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
import django
django.setup()
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from django.core.files.base import ContentFile
from main.models import Profile
from plant_library.models import Plant
from my_ecopatch.models import EcoPatch,PatchPlant
from garden_journal.models import GardenJournal
from smart_care.models import CareTask
from seed_exchange.models import SeedExchange
from PIL import Image
call_command('migrate',verbosity=0,interactive=False)
User=get_user_model()
u,_=User.objects.get_or_create(username='qa_audit',defaults={'email':'audit@example.invalid','first_name':'Penguji','is_staff':True})
other,_=User.objects.get_or_create(username='qa_other',defaults={'email':'other@example.invalid'})
Profile.objects.update_or_create(user=u,defaults={'city':'Depok','bio':'Kebun kecil untuk memeriksa alur aplikasi.','instagram':'ecopatch_qa','avatar_petak':'happy'})
Profile.objects.update_or_create(user=other,defaults={'city':'Bogor'})
plants=[]
for name,cat,sun in [('Bayam','vegetables','partial'),('Lidah Buaya','indoor_low_light','shade'),('Kangkung','vegetables','full')]:
 p,_=Plant.objects.get_or_create(name=name,defaults={'scientific_name':'Tanaman contoh','category':cat,'sunlight':sun,'watering':'moderate','difficulty':'easy','indoor_outdoor':'both','space_requirement':'any','description':'Tanaman untuk audit fungsi dan responsivitas.'})
 plants.append(p)
patch,_=EcoPatch.objects.get_or_create(owner=u,name='Balkon Belakang',defaults={'space_type':'balcony','size_m2':4,'sunlight':'partial','city':'Depok','goal':'Menanam sayur untuk kebutuhan rumah.'})
for i,p in enumerate(plants):
 PatchPlant.objects.get_or_create(patch=patch,plant=p,defaults={'quantity':i+1,'status':['growing','planted','planned'][i],'planted_at':timezone.localdate()})
empty,_=EcoPatch.objects.get_or_create(owner=u,name='Teras Rumah',defaults={'space_type':'terrace','city':'Depok'})
foreign,_=EcoPatch.objects.get_or_create(owner=other,name='Kebun Pengguna Lain',defaults={'space_type':'small_yard','city':'Bogor'})
buf=io.BytesIO();Image.new('RGB',(320,240),'#73a965').save(buf,'PNG');image=buf.getvalue()
j,_=GardenJournal.objects.get_or_create(user=u,plant_name='Bayam',title='Daun baru mulai tumbuh',defaults={'ecopatch':patch,'ecopatch_name':patch.name,'date':timezone.localdate(),'notes':'Ada daun baru. Penyiraman dilakukan pagi hari.','plant_height':12,'plant_condition':'healthy'})
if not j.image:j.image.save('audit-plant.png',ContentFile(image))
GardenJournal.objects.get_or_create(user=u,plant_name='Bayam',title='Hari pertama menanam',defaults={'ecopatch':patch,'date':timezone.localdate()-timedelta(days=2),'notes':'Mulai menanam di balkon.','plant_height':7,'plant_condition':'healthy'})
pp=patch.plants.get(plant=plants[0])
task,_=CareTask.objects.get_or_create(user=u,patch_plant=pp,task_type='watering',due_date=timezone.localdate(),defaults={'plant_name':'Bayam','notes':'Periksa kelembapan tanah.'})
listing,_=SeedExchange.objects.get_or_create(user=u,title='Bibit Bayam untuk dibagikan',defaults={'item_type':'seed','plant_name':'Bayam','city':'Depok','contact':'Instagram @ecopatch_qa','transaction_type':'giveaway','description':'Bibit sehat, tersedia untuk dibagikan.'})
if not listing.image:listing.image.save('audit-seed.png',ContentFile(image))
public,_=SeedExchange.objects.get_or_create(user=other,title='Bibit Kangkung',defaults={'item_type':'seedling','plant_name':'Kangkung','city':'Bogor','contact':'Instagram @ecopatch_qa','transaction_type':'swap'})
if not public.image:public.image.save('audit-other.png',ContentFile(image))
c=Client();c.force_login(u)
manifest={'cookie':c.cookies['sessionid'].value,'patch':patch.pk,'empty_patch':empty.pk,'plant':plants[0].pk,'patchplant':pp.pk,'journal':j.pk,'task':task.pk,'listing':listing.pk,'other_listing':public.pk}
(OUT/'manifest.json').write_text(json.dumps(manifest))
# Keep browser tests deterministic and avoid real network calls to the weather provider.
import smart_care.views as careviews
careviews.weather_payload=lambda *args,**kwargs:{'available':False,'city':'Depok','message':'Cuaca tidak tersedia untuk audit lokal.'}
print('AUDIT_READY http://127.0.0.1:8765',flush=True)
call_command('runserver','127.0.0.1:8765',use_reloader=False,verbosity=0)
