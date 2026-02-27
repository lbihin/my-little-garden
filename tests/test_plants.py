import pytest
from django.utils import timezone
from plants.models import Plant, PlantTask


@pytest.fixture
def plant(garden):
    return Plant.objects.create(
        garden=garden,
        common_name="Lavande",
        scientific_name="Lavandula angustifolia",
    )


@pytest.fixture
def plant_task(plant):
    return PlantTask.objects.create(
        plant=plant,
        title="Tailler après floraison",
        priority=2,
    )


# ── Model tests ──────────────────────────────────────────────


class TestPlantModel:
    def test_str_with_scientific(self, plant):
        assert str(plant) == "Lavande (Lavandula angustifolia)"

    def test_str_without_scientific(self, garden):
        p = Plant.objects.create(garden=garden, common_name="Rosier")
        assert str(p) == "Rosier"

    def test_slug_generated(self, plant):
        assert plant.slug == "lavande"

    def test_slug_unique(self, garden):
        p1 = Plant.objects.create(garden=garden, common_name="Basilic")
        p2 = Plant.objects.create(garden=garden, common_name="Basilic")
        assert p1.slug != p2.slug

    def test_get_absolute_url(self, plant):
        url = plant.get_absolute_url()
        assert plant.slug in url
        assert plant.garden.slug in url

    def test_pending_tasks_count(self, plant):
        assert plant.pending_tasks_count() == 0
        PlantTask.objects.create(plant=plant, title="Task 1")
        assert plant.pending_tasks_count() == 1
        PlantTask.objects.create(plant=plant, title="Task 2", done=True)
        assert plant.pending_tasks_count() == 1

    def test_search(self, plant):
        qs = Plant.objects.search("lavande")
        assert plant in qs

    def test_search_scientific(self, plant):
        qs = Plant.objects.search("angustifolia")
        assert plant in qs

    def test_search_empty(self):
        qs = Plant.objects.search("")
        assert qs.count() == 0


class TestPlantTaskModel:
    def test_str(self, plant_task):
        assert str(plant_task) == "Tailler après floraison"

    def test_toggle_done(self, plant_task):
        assert plant_task.done is False
        plant_task.done = True
        plant_task.completed_at = timezone.now()
        plant_task.save()
        plant_task.refresh_from_db()
        assert plant_task.done is True
        assert plant_task.completed_at is not None

    def test_priority_choices(self, plant_task):
        assert plant_task.priority == 2
        plant_task.priority = 3
        plant_task.save()
        plant_task.refresh_from_db()
        assert plant_task.priority == 3

    def test_ordering(self, plant):
        t1 = PlantTask.objects.create(plant=plant, title="Low", priority=1)
        t2 = PlantTask.objects.create(plant=plant, title="High", priority=3)
        t3 = PlantTask.objects.create(plant=plant, title="Done", priority=3, done=True)
        tasks = list(plant.tasks.all())
        # done=False first, then by priority desc
        assert tasks[0] == t2
        assert tasks[1] == t1
        assert tasks[2] == t3


# ── View tests ───────────────────────────────────────────────


@pytest.mark.django_db
class TestPlantViews:
    def test_plant_list_requires_login(self, client, garden):
        resp = client.get(f"/gardens/{garden.slug}/plants/")
        assert resp.status_code == 302

    def test_plant_list_authenticated(self, client, garden, user):
        client.login(username="testeur", password="secret123!")
        resp = client.get(f"/gardens/{garden.slug}/plants/")
        assert resp.status_code == 200

    def test_plant_create(self, client, garden, user):
        client.login(username="testeur", password="secret123!")
        resp = client.post(
            f"/gardens/{garden.slug}/plants/add/",
            {"common_name": "Menthe", "scientific_name": "", "notes": ""},
        )
        assert resp.status_code == 302
        assert Plant.objects.filter(common_name="Menthe").exists()

    def test_plant_detail(self, client, garden, plant, user):
        client.login(username="testeur", password="secret123!")
        resp = client.get(plant.get_absolute_url())
        assert resp.status_code == 200
        assert "Lavande" in resp.content.decode()

    def test_plant_delete(self, client, garden, plant, user):
        client.login(username="testeur", password="secret123!")
        resp = client.post(
            f"/gardens/{garden.slug}/plants/{plant.slug}/delete/"
        )
        assert resp.status_code == 302
        assert not Plant.objects.filter(pk=plant.pk).exists()


@pytest.mark.django_db
class TestPlantTaskViews:
    def test_task_create_htmx(self, client, garden, plant, user):
        client.login(username="testeur", password="secret123!")
        resp = client.post(
            f"/gardens/{garden.slug}/plants/{plant.slug}/tasks/add/",
            {"title": "Arroser", "priority": 3},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        assert PlantTask.objects.filter(title="Arroser").exists()

    def test_task_toggle(self, client, garden, plant, plant_task, user):
        client.login(username="testeur", password="secret123!")
        resp = client.post(
            f"/gardens/{garden.slug}/plants/tasks/{plant_task.pk}/toggle/",
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        plant_task.refresh_from_db()
        assert plant_task.done is True

    def test_task_delete(self, client, garden, plant, plant_task, user):
        client.login(username="testeur", password="secret123!")
        resp = client.post(
            f"/gardens/{garden.slug}/plants/tasks/{plant_task.pk}/delete/",
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        assert not PlantTask.objects.filter(pk=plant_task.pk).exists()
