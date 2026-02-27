from django.contrib import admin

from gardens.models import Address, Garden


@admin.register(Garden)
class GardenAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created_by", "creation"]
    search_fields = ["name", "description"]
    readonly_fields = ["slug", "creation", "updated"]


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "street", "postal_code", "country"]
    readonly_fields = ["latitude", "longitude"]
