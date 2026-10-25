"""Tests for tasks, suggestions, plant source and the AJAX / page views.
Weather and recommendation rules are tested in tests.py. Nothing here touches the network."""
import importlib
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.apps import apps
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from my_ecopatch.models import EcoPatch, PatchPlant
from plant_library.models import Plant

from .models import CareTask
from .plant_source import find_patch_plant, get_user_city, get_user_plants, link_task
from .suggestions import INTERVALS, HistoryEntry, build_suggestions, plant_status
from .tests import API_RESPONSE, fake_response
from .weather import WeatherUnavailable

FAST_HASHER = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


def make_task(user, **kwargs):
    fields = {"plant_name": "Cabai", "task_type": "watering", "due_date": timezone.localdate()}
    fields.update(kwargs)
    return CareTask.objects.create(user=user, **fields)


def completed_task(user, plant_name, task_type, days_ago, **kwargs):
    """A task that was completed `days_ago` days ago (completed_at and due_date both set back)."""
    day = timezone.localdate() - timedelta(days=days_ago)
    task = make_task(user, plant_name=plant_name, task_type=task_type, due_date=day, **kwargs)
    task.set_status(CareTask.Status.COMPLETED)
    CareTask.objects.filter(pk=task.pk).update(completed_at=timezone.now() - timedelta(days=days_ago))
    task.refresh_from_db()
    return task


def make_patch(user, name=None, space_type="balcony", city="Depok"):
    return EcoPatch.objects.create(owner=user, name=name or f"Kebun {user.username}", space_type=space_type, city=city)


def make_patch_plant(user, name="Cabai", patch=None, status="planted", **kwargs):
    """A plant in the user's My EcoPatch, typed by name (the old way). Pass plant= and name="" for a library plant."""
    return PatchPlant.objects.create(patch=patch or make_patch(user), plant_name=name, status=status, **kwargs)


def make_library_plant(name):
    return Plant.objects.create(
        name=name, category="herbs", sunlight="full", watering="moderate",
        difficulty="easy", indoor_outdoor="both", space_requirement="any",
    )


class CacheClearingTestCase(TestCase):
    def setUp(self):
        cache.clear()


@FAST_HASHER
class CareTaskModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass12345")

    def test_defaults(self):
        task = make_task(self.user)
        self.assertEqual(task.status, CareTask.Status.PENDING)
        self.assertEqual(task.source, CareTask.Source.MANUAL)
        self.assertTrue(task.is_outdoor)
        self.assertFalse(task.is_completed)
        self.assertIsNone(task.completed_at)

    def test_due_date_defaults_to_today(self):
        task = CareTask.objects.create(user=self.user, plant_name="Basil", task_type="pruning")
        self.assertEqual(task.due_date, timezone.localdate())

    def test_str(self):
        self.assertIn("Cabai", str(make_task(self.user)))

    def test_toggle_flips_pending_and_completed_and_sets_completed_at(self):
        task = make_task(self.user)
        task.toggle()
        self.assertEqual(task.status, CareTask.Status.COMPLETED)
        self.assertTrue(task.is_completed)
        self.assertIsNotNone(task.completed_at)
        task.toggle()
        self.assertEqual(task.status, CareTask.Status.PENDING)
        self.assertIsNone(task.completed_at)

    def test_skipped_task_cannot_be_toggled(self):
        task = make_task(self.user)
        task.set_status(CareTask.Status.SKIPPED)
        with self.assertRaises(ValueError):
            task.toggle()

    def test_a_suggestion_cannot_be_stored_twice_for_the_same_day(self):
        make_task(self.user, source="suggested")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_task(self.user, source="suggested")

    def test_manual_tasks_may_repeat_on_the_same_day(self):
        make_task(self.user)
        make_task(self.user)
        self.assertEqual(CareTask.objects.count(), 2)


class BuildSuggestionsTests(SimpleTestCase):
    today = date(2026, 10, 24)
    plants = [("Cabai", True)]

    def entry(self, task_type, status, days_ago, plant="Cabai"):
        day = self.today - timedelta(days=days_ago)
        return HistoryEntry(plant, task_type, status, day, day if status == "completed" else None)

    def suggested(self, history, plants=None):
        found = build_suggestions(plants or self.plants, history, self.today)
        return {(item["plant_name"], item["task_type"]): item for item in found}

    def test_intervals_are_the_documented_defaults(self):
        self.assertEqual(INTERVALS, {"watering": 2, "fertilizing": 14, "inspection": 7})

    def test_never_recorded_is_suggested_with_that_reason(self):
        found = self.suggested([])
        self.assertEqual(set(found), {("Cabai", "watering"), ("Cabai", "fertilizing"), ("Cabai", "inspection")})
        self.assertEqual(found[("Cabai", "watering")]["reason"], "Belum pernah dicatat")

    def test_result_carries_the_fields_the_page_needs(self):
        item = build_suggestions([("Lidah mertua", False)], [], self.today)[0]
        self.assertEqual(set(item), {"plant_name", "task_type", "is_outdoor", "reason"})
        self.assertFalse(item["is_outdoor"])

    def test_interval_not_yet_passed_means_no_suggestion(self):
        found = self.suggested([self.entry("watering", "completed", 1)])
        self.assertNotIn(("Cabai", "watering"), found)

    def test_interval_reached_is_suggested_with_days_in_the_reason(self):
        found = self.suggested([self.entry("watering", "completed", 2)])
        self.assertEqual(found[("Cabai", "watering")]["reason"], "Terakhir disiram 2 hari lalu")

    def test_long_ago_fertilizing_reason(self):
        found = self.suggested([self.entry("fertilizing", "completed", 15)])
        self.assertEqual(found[("Cabai", "fertilizing")]["reason"], "Terakhir dipupuk 15 hari lalu")

    def test_only_the_latest_completion_counts(self):
        history = [self.entry("watering", "completed", 10), self.entry("watering", "completed", 1)]
        self.assertNotIn(("Cabai", "watering"), self.suggested(history))

    def test_nothing_is_suggested_when_today_already_has_a_task_of_any_status(self):
        for status in ("pending", "completed", "skipped"):
            history = [self.entry("watering", status, 0)]
            self.assertNotIn(("Cabai", "watering"), self.suggested(history), status)

    def test_a_task_today_for_another_type_or_plant_does_not_block(self):
        history = [self.entry("fertilizing", "pending", 0), self.entry("watering", "pending", 0, plant="Tomat")]
        self.assertIn(("Cabai", "watering"), self.suggested(history))

    def test_skipped_does_not_count_as_a_completion(self):
        found = self.suggested([self.entry("watering", "skipped", 3)])
        self.assertIn(("Cabai", "watering"), found)
        self.assertEqual(found[("Cabai", "watering")]["reason"], "Belum pernah dicatat")

    def test_pruning_repotting_harvesting_are_never_suggested(self):
        types = {task_type for _, task_type in self.suggested([])}
        self.assertTrue(types.isdisjoint({"pruning", "repotting", "harvesting"}))

    def test_plant_names_match_ignoring_case_and_spaces(self):
        history = [self.entry("watering", "completed", 0, plant="  cabai ")]
        self.assertNotIn(("Cabai", "watering"), self.suggested(history))

    def test_never_recorded_types_can_be_trimmed_without_losing_interval_suggestions(self):
        history = [self.entry("fertilizing", "completed", 20)]
        found = build_suggestions(self.plants, history, self.today, never_recorded=("watering",))
        types = {item["task_type"] for item in found}
        self.assertEqual(types, {"watering", "fertilizing"})  # inspection is skipped, fertilizing is overdue

    def test_yesterday_reads_naturally(self):
        found = build_suggestions(self.plants, [self.entry("watering", "completed", 1)], self.today, intervals={"watering": 1})
        self.assertEqual(found[0]["reason"], "Terakhir disiram kemarin")


class PlantStatusTests(SimpleTestCase):
    today = date(2026, 10, 24)
    plant = ("Cabai", True)

    def done(self, task_type, days_ago, plant="Cabai"):
        day = self.today - timedelta(days=days_ago)
        return HistoryEntry(plant, task_type, "completed", day, day)

    def status(self, history):
        return plant_status(self.plant, history, self.today)

    def test_never_recorded_shows_an_empty_pot_with_that_label(self):
        status = self.status([])
        self.assertEqual((status["water"], status["label"]), (0.0, "Belum dicatat"))
        self.assertTrue(status["never_recorded"])
        self.assertFalse(status["watering_due"])

    def test_just_watered_is_full(self):
        status = self.status([self.done("watering", 0)])
        self.assertEqual((status["water"], status["label"]), (1.0, "Baru disiram"))
        self.assertFalse(status["never_recorded"])

    def test_halfway_through_the_interval(self):
        status = self.status([self.done("watering", 1)])
        self.assertEqual((status["water"], status["label"]), (0.5, "Siram besok"))
        self.assertFalse(status["watering_due"])

    def test_interval_reached_means_empty_and_due(self):
        status = self.status([self.done("watering", 2)])
        self.assertEqual((status["water"], status["label"]), (0.0, "Waktunya siram"))
        self.assertTrue(status["watering_due"])

    def test_fraction_is_clamped_between_zero_and_one(self):
        self.assertEqual(self.status([self.done("watering", 30)])["water"], 0.0)
        self.assertEqual(self.status([self.done("watering", -3)])["water"], 1.0)  # completed "in the future"

    def test_longer_interval_counts_days_left(self):
        status = plant_status(self.plant, [self.done("watering", 1)], self.today, intervals={**INTERVALS, "watering": 4})
        self.assertEqual((status["water"], status["label"]), (0.75, "Siram 3 hari lagi"))

    def test_the_latest_watering_counts(self):
        status = self.status([self.done("watering", 9), self.done("watering", 0)])
        self.assertEqual(status["water"], 1.0)

    def test_fertilizing_and_inspection_dots(self):
        fresh = self.status([self.done("fertilizing", 3), self.done("inspection", 3)])
        self.assertTrue(fresh["fertilizing_ok"] and fresh["inspection_ok"])
        due = self.status([self.done("fertilizing", 14), self.done("inspection", 7)])
        self.assertFalse(due["fertilizing_ok"] or due["inspection_ok"])
        self.assertFalse(self.status([])["fertilizing_ok"])  # never recorded counts as due

    def test_other_plants_and_skipped_entries_are_ignored(self):
        skipped = HistoryEntry("Cabai", "watering", "skipped", self.today, None)
        status = self.status([self.done("watering", 0, plant="Tomat"), skipped])
        self.assertTrue(status["never_recorded"])

    def test_names_match_ignoring_case_and_spaces(self):
        self.assertEqual(self.status([self.done("watering", 0, plant="  cabai ")])["water"], 1.0)


@FAST_HASHER
class PlantSourceTests(TestCase):
    """Smart Care learns the user's plants from My EcoPatch, never from the tasks."""

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass12345")
        self.other = User.objects.create_user("bob", password="pass12345")

    def test_only_the_users_own_plants(self):
        make_patch_plant(self.user, "Cabai")
        make_patch_plant(self.other, "Tomat bob")
        self.assertEqual(get_user_plants(self.user), [("Cabai", True)])
        self.assertEqual(get_user_plants(self.other), [("Tomat bob", True)])

    def test_tasks_alone_do_not_make_a_plant(self):
        make_task(self.user, plant_name="Cabai")
        self.assertEqual(get_user_plants(self.user), [])

    def test_only_planted_and_growing_plants_take_part(self):
        patch_ = make_patch(self.user)
        for status in ("planned", "planted", "growing", "harvested", "removed"):
            make_patch_plant(self.user, status.capitalize(), patch=patch_, status=status)
        self.assertEqual([name for name, _ in get_user_plants(self.user)], ["Growing", "Planted"])

    def test_the_name_comes_from_the_plant_library_when_linked(self):
        make_patch_plant(self.user, name="", plant=make_library_plant("Basil"))
        make_patch_plant(self.user, name="Cabai")
        self.assertEqual(get_user_plants(self.user), [("Basil", True), ("Cabai", True)])

    def test_a_plant_in_two_patches_is_listed_once_and_the_newest_row_decides(self):
        make_patch_plant(self.user, "Cabai", patch=make_patch(self.user, "Balkon", "balcony"))
        make_patch_plant(self.user, "  cabai ", patch=make_patch(self.user, "Kamar", "indoor"))
        self.assertEqual(get_user_plants(self.user), [("cabai", False)])

    def test_outdoor_follows_the_space_type_of_the_patch(self):
        for space_type, outdoor in (("balcony", True), ("terrace", True), ("rooftop", True), ("small_yard", True), ("indoor", False)):
            user = User.objects.create_user(f"u_{space_type}", password="pass12345")
            make_patch_plant(user, "Cabai", patch=make_patch(user, space_type=space_type))
            self.assertEqual(get_user_plants(user), [("Cabai", outdoor)], space_type)

    def test_a_plant_without_any_name_is_skipped(self):
        make_patch_plant(self.user, name="")
        self.assertEqual(get_user_plants(self.user), [])

    def test_find_patch_plant_ignores_case_spaces_and_other_users(self):
        mine = make_patch_plant(self.user, "Cabai Rawit")
        make_patch_plant(self.other, "Tomat bob")
        self.assertEqual(find_patch_plant(self.user, "  cabai   RAWIT "), mine)
        self.assertIsNone(find_patch_plant(self.user, "Tomat bob"))
        self.assertIsNone(find_patch_plant(self.user, ""))

    def test_user_without_plants_has_none(self):
        self.assertEqual(get_user_plants(self.user), [])

    def test_city_is_the_one_of_the_newest_patch_with_a_plant_to_care_for(self):
        self.assertEqual(get_user_city(self.user), "")
        make_patch_plant(self.user, "Cabai", patch=make_patch(self.user, city="Bandung"), status="planned")
        self.assertEqual(get_user_city(self.user), "")  # nothing is planted yet
        make_patch_plant(self.user, "Basil", patch=make_patch(self.user, city="Malang"))
        make_patch_plant(self.user, "Mint", patch=make_patch(self.user, city="Medan"))
        self.assertEqual(get_user_city(self.user), "Medan")
        self.assertEqual(get_user_city(self.other), "")


@FAST_HASHER
class CareViewTests(CacheClearingTestCase):
    """Page, CRUD, toggle, date browsing and the weather endpoint. Suggestions are switched off here
    (they have their own test case) so the counts only reflect the tasks the test creates."""

    def setUp(self):
        super().setUp()
        patcher = patch("smart_care.views.build_suggestions", return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user("alice", password="pass12345")
        self.other = User.objects.create_user("bob", password="pass12345")
        self.client.login(username="alice", password="pass12345")

    # ---- access control
    def test_guest_is_redirected_to_login_everywhere(self):
        self.client.logout()
        task = make_task(self.user)
        urls = [
            reverse("smart_care:list"),
            reverse("smart_care:weather"),
            reverse("smart_care:create"),
            reverse("smart_care:update", args=[task.pk]),
            reverse("smart_care:delete", args=[task.pk]),
            reverse("smart_care:complete", args=[task.pk]),
            reverse("smart_care:suggestion_accept"),
            reverse("smart_care:suggestion_skip"),
            reverse("smart_care:suggestion_restore"),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn(reverse("main:login"), response["Location"], url)

    def test_other_users_task_is_a_404_for_every_action(self):
        task = make_task(self.other)
        self.assertEqual(self.client.get(reverse("smart_care:update", args=[task.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("smart_care:update", args=[task.pk]), {}).status_code, 404)
        self.assertEqual(self.client.post(reverse("smart_care:delete", args=[task.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("smart_care:complete", args=[task.pk])).status_code, 404)
        task.refresh_from_db()
        self.assertEqual(task.status, CareTask.Status.PENDING)

    def test_list_only_shows_own_tasks(self):
        make_task(self.user, plant_name="Cabai saya")
        make_task(self.other, plant_name="Tomat bob")
        response = self.client.get(reverse("smart_care:list"))
        self.assertContains(response, "Cabai saya")
        self.assertNotContains(response, "Tomat bob")

    # ---- CRUD
    def test_create_assigns_logged_in_user_and_defaults(self):
        plant = make_patch_plant(self.user, "Basil")
        response = self.client.post(reverse("smart_care:create"), {
            "patch_plant": plant.pk, "task_type": "pruning", "due_date": "2026-11-02", "notes": "",
        })
        self.assertRedirects(response, reverse("smart_care:list") + "?date=2026-11-02", fetch_redirect_response=False)
        task = CareTask.objects.get()
        self.assertEqual(task.user, self.user)
        self.assertEqual(task.patch_plant, plant)
        self.assertEqual(task.plant_name, "Basil")
        self.assertEqual(task.source, CareTask.Source.MANUAL)
        self.assertEqual(task.status, CareTask.Status.PENDING)

    def test_manual_form_has_no_repeat_field(self):
        response = self.client.get(reverse("smart_care:create"))
        self.assertNotContains(response, "repeat_every_days")
        self.assertNotContains(response, "Ulangi")

    def test_outdoor_flag_is_taken_from_the_plants_patch(self):
        indoor = make_patch_plant(self.user, "Lidah mertua", patch=make_patch(self.user, space_type="indoor"))
        outdoor = make_patch_plant(self.user, "Cabai")
        for plant in (indoor, outdoor):
            self.client.post(reverse("smart_care:create"), {
                "patch_plant": plant.pk, "task_type": "inspection", "due_date": "2026-11-02",
            })
        self.assertEqual(dict(CareTask.objects.values_list("plant_name", "is_outdoor")), {"Lidah mertua": False, "Cabai": True})

    def test_update_own_task(self):
        task = make_task(self.user)
        plant = make_patch_plant(self.user, "Cabai merah")
        self.client.post(reverse("smart_care:update", args=[task.pk]), {
            "patch_plant": plant.pk, "task_type": "pruning", "due_date": task.due_date.isoformat(),
        })
        task.refresh_from_db()
        self.assertEqual(task.patch_plant, plant)
        self.assertEqual(task.plant_name, "Cabai merah")
        self.assertEqual(task.task_type, "pruning")

    # ---- the plant choice
    def test_a_new_task_needs_a_plant(self):
        response = self.client.post(reverse("smart_care:create"), {"task_type": "pruning", "due_date": "2026-11-02"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context["form"].errors), {"patch_plant"})
        self.assertEqual(CareTask.objects.count(), 0)

    def test_another_users_plant_is_rejected_on_the_server(self):
        theirs = make_patch_plant(self.other, "Tomat bob")
        response = self.client.post(reverse("smart_care:create"), {
            "patch_plant": theirs.pk, "task_type": "pruning", "due_date": "2026-11-02",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("patch_plant", response.context["form"].errors)
        self.assertEqual(CareTask.objects.count(), 0)

    def test_a_plant_that_is_not_planted_yet_is_rejected_on_the_server(self):
        for status in ("planned", "harvested", "removed"):
            plant = make_patch_plant(self.user, status.capitalize(), status=status)
            response = self.client.post(reverse("smart_care:create"), {
                "patch_plant": plant.pk, "task_type": "pruning", "due_date": "2026-11-02",
            })
            self.assertIn("patch_plant", response.context["form"].errors, status)
        self.assertEqual(CareTask.objects.count(), 0)

    def test_the_form_offers_only_the_users_own_planted_or_growing_plants(self):
        make_patch_plant(self.user, "Cabai")
        make_patch_plant(self.user, "Rencana", status="planned")
        make_patch_plant(self.user, "Dibuang", status="removed")
        make_patch_plant(self.other, "Tomat bob")
        response = self.client.get(reverse("smart_care:create"))
        self.assertContains(response, "Cabai (Kebun alice)")  # the patch tells apart two plants with one name
        for name in ("Rencana", "Dibuang", "Tomat bob"):
            self.assertNotContains(response, name)

    def test_the_form_says_what_to_do_when_there_is_no_plant(self):
        response = self.client.get(reverse("smart_care:create"))
        self.assertContains(response, "Belum ada tanaman yang sedang ditanam")
        self.assertContains(response, reverse("my_ecopatch:list"))
        make_patch_plant(self.user)
        self.assertNotContains(self.client.get(reverse("smart_care:create")), "Belum ada tanaman yang sedang ditanam")

    def test_linking_copies_the_plants_name_onto_the_task(self):
        plant = make_patch_plant(self.user, name="", plant=make_library_plant("Basil"))
        self.client.post(reverse("smart_care:create"), {
            "patch_plant": plant.pk, "task_type": "pruning", "due_date": "2026-11-02",
        })
        Plant.objects.filter(pk=plant.plant_id).update(name="Basil thai")  # renamed in the library afterwards
        task = CareTask.objects.get()
        self.assertEqual(task.plant_name, "Basil")

    def test_removing_the_plant_keeps_the_task_and_its_name(self):
        plant = make_patch_plant(self.user, "Cabai")
        self.client.post(reverse("smart_care:create"), {
            "patch_plant": plant.pk, "task_type": "pruning", "due_date": "2026-11-02",
        })
        plant.delete()
        task = CareTask.objects.get()
        self.assertIsNone(task.patch_plant)
        self.assertEqual(task.plant_name, "Cabai")

    def test_a_task_without_a_plant_can_still_be_edited(self):
        old = make_task(self.user, plant_name="Lama")
        response = self.client.post(reverse("smart_care:update", args=[old.pk]), {
            "task_type": "pruning", "due_date": old.due_date.isoformat(), "notes": "catatan",
        })
        self.assertEqual(response.status_code, 302)
        old.refresh_from_db()
        self.assertEqual((old.plant_name, old.task_type, old.patch_plant, old.notes), ("Lama", "pruning", None, "catatan"))

    def test_editing_keeps_the_tasks_plant_selectable_after_its_status_moved_on(self):
        plant = make_patch_plant(self.user, "Cabai", status="harvested")
        task = make_task(self.user)
        link_task(task, plant)
        task.save()
        self.assertContains(self.client.get(reverse("smart_care:update", args=[task.pk])), "Cabai (Kebun alice)")

    def test_delete_own_task_requires_post(self):
        task = make_task(self.user)
        self.assertEqual(self.client.get(reverse("smart_care:delete", args=[task.pk])).status_code, 405)
        self.client.post(reverse("smart_care:delete", args=[task.pk]))
        self.assertFalse(CareTask.objects.filter(pk=task.pk).exists())

    def test_list_uses_a_bootstrap_modal_for_delete_not_confirm(self):
        make_task(self.user)
        response = self.client.get(reverse("smart_care:list"))
        self.assertContains(response, 'id="care-delete-modal"')
        self.assertContains(response, "data-delete-url")
        self.assertNotContains(response, "confirm(")

    # ---- popup (HTMX)
    def test_htmx_get_returns_only_the_popup_content(self):
        response = self.client.get(reverse("smart_care:create"), HTTP_HX_REQUEST="true")
        self.assertContains(response, "modal-header")
        self.assertContains(response, "Pilih jenis tugas")
        self.assertNotContains(response, "<html")

    def test_htmx_valid_post_redirects_via_header(self):
        plant = make_patch_plant(self.user, "Basil")
        response = self.client.post(reverse("smart_care:create"), {
            "patch_plant": plant.pk, "task_type": "pruning", "due_date": "2026-11-02",
        }, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 204)
        self.assertIn("date=2026-11-02", response["HX-Redirect"])

    def test_htmx_invalid_post_redisplays_the_popup(self):
        response = self.client.post(reverse("smart_care:create"), {"plant_name": ""}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "care-field-error")
        self.assertNotContains(response, "<html")

    # ---- completion (AJAX)
    def test_complete_toggles_and_returns_json(self):
        task = make_task(self.user)
        make_task(self.user, plant_name="Tomat")
        url = reverse("smart_care:complete", args=[task.pk])

        data = self.client.post(url).json()
        self.assertEqual(data["status"], "completed")
        self.assertTrue(data["is_completed"])
        self.assertEqual(data["progress"], {"total": 2, "done": 1, "pending": 1, "percent": 50, "stage": 2})
        task.refresh_from_db()
        self.assertEqual(task.status, CareTask.Status.COMPLETED)
        self.assertIsNotNone(task.completed_at)

        data = self.client.post(url).json()  # tick again = undo
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["progress"]["done"], 0)

    def test_complete_requires_post(self):
        task = make_task(self.user)
        self.assertEqual(self.client.get(reverse("smart_care:complete", args=[task.pk])).status_code, 405)

    def test_complete_refuses_a_skipped_task(self):
        task = make_task(self.user)
        task.set_status(CareTask.Status.SKIPPED)
        response = self.client.post(reverse("smart_care:complete", args=[task.pk]))
        self.assertEqual(response.status_code, 409)
        task.refresh_from_db()
        self.assertEqual(task.status, CareTask.Status.SKIPPED)

    def test_progress_stage_covers_all_four_states(self):
        tasks = [make_task(self.user, plant_name=f"T{i}") for i in range(4)]
        stages = []
        for task in tasks:
            stages.append(self.client.post(reverse("smart_care:complete", args=[task.pk])).json()["progress"]["stage"])
        self.assertEqual(stages, [1, 2, 2, 3])

    def test_skipped_tasks_are_hidden_and_not_counted(self):
        make_task(self.user, plant_name="Terlihat")
        make_task(self.user, plant_name="Disembunyikan").set_status(CareTask.Status.SKIPPED)
        response = self.client.get(reverse("smart_care:list"))
        self.assertContains(response, "Terlihat")
        self.assertNotContains(response, 'aria-label="Edit Disembunyikan"')
        self.assertEqual(response.context["progress"]["total"], 1)

    # ---- date browsing
    def test_list_filters_by_date_and_builds_a_seven_day_strip(self):
        make_task(self.user, plant_name="Hari ini", due_date=timezone.localdate())
        make_task(self.user, plant_name="Besok", due_date=timezone.localdate() + timedelta(days=1))
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.get(reverse("smart_care:list"), {"date": tomorrow})
        self.assertContains(response, "Besok")
        self.assertNotContains(response, 'care-task-name">Hari ini')  # today's task row is not shown on tomorrow
        self.assertEqual(len(response.context["strip"]), 7)
        self.assertEqual(response.context["strip"][3]["date"].isoformat(), tomorrow)
        self.assertTrue(response.context["strip"][3]["is_selected"])

    def test_date_navigation_is_labelled(self):
        response = self.client.get(reverse("smart_care:list"))
        for label in ("Minggu lalu", "Hari ini", "Minggu depan", "Pilih tanggal"):
            self.assertContains(response, label)
        self.assertContains(response, 'type="date"')
        self.assertContains(response, 'aria-current="date"')  # today's button reads as the current one
        previous_week = (timezone.localdate() - timedelta(days=7)).isoformat()
        self.assertEqual(response.context["prev_week_url"], reverse("smart_care:list") + "?date=" + previous_week)

    def test_strip_counts_pending_tasks_per_day(self):
        today = timezone.localdate()
        make_task(self.user, due_date=today)
        make_task(self.user, due_date=today, plant_name="Selesai").toggle()
        make_task(self.user, due_date=today + timedelta(days=2))
        counts = {day["date"]: day["pending"] for day in self.client.get(reverse("smart_care:list")).context["strip"]}
        self.assertEqual(counts[today], 1)
        self.assertEqual(counts[today + timedelta(days=2)], 1)
        self.assertEqual(counts[today - timedelta(days=1)], 0)

    def test_overdue_shows_only_when_viewing_today(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        make_task(self.user, plant_name="Kemarin", due_date=yesterday)
        today_view = self.client.get(reverse("smart_care:list"))
        self.assertEqual([t.plant_name for t in today_view.context["overdue_tasks"]], ["Kemarin"])
        other_view = self.client.get(reverse("smart_care:list"), {"date": (timezone.localdate() + timedelta(days=3)).isoformat()})
        self.assertEqual(list(other_view.context["overdue_tasks"]), [])

    def test_bad_date_falls_back_to_today(self):
        response = self.client.get(reverse("smart_care:list"), {"date": "bukan-tanggal"})
        self.assertEqual(response.context["selected_date"], timezone.localdate())

    # ---- weather endpoint (fetch mocked, never the network)
    @patch("smart_care.views.weather_payload")
    def test_weather_endpoint_returns_json_and_remembers_city(self, mock_payload):
        mock_payload.return_value = {"available": True, "city": "Bandung"}
        response = self.client.get(reverse("smart_care:weather"), {"city": "Bandung"})
        self.assertEqual(response.json()["city"], "Bandung")
        mock_payload.assert_called_with("Bandung")
        self.assertEqual(self.client.session["care_city"], "Bandung")
        self.client.get(reverse("smart_care:weather"))
        mock_payload.assert_called_with("Bandung")  # remembered from the session

    @patch("smart_care.views.weather_payload", return_value={"available": True})
    def test_default_city_is_depok(self, mock_payload):
        self.client.get(reverse("smart_care:weather"))
        mock_payload.assert_called_with("Depok")

    @patch("smart_care.views.weather_payload", return_value={"available": True})
    def test_city_falls_back_to_the_profile_city_when_that_feature_exists(self, mock_payload):
        profile = MagicMock(city="Malang")
        with patch.object(User, "profile", profile, create=True):
            self.client.get(reverse("smart_care:weather"))
        mock_payload.assert_called_with("Malang")

    @patch("smart_care.views.weather_payload", return_value={"available": True})
    def test_city_comes_from_the_users_ecopatch(self, mock_payload):
        make_patch_plant(self.user, patch=make_patch(self.user, city="Bandung"))
        self.client.get(reverse("smart_care:weather"))
        mock_payload.assert_called_with("Bandung")

    @patch("smart_care.views.weather_payload", return_value={"available": True})
    def test_the_city_picked_on_the_page_beats_the_ecopatch_city(self, mock_payload):
        make_patch_plant(self.user, patch=make_patch(self.user, city="Bandung"))
        self.client.get(reverse("smart_care:weather"), {"city": "Malang"})
        mock_payload.assert_called_with("Malang")

    @patch("smart_care.views.weather_payload", return_value={"available": True})
    def test_the_ecopatch_city_beats_the_profile_city(self, mock_payload):
        make_patch_plant(self.user, patch=make_patch(self.user, city="Bandung"))
        with patch.object(User, "profile", MagicMock(city="Medan"), create=True):
            self.client.get(reverse("smart_care:weather"))
        mock_payload.assert_called_with("Bandung")

    @patch("smart_care.views.weather_payload")
    def test_unknown_city_is_rejected(self, mock_payload):
        response = self.client.get(reverse("smart_care:weather"), {"city": "Atlantis"})
        self.assertEqual(response.status_code, 400)
        mock_payload.assert_not_called()

    @patch("smart_care.views.weather_payload", side_effect=WeatherUnavailable("down"))
    def test_weather_failure_is_handled_gracefully(self, _mock):
        response = self.client.get(reverse("smart_care:weather"))
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["available"])

    def test_weather_endpoint_returns_seven_forecast_days(self):
        with patch("smart_care.weather.urlopen", return_value=fake_response(API_RESPONSE)) as mock_urlopen:
            data = self.client.get(reverse("smart_care:weather")).json()
        self.assertEqual(len(data["daily"]), 7)
        self.assertEqual([day["rainy"] for day in data["daily"]], [True, False, False, False, True, False, False])
        self.assertEqual(data["daily"][0]["date"], "2026-10-24")
        self.assertEqual(mock_urlopen.call_count, 1)

    def test_page_renders_without_calling_the_weather_api(self):
        with patch("smart_care.weather.urlopen") as mock_urlopen:
            response = self.client.get(reverse("smart_care:list"))
        self.assertEqual(response.status_code, 200)
        mock_urlopen.assert_not_called()  # the page loads weather from JS, not during render
        self.assertContains(response, "care-retry")


@FAST_HASHER
class SuggestionViewTests(CacheClearingTestCase):
    """Accept / skip / restore and how suggestions show up on the page (real build_suggestions)."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user("alice", password="pass12345")
        self.other = User.objects.create_user("bob", password="pass12345")
        self.client.login(username="alice", password="pass12345")
        # One plant in My EcoPatch with no care recorded yet, so nothing exists today
        self.cabai = make_patch_plant(self.user, "Cabai")
        self.accept = reverse("smart_care:suggestion_accept")
        self.skip = reverse("smart_care:suggestion_skip")
        self.restore = reverse("smart_care:suggestion_restore")
        self.watering = {"plant_name": "Cabai", "task_type": "watering"}

    def todays(self, **filters):
        return CareTask.objects.filter(user=self.user, due_date=timezone.localdate(), **filters)

    def test_suggestions_appear_in_the_list_with_label_and_reason(self):
        response = self.client.get(reverse("smart_care:list"))
        self.assertEqual({s["task_type"] for s in response.context["suggestions"]}, {"watering", "fertilizing", "inspection"})
        self.assertContains(response, "Belum pernah dicatat")
        self.assertContains(response, 'class="care-tag">Saran')
        self.assertContains(response, "care-skip")
        self.assertEqual(self.todays().count(), 0)  # suggestions are not stored

    def test_suggestions_only_exist_for_today(self):
        for offset in (-1, 1, 5):
            day = (timezone.localdate() + timedelta(days=offset)).isoformat()
            response = self.client.get(reverse("smart_care:list"), {"date": day})
            self.assertEqual(response.context["suggestions"], [], offset)

    def test_unaccepted_suggestions_never_become_overdue(self):
        response = self.client.get(reverse("smart_care:list"))
        self.assertEqual(list(response.context["overdue_tasks"]), [])
        self.assertEqual(CareTask.objects.filter(user=self.user, status="pending").count(), 0)

    def test_one_pot_per_plant_on_the_page(self):
        response = self.client.get(reverse("smart_care:list"))
        self.assertEqual([pot["plant_name"] for pot in response.context["pots"]], ["Cabai"])
        self.assertContains(response, 'class="care-pot')
        self.assertContains(response, "Belum dicatat")
        self.assertContains(response, "perkiraan dari jadwal")

    def test_ticking_watering_returns_the_updated_pot(self):
        data = self.client.post(self.accept, self.watering).json()
        self.assertEqual(data["pot"]["water"], 1.0)
        self.assertEqual(data["pot"]["label"], "Baru disiram")
        inspection = self.client.post(self.accept, {"plant_name": "Cabai", "task_type": "inspection"}).json()
        self.assertTrue(inspection["pot"]["inspection_ok"])

    def test_suggestions_count_towards_progress_and_the_strip(self):
        response = self.client.get(reverse("smart_care:list"))
        self.assertEqual(response.context["progress"]["total"], 3)
        today_cell = next(day for day in response.context["strip"] if day["is_today"])
        self.assertEqual(today_cell["pending"], 3)

    def test_accept_creates_a_completed_suggested_task_today(self):
        data = self.client.post(self.accept, self.watering).json()
        task = self.todays().get()
        self.assertEqual((task.status, task.source, task.task_type), ("completed", "suggested", "watering"))
        self.assertIsNotNone(task.completed_at)
        self.assertTrue(task.is_outdoor)
        self.assertEqual((task.patch_plant, task.plant_name), (self.cabai, "Cabai"))
        self.assertTrue(data["created"])
        self.assertEqual(data["id"], task.pk)
        self.assertIn("data-complete-url", data["html"])  # a real task row, so it can be toggled / edited afterwards
        self.assertIn("Saran", data["html"])

    def test_accept_response_has_the_same_shape_as_toggle(self):
        task = make_task(self.user, plant_name="Tomat")
        toggle = self.client.post(reverse("smart_care:complete", args=[task.pk])).json()
        accept = self.client.post(self.accept, self.watering).json()
        self.assertTrue(set(toggle) <= set(accept))
        self.assertEqual(set(toggle["progress"]), set(accept["progress"]))

    def test_accept_updates_progress_with_the_suggestions_in_the_total(self):
        data = self.client.post(self.accept, self.watering).json()
        self.assertEqual(data["progress"]["total"], 3)
        self.assertEqual(data["progress"]["done"], 1)

    def test_accept_is_idempotent(self):
        first = self.client.post(self.accept, self.watering).json()
        second = self.client.post(self.accept, self.watering).json()
        self.assertEqual(self.todays().count(), 1)
        self.assertEqual(first["id"], second["id"])
        self.assertFalse(second["created"])

    def test_skip_creates_a_skipped_suggested_task_and_is_idempotent(self):
        first = self.client.post(self.skip, self.watering).json()
        self.client.post(self.skip, self.watering)
        task = self.todays().get()
        self.assertEqual((task.status, task.source), ("skipped", "suggested"))
        self.assertEqual(first["skipped"]["label"], "Watering")
        self.assertEqual(first["progress"]["total"], 2)  # the skipped one no longer counts

    def test_skip_hides_the_suggestion_but_offers_an_undo(self):
        self.client.post(self.skip, self.watering)
        response = self.client.get(reverse("smart_care:list"))
        self.assertNotIn("watering", {s["task_type"] for s in response.context["suggestions"]})
        self.assertEqual(response.context["progress"]["total"], 2)
        self.assertContains(response, "care-restore")

    def test_skipped_then_accepted_does_not_create_a_second_task(self):
        self.client.post(self.skip, self.watering)
        self.client.post(self.accept, self.watering)
        self.assertEqual(self.todays().count(), 1)
        self.assertEqual(self.todays().get().status, "skipped")

    def test_restore_brings_the_suggestion_back(self):
        self.client.post(self.skip, self.watering)
        self.assertTrue(self.client.post(self.restore, self.watering).json()["restored"])
        self.assertEqual(self.todays().count(), 0)
        response = self.client.get(reverse("smart_care:list"))
        self.assertIn("watering", {s["task_type"] for s in response.context["suggestions"]})
        self.assertFalse(self.client.post(self.restore, self.watering).json()["restored"])  # nothing left to restore

    def test_restore_never_removes_a_completed_or_manual_task(self):
        self.client.post(self.accept, self.watering)
        make_task(self.user, plant_name="Cabai", task_type="inspection")
        self.client.post(self.restore, self.watering)
        self.client.post(self.restore, {"plant_name": "Cabai", "task_type": "inspection"})
        self.assertEqual(self.todays().count(), 2)

    def test_toggling_an_accepted_suggestion_reopens_it(self):
        task_id = self.client.post(self.accept, self.watering).json()["id"]
        data = self.client.post(reverse("smart_care:complete", args=[task_id])).json()
        self.assertEqual(data["status"], "pending")
        self.assertEqual(self.todays().count(), 1)  # still one row, not a fresh suggestion

    def test_completed_task_in_history_delays_the_next_suggestion(self):
        completed_task(self.user, "Cabai", "watering", days_ago=1)
        response = self.client.get(reverse("smart_care:list"))
        self.assertNotIn("watering", {s["task_type"] for s in response.context["suggestions"]})
        completed_task(self.user, "Cabai", "inspection", days_ago=9)
        response = self.client.get(reverse("smart_care:list"))
        reasons = {s["task_type"]: s["reason"] for s in response.context["suggestions"]}
        self.assertEqual(reasons["inspection"], "Terakhir diperiksa 9 hari lalu")

    def test_rejects_unknown_plants_and_types(self):
        for payload in (
            {"plant_name": "Tanaman asing", "task_type": "watering"},
            {"plant_name": "Cabai", "task_type": "pruning"},  # manual only
            {"plant_name": "Cabai", "task_type": "bukan-jenis"},
            {"plant_name": "", "task_type": "watering"},
        ):
            for url in (self.accept, self.skip, self.restore):
                self.assertEqual(self.client.post(url, payload).status_code, 400, (url, payload))
        self.assertEqual(self.todays().count(), 0)

    def test_another_users_plant_cannot_be_used(self):
        make_patch_plant(self.other, "Tomat bob")
        for url in (self.accept, self.skip):
            response = self.client.post(url, {"plant_name": "Tomat bob", "task_type": "watering"})
            self.assertEqual(response.status_code, 400)
        self.assertEqual(CareTask.objects.filter(user=self.other, source="suggested").count(), 0)
        self.assertEqual(self.todays().count(), 0)

    def test_my_suggestion_action_never_touches_another_users_task(self):
        other_task = make_task(self.other, plant_name="Cabai", task_type="watering")
        self.client.post(self.accept, self.watering)
        other_task.refresh_from_db()
        self.assertEqual(other_task.status, CareTask.Status.PENDING)
        self.assertEqual(CareTask.objects.filter(user=self.other).count(), 1)

    def test_endpoints_require_post(self):
        for url in (self.accept, self.skip, self.restore):
            self.assertEqual(self.client.get(url).status_code, 405)

    def test_empty_state_for_a_user_without_plants(self):
        self.client.logout()
        newbie = User.objects.create_user("carol", password="pass12345")
        self.client.force_login(newbie)
        response = self.client.get(reverse("smart_care:list"))
        self.assertContains(response, "Tambahkan tanamanmu di")
        self.assertContains(response, reverse("my_ecopatch:list"))
        self.assertFalse(response.context["has_plants"])
        self.assertContains(response, "Tambah Care Task")

    def test_suggestions_come_from_my_ecopatch_not_from_tasks(self):
        self.client.logout()
        dave = User.objects.create_user("dave", password="pass12345")
        self.client.force_login(dave)
        make_task(dave, plant_name="Cabai")  # a task is not a plant
        make_patch_plant(dave, "Rencana", status="planned")  # not planted yet
        response = self.client.get(reverse("smart_care:list"))
        self.assertEqual(response.context["suggestions"], [])
        self.assertEqual(response.context["pots"], [])
        self.assertFalse(response.context["has_plants"])

    def test_a_plant_leaves_the_suggestions_when_it_is_removed_in_my_ecopatch(self):
        self.assertTrue(self.client.get(reverse("smart_care:list")).context["suggestions"])
        PatchPlant.objects.filter(pk=self.cabai.pk).update(status="removed")
        self.assertEqual(self.client.get(reverse("smart_care:list")).context["suggestions"], [])
        self.assertEqual(self.client.post(self.accept, self.watering).status_code, 400)

    def test_accepting_for_an_indoor_plant_links_it_and_keeps_it_indoor(self):
        make_patch_plant(self.user, "Lidah mertua", patch=make_patch(self.user, "Kamar", "indoor"))
        self.client.post(self.accept, {"plant_name": "Lidah mertua", "task_type": "watering"})
        task = self.todays().get(plant_name="Lidah mertua")
        self.assertFalse(task.is_outdoor)
        self.assertEqual(task.patch_plant.patch.name, "Kamar")

    def test_suggestion_building_never_calls_the_network(self):
        with patch("smart_care.weather.urlopen") as mock_urlopen:
            self.client.get(reverse("smart_care:list"))
            self.client.post(self.accept, self.watering)
        mock_urlopen.assert_not_called()


@FAST_HASHER
class LinkExistingTasksMigrationTests(TestCase):
    """The data migration that links tasks made from a typed name to the plant of My EcoPatch."""

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass12345")
        self.other = User.objects.create_user("bob", password="pass12345")
        self.migration = importlib.import_module("smart_care.migrations.0004_link_existing_tasks")

    def run_migration(self):
        self.migration.link_tasks_to_plants(apps, None)

    def test_a_unique_name_is_linked_ignoring_case_and_spaces(self):
        plant = make_patch_plant(self.user, "Cabai Rawit")
        task = make_task(self.user, plant_name="  cabai   RAWIT ", is_outdoor=False)
        self.run_migration()
        task.refresh_from_db()
        self.assertEqual(task.patch_plant, plant)
        self.assertEqual((task.plant_name, task.is_outdoor), ("  cabai   RAWIT ", False))  # nothing else is touched

    def test_the_name_may_come_from_the_plant_library(self):
        plant = make_patch_plant(self.user, name="", plant=make_library_plant("Basil"))
        task = make_task(self.user, plant_name="Basil")
        self.run_migration()
        task.refresh_from_db()
        self.assertEqual(task.patch_plant, plant)

    def test_two_plants_with_the_same_name_are_ambiguous_and_left_alone(self):
        make_patch_plant(self.user, "Cabai", patch=make_patch(self.user, "Balkon"))
        make_patch_plant(self.user, "cabai", patch=make_patch(self.user, "Kamar"))
        task = make_task(self.user, plant_name="Cabai")
        self.run_migration()
        task.refresh_from_db()
        self.assertIsNone(task.patch_plant)

    def test_no_match_is_left_alone(self):
        make_patch_plant(self.user, "Cabai")
        task = make_task(self.user, plant_name="Tomat")
        self.run_migration()
        task.refresh_from_db()
        self.assertIsNone(task.patch_plant)

    def test_another_users_plant_is_never_used(self):
        make_patch_plant(self.other, "Tomat")
        task = make_task(self.user, plant_name="Tomat")
        self.run_migration()
        task.refresh_from_db()
        self.assertIsNone(task.patch_plant)

    def test_a_task_that_is_already_linked_keeps_its_plant(self):
        first = make_patch_plant(self.user, "Cabai")
        make_patch_plant(self.user, "Tomat")
        task = make_task(self.user, plant_name="Tomat", patch_plant=first)
        self.run_migration()
        task.refresh_from_db()
        self.assertEqual(task.patch_plant, first)

    def test_running_it_twice_changes_nothing_more(self):
        plant = make_patch_plant(self.user, "Cabai")
        task = make_task(self.user, plant_name="Cabai")
        self.run_migration()
        self.run_migration()
        task.refresh_from_db()
        self.assertEqual(task.patch_plant, plant)

    def test_the_migration_can_be_reversed(self):
        operation = self.migration.Migration.operations[0]
        self.assertTrue(operation.reversible)
