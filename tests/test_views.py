import pytest
from django.test import Client
from django.urls import reverse


@pytest.fixture
def auth_client(user):
    client = Client()
    client.force_login(user)
    return client


class TestHomeView:
    def test_home_accessible(self, client):
        resp = client.get(reverse("home"))
        assert resp.status_code == 200

    def test_home_uses_correct_template(self, client):
        resp = client.get(reverse("home"))
        assert "index.html" in [t.name for t in resp.templates]


class TestGardenViews:
    def test_list_requires_login(self, client):
        resp = client.get(reverse("gardens:list"))
        assert resp.status_code == 302  # redirect to login

    def test_list_authenticated(self, auth_client):
        resp = auth_client.get(reverse("gardens:list"))
        assert resp.status_code == 200

    def test_create_garden(self, auth_client):
        resp = auth_client.post(
            reverse("gardens:create"),
            {"name": "Nouveau Potager", "description": "Un beau potager"},
        )
        assert resp.status_code == 302  # redirect on success

    def test_create_garden_with_address(self, auth_client):
        from gardens.models import Garden

        resp = auth_client.post(
            reverse("gardens:create"),
            {
                "name": "Jardin Localisé",
                "description": "Avec adresse",
                "addr-street": "10 rue de la Paix",
                "addr-city": "Paris",
                "addr-postal_code": "75002",
                "addr-country": "France",
            },
        )
        assert resp.status_code == 302
        garden = Garden.objects.get(name="Jardin Localisé")
        assert garden.address is not None
        assert garden.address.city == "Paris"

    def test_create_garden_without_address(self, auth_client):
        from gardens.models import Garden

        resp = auth_client.post(
            reverse("gardens:create"),
            {"name": "Jardin Sans Adresse", "description": "Pas d'adresse"},
        )
        assert resp.status_code == 302
        garden = Garden.objects.get(name="Jardin Sans Adresse")
        assert garden.address is None

    def test_detail_garden(self, auth_client, garden):
        resp = auth_client.get(reverse("gardens:detail", kwargs={"slug": garden.slug}))
        assert resp.status_code == 200

    def test_edit_garden(self, auth_client, garden):
        resp = auth_client.get(reverse("gardens:edit", kwargs={"slug": garden.slug}))
        assert resp.status_code == 200

    def test_edit_garden_add_address(self, auth_client, garden):
        resp = auth_client.post(
            reverse("gardens:edit", kwargs={"slug": garden.slug}),
            {
                "name": garden.name,
                "description": garden.description,
                "addr-street": "5 avenue Foch",
                "addr-city": "Lyon",
                "addr-postal_code": "69001",
                "addr-country": "France",
            },
        )
        assert resp.status_code == 302
        garden.refresh_from_db()
        assert garden.address is not None
        assert garden.address.city == "Lyon"


class TestActivityViews:
    def test_list_requires_login(self, client, garden):
        url = reverse(
            "gardens:activities:index",
            kwargs={"garden_slug": garden.slug},
        )
        resp = client.get(url)
        assert resp.status_code == 302

    def test_list_authenticated(self, auth_client, garden):
        url = reverse(
            "gardens:activities:index",
            kwargs={"garden_slug": garden.slug},
        )
        resp = auth_client.get(url)
        assert resp.status_code == 200

    def test_create_form_loads(self, auth_client, garden):
        url = reverse(
            "gardens:activities:create_activity",
            kwargs={"garden_slug": garden.slug},
        )
        resp = auth_client.get(url)
        assert resp.status_code == 200


class TestAccountViews:
    def test_login_page(self, client):
        resp = client.get(reverse("accounts:login"))
        assert resp.status_code == 200

    def test_register_page(self, client):
        resp = client.get(reverse("accounts:register"))
        assert resp.status_code == 200
