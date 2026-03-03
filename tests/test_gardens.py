import pytest
from gardens.models import Address, Garden


class TestGardenModel:
    def test_str(self, garden):
        assert str(garden) == "Mon jardin test"

    def test_slug_is_generated(self, garden):
        assert garden.slug is not None
        assert garden.slug == "mon-jardin-test"

    def test_get_absolute_url(self, garden):
        url = garden.get_absolute_url()
        assert garden.slug in url

    def test_get_edit_url(self, garden):
        assert "edit" in garden.get_edit_url()

    def test_get_delete_url(self, garden):
        assert "delete" in garden.get_delete_url()

    def test_has_address_false(self, garden):
        assert garden.has_address() is False

    def test_has_address_true(self, garden, db):
        addr = Address.objects.create(name="Maison")
        garden.address = addr
        garden.save()
        assert garden.has_address() is True

    def test_get_last_update(self, garden):
        result = garden.get_last_update()
        assert isinstance(result, str)


class TestGardenSlugUniqueness:
    def test_unique_slug_for_same_name(self, user):
        g1 = Garden.objects.create(name="Potager", created_by=user)
        g2 = Garden.objects.create(name="Potager", created_by=user)
        assert g1.slug != g2.slug

    def test_slugify_instance_name_no_collision(self, user):
        """Each call produces a unique slug suffix."""
        Garden.objects.create(name="Duplicata", created_by=user)
        # Create some collision entries
        for _ in range(5):
            Garden.objects.create(name="Duplicata", created_by=user)
        slugs = list(
            Garden.objects.filter(name="Duplicata").values_list("slug", flat=True)
        )
        assert len(slugs) == len(set(slugs))


class TestGardenSearch:
    @pytest.fixture(autouse=True)
    def _gardens(self, user):
        Garden.objects.create(name="Potager Nord", created_by=user)
        Garden.objects.create(name="Potager Sud", created_by=user)
        Garden.objects.create(
            name="Verger", description="Pommiers et poiriers", created_by=user
        )

    def test_search_by_name(self):
        assert Garden.objects.search("Potager").count() == 2

    def test_search_by_description(self):
        assert Garden.objects.search("Pommiers").count() == 1

    def test_search_no_match(self):
        assert Garden.objects.search("inexistant").count() == 0

    def test_search_empty_query(self):
        assert Garden.objects.search("").count() == 0


class TestAddress:
    def test_str(self, db):
        addr = Address(name="Bureau")
        assert str(addr) == "Bureau"

    def test_get_not_empty_fields(self, db):
        addr = Address(name="Maison", city="Paris", country="France")
        fields = addr.get_not_empty_fields()
        field_names = [f[0] for f in fields]
        assert "city" in field_names
        assert "country" in field_names
        assert (
            "street" not in field_names
        )  # empty string excluded? Actually "" is falsy


class TestGetCardImageUrl:
    def test_returns_static_map_with_coordinates(self, garden, db):
        addr = Address.objects.create(name="Jardin", latitude=48.8566, longitude=2.3522)
        garden.address = addr
        garden.save()
        url = garden.get_card_image_url()
        assert "staticmap.openstreetmap.de" in url
        assert "48.8566" in url
        assert "2.3522" in url

    def test_returns_default_image_without_address(self, garden):
        assert garden.get_card_image_url() == "/static/img/default-garden.svg"

    def test_returns_default_image_without_coordinates(self, garden, db):
        addr = Address.objects.create(name="Jardin")
        garden.address = addr
        garden.save()
        assert garden.get_card_image_url() == "/static/img/default-garden.svg"
