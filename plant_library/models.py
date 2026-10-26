from django.db import models


class Plant(models.Model):
    class Category(models.TextChoices):
        VEGETABLES = 'vegetables', 'Vegetables'
        HERBS = 'herbs', 'Herbs'
        FRUIT_CONTAINER = 'fruit_container', 'Fruit / Container Plants'
        FLOWERS = 'flowers', 'Flowers'
        INDOOR_LOW_LIGHT = 'indoor_low_light', 'Indoor / Low-Light Plants'
        AROMATIC_USEFUL = 'aromatic_useful', 'Aromatic / Useful Plants'

    # Pilihan sementara untuk sunlight (akan dikonfirmasi ke Haikal)
    class Sunlight(models.TextChoices):
        FULL = 'full', 'Full Sun'
        PARTIAL = 'partial', 'Partial Sun'
        SHADE = 'shade', 'Shade'

    class Watering(models.TextChoices):
        LOW = 'low', 'Low (Jarang)'
        MODERATE = 'moderate', 'Moderate (Sedang)'
        HIGH = 'high', 'High (Sering)'

    class Difficulty(models.TextChoices):
        EASY = 'easy', 'Easy'
        MEDIUM = 'medium', 'Medium'
        HARD = 'hard', 'Hard'

    class Placement(models.TextChoices):
        INDOOR = 'indoor', 'Indoor'
        OUTDOOR = 'outdoor', 'Outdoor'
        BOTH = 'both', 'Indoor & Outdoor'

    # Pilihan sementara untuk space_requirement (akan dikonfirmasi ke Haikal)
    class SpaceRequirement(models.TextChoices):
        BALCONY = 'balcony', 'Balcony'
        INDOOR = 'indoor', 'Indoor'
        TERRACE = 'terrace', 'Terrace'
        ROOFTOP = 'rooftop', 'Rooftop'
        SMALL_YARD = 'small_yard', 'Small Yard'
        ANY = 'any', 'Any Space / Fleksibel'

    name = models.CharField(max_length=100)
    scientific_name = models.CharField(max_length=150, blank=True, default='')
    category = models.CharField(max_length=30, choices=Category.choices)
    sunlight = models.CharField(max_length=20, choices=Sunlight.choices)
    watering = models.CharField(max_length=20, choices=Watering.choices)
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices)
    indoor_outdoor = models.CharField(max_length=20, choices=Placement.choices)
    space_requirement = models.CharField(max_length=30, choices=SpaceRequirement.choices)
    description = models.TextField(blank=True, default='')
    image_url = models.URLField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    # Hari antar dua penyiraman menurut kolom watering. Dipakai Smart Care untuk saran siram.
    WATERING_BASE_DAYS = {Watering.HIGH: 1, Watering.MODERATE: 2, Watering.LOW: 4}
    WATERING_MAX_DAYS = 6

    @property
    def watering_interval_days(self):
        """Perkiraan hari antar dua penyiraman, disesuaikan dengan tanamannya.

        Dasar dari frekuensi penyiraman (sering 1, sedang 2, jarang 4). Tanaman dalam ruangan dan tanaman
        tempat teduh lebih lambat kering, jadi masing-masing menambah satu hari. Paling lama 6 hari.
        """
        days = self.WATERING_BASE_DAYS.get(self.watering, self.WATERING_BASE_DAYS[self.Watering.MODERATE])
        if self.indoor_outdoor == self.Placement.INDOOR or self.category == self.Category.INDOOR_LOW_LIGHT:
            days += 1
        if self.sunlight == self.Sunlight.SHADE:
            days += 1
        return min(days, self.WATERING_MAX_DAYS)

