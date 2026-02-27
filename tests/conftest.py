import pytest
from django.contrib.auth.models import User

from activities.models import Fertilizer, FertilizationTask, Activity
from gardens.models import Garden


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testeur", password="secret123!")


@pytest.fixture
def garden(user):
    return Garden.objects.create(
        name="Mon jardin test",
        description="Un jardin pour les tests",
        created_by=user,
    )


@pytest.fixture
def fertilizer(db):
    return Fertilizer.objects.create(
        name="NPK Universel",
        company="TestCo",
        organic=True,
        n_rate=10.0,
        p_rate=10.0,
        k_rate=10.0,
    )


@pytest.fixture
def fertilization_task(fertilizer):
    return FertilizationTask.objects.create(
        quantity_as_float=5.0,
        unit="kg",
        fertilizer=fertilizer,
    )


@pytest.fixture
def activity(garden, fertilization_task):
    from django.utils import timezone

    return Activity.objects.create(
        creation=timezone.now(),
        comment="Première fertilisation",
        garden=garden,
        task=fertilization_task,
    )
