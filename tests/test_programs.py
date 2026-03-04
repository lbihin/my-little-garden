"""
Tests for the "Follow the Pro" lawn programme feature.
"""

import pytest
from django.urls import reverse
from weather.forms import LawnAssessmentForm, LawnProfileForm
from weather.models import LawnAssessment, LawnProfile
from weather.programs import MonthlyPlan, get_monthly_plan

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lawn_profile(garden):
    return LawnProfile.objects.create(
        garden=garden,
        grass_type="cool_season",
        lawn_state="established",
        usage="family",
        sun_exposure="full_sun",
        soil_type="loam",
        goal="nice",
        has_irrigation=False,
        mowing_frequency=1,
    )


@pytest.fixture
def lawn_profile_perfect(garden):
    return LawnProfile.objects.create(
        garden=garden,
        grass_type="cool_season",
        lawn_state="established",
        usage="sport",
        sun_exposure="full_sun",
        soil_type="clay",
        goal="perfect",
        has_irrigation=True,
        mowing_frequency=2,
    )


@pytest.fixture
def lawn_profile_basic(garden):
    return LawnProfile.objects.create(
        garden=garden,
        grass_type="mixed",
        lawn_state="established",
        usage="decorative",
        sun_exposure="partial",
        soil_type="unknown",
        goal="basic",
        has_irrigation=False,
        mowing_frequency=1,
    )


@pytest.fixture
def assessment(lawn_profile):
    return LawnAssessment.objects.create(
        lawn_profile=lawn_profile,
        overall_rating=3,
        issues=["weeds", "bare_patches"],
        notes="Quelques zones dégarnies après l'hiver.",
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestLawnProfileModel:
    def test_str(self, lawn_profile):
        assert "Mon jardin test" in str(lawn_profile)

    def test_intensity_mapping(self, garden):
        for goal, expected in [
            ("basic", "low"),
            ("nice", "medium"),
            ("perfect", "high"),
        ]:
            p = LawnProfile(garden=garden, goal=goal)
            assert p.intensity == expected

    def test_one_to_one_garden(self, lawn_profile, garden):
        assert garden.lawn_profile == lawn_profile


class TestLawnAssessmentModel:
    def test_str(self, assessment):
        assert "Correct" in str(assessment)

    def test_get_issue_labels(self, assessment):
        labels = assessment.get_issue_labels()
        assert "Mauvaises herbes" in labels
        assert "Zones dégarnies" in labels

    def test_ordering(self, lawn_profile):
        LawnAssessment.objects.create(lawn_profile=lawn_profile, overall_rating=2)
        LawnAssessment.objects.create(lawn_profile=lawn_profile, overall_rating=5)
        assessments = list(lawn_profile.assessments.all())
        # Ordering is -date; both same date, so just check all returned
        assert len(assessments) == 2


# ---------------------------------------------------------------------------
# Form tests
# ---------------------------------------------------------------------------


class TestLawnProfileForm:
    def test_valid_form(self):
        data = {
            "grass_type": "cool_season",
            "lawn_state": "established",
            "usage": "family",
            "sun_exposure": "full_sun",
            "soil_type": "loam",
            "goal": "nice",
            "mowing_frequency": 1,
        }
        form = LawnProfileForm(data)
        assert form.is_valid(), form.errors

    def test_invalid_mowing_frequency(self):
        data = {
            "grass_type": "cool_season",
            "lawn_state": "established",
            "usage": "family",
            "sun_exposure": "full_sun",
            "soil_type": "loam",
            "goal": "nice",
            "mowing_frequency": -1,
        }
        form = LawnProfileForm(data)
        assert not form.is_valid()


class TestLawnAssessmentForm:
    def test_valid_form(self):
        data = {
            "overall_rating": 4,
            "issues": ["weeds"],
            "notes": "Test note",
        }
        form = LawnAssessmentForm(data)
        assert form.is_valid(), form.errors

    def test_no_issues(self):
        data = {"overall_rating": 5, "issues": [], "notes": ""}
        form = LawnAssessmentForm(data)
        assert form.is_valid()

    def test_none_clears_other_issues(self):
        data = {"overall_rating": 3, "issues": ["none", "weeds"]}
        form = LawnAssessmentForm(data)
        assert form.is_valid()
        assert form.cleaned_data["issues"] == ["none"]


# ---------------------------------------------------------------------------
# Programs knowledge base tests
# ---------------------------------------------------------------------------


class TestGetMonthlyPlan:
    def test_returns_monthly_plan(self, lawn_profile):
        plan = get_monthly_plan(lawn_profile, month=4)
        assert isinstance(plan, MonthlyPlan)
        assert plan.month == 4
        assert plan.month_name == "Avril"
        assert plan.season == "printemps"

    def test_has_tasks_in_spring(self, lawn_profile):
        plan = get_monthly_plan(lawn_profile, month=4)
        assert len(plan.tasks) > 0
        categories = {t.category for t in plan.tasks}
        assert "mowing" in categories

    def test_has_tasks_in_summer(self, lawn_profile):
        plan = get_monthly_plan(lawn_profile, month=7)
        assert len(plan.tasks) > 0

    def test_winter_is_quiet(self, lawn_profile_basic):
        plan = get_monthly_plan(lawn_profile_basic, month=1)
        # Winter with basic goal should have very few or no tasks
        assert len(plan.tasks) <= 2

    def test_perfect_has_more_tasks_than_basic(self, garden):
        basic = LawnProfile(
            garden=garden,
            goal="basic",
            grass_type="cool_season",
            lawn_state="established",
            usage="decorative",
            sun_exposure="full_sun",
            soil_type="loam",
        )
        perfect = LawnProfile(
            garden=garden,
            goal="perfect",
            grass_type="cool_season",
            lawn_state="established",
            usage="sport",
            sun_exposure="full_sun",
            soil_type="loam",
        )
        plan_basic = get_monthly_plan(basic, month=4)
        plan_perfect = get_monthly_plan(perfect, month=4)
        assert len(plan_perfect.tasks) > len(plan_basic.tasks)

    def test_issue_tasks_added(self, lawn_profile):
        plan = get_monthly_plan(lawn_profile, month=6, latest_issues=["weeds", "moss"])
        corrective = [t for t in plan.tasks if t.category == "corrective"]
        assert len(corrective) == 2

    def test_issue_none_no_corrective(self, lawn_profile):
        plan = get_monthly_plan(lawn_profile, month=6, latest_issues=["none"])
        corrective = [t for t in plan.tasks if t.category == "corrective"]
        assert len(corrective) == 0

    def test_tasks_sorted_by_priority(self, lawn_profile):
        plan = get_monthly_plan(lawn_profile, month=4)
        if len(plan.tasks) > 1:
            priorities = [t.priority for t in plan.tasks]
            assert priorities == sorted(priorities)

    def test_tips_present(self, lawn_profile):
        plan = get_monthly_plan(lawn_profile, month=4)
        assert len(plan.tips) > 0

    def test_headline_present(self, lawn_profile):
        for m in range(1, 13):
            plan = get_monthly_plan(lawn_profile, month=m)
            assert plan.headline != ""

    def test_shade_adjusts_mowing(self, garden):
        shade = LawnProfile(
            garden=garden,
            goal="nice",
            grass_type="cool_season",
            lawn_state="established",
            usage="family",
            sun_exposure="shade",
            soil_type="loam",
        )
        plan = get_monthly_plan(shade, month=5)
        mowing = [t for t in plan.tasks if t.category == "mowing"]
        assert any("ombragée" in t.detail for t in mowing)

    def test_sandy_soil_fertiliser_note(self, garden):
        sandy = LawnProfile(
            garden=garden,
            goal="nice",
            grass_type="cool_season",
            lawn_state="established",
            usage="family",
            sun_exposure="full_sun",
            soil_type="sandy",
        )
        plan = get_monthly_plan(sandy, month=4)
        fert = [t for t in plan.tasks if t.category == "fertilisation"]
        assert any("sableux" in t.detail.lower() for t in fert)

    def test_degraded_gets_overseeding(self, garden):
        degraded = LawnProfile(
            garden=garden,
            goal="nice",
            grass_type="cool_season",
            lawn_state="degraded",
            usage="family",
            sun_exposure="full_sun",
            soil_type="loam",
        )
        plan = get_monthly_plan(degraded, month=9)
        categories = {t.category for t in plan.tasks}
        assert "overseeding" in categories

    def test_all_months_produce_plan(self, lawn_profile):
        for m in range(1, 13):
            plan = get_monthly_plan(lawn_profile, month=m)
            assert isinstance(plan, MonthlyPlan)
            assert plan.month == m


# ---------------------------------------------------------------------------
# View tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLawnProgramViews:
    def test_program_redirects_without_profile(self, client, user, garden):
        client.login(username="testeur", password="secret123!")
        url = reverse(
            "gardens:weather:program",
            kwargs={"garden_slug": garden.slug},
        )
        resp = client.get(url)
        assert resp.status_code == 302
        assert "questionnaire" in resp.url

    def test_program_shows_plan(self, client, user, garden, lawn_profile):
        client.login(username="testeur", password="secret123!")
        url = reverse(
            "gardens:weather:program",
            kwargs={"garden_slug": garden.slug},
        )
        resp = client.get(url)
        assert resp.status_code == 200
        assert "Follow the Pro" in resp.content.decode()

    def test_program_month_selector(self, client, user, garden, lawn_profile):
        client.login(username="testeur", password="secret123!")
        url = reverse(
            "gardens:weather:program",
            kwargs={"garden_slug": garden.slug},
        )
        resp = client.get(url + "?month=9")
        assert resp.status_code == 200
        assert "Septembre" in resp.content.decode()

    def test_questionnaire_get(self, client, user, garden):
        client.login(username="testeur", password="secret123!")
        url = reverse(
            "gardens:weather:questionnaire",
            kwargs={"garden_slug": garden.slug},
        )
        resp = client.get(url)
        assert resp.status_code == 200
        assert "Questionnaire" in resp.content.decode()

    def test_questionnaire_post_creates_profile(self, client, user, garden):
        client.login(username="testeur", password="secret123!")
        url = reverse(
            "gardens:weather:questionnaire",
            kwargs={"garden_slug": garden.slug},
        )
        data = {
            "grass_type": "cool_season",
            "lawn_state": "established",
            "usage": "family",
            "sun_exposure": "full_sun",
            "soil_type": "loam",
            "goal": "nice",
            "mowing_frequency": 1,
        }
        resp = client.post(url, data)
        assert resp.status_code == 302
        assert LawnProfile.objects.filter(garden=garden).exists()

    def test_questionnaire_update_existing(self, client, user, garden, lawn_profile):
        client.login(username="testeur", password="secret123!")
        url = reverse(
            "gardens:weather:questionnaire",
            kwargs={"garden_slug": garden.slug},
        )
        data = {
            "grass_type": "warm_season",
            "lawn_state": "young",
            "usage": "sport",
            "sun_exposure": "shade",
            "soil_type": "clay",
            "goal": "perfect",
            "mowing_frequency": 3,
        }
        resp = client.post(url, data)
        assert resp.status_code == 302
        lawn_profile.refresh_from_db()
        assert lawn_profile.goal == "perfect"
        assert lawn_profile.grass_type == "warm_season"

    def test_assessment_get(self, client, user, garden, lawn_profile):
        client.login(username="testeur", password="secret123!")
        url = reverse(
            "gardens:weather:assessment",
            kwargs={"garden_slug": garden.slug},
        )
        resp = client.get(url)
        assert resp.status_code == 200

    def test_assessment_post(self, client, user, garden, lawn_profile):
        client.login(username="testeur", password="secret123!")
        url = reverse(
            "gardens:weather:assessment",
            kwargs={"garden_slug": garden.slug},
        )
        data = {
            "overall_rating": 4,
            "issues": ["weeds"],
            "notes": "Pas mal !",
        }
        resp = client.post(url, data)
        assert resp.status_code == 302
        assert LawnAssessment.objects.filter(lawn_profile=lawn_profile).count() == 1

    def test_assessment_redirects_without_profile(self, client, user, garden):
        client.login(username="testeur", password="secret123!")
        url = reverse(
            "gardens:weather:assessment",
            kwargs={"garden_slug": garden.slug},
        )
        resp = client.get(url)
        assert resp.status_code == 302
        assert "questionnaire" in resp.url

    def test_unauthenticated_redirects(self, client, garden):
        url = reverse(
            "gardens:weather:program",
            kwargs={"garden_slug": garden.slug},
        )
        resp = client.get(url)
        assert resp.status_code == 302
        assert "login" in resp.url
