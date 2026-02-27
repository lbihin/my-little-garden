from django.contrib import admin

from plants.models import Plant, PlantTask


class PlantTaskInline(admin.TabularInline):
    model = PlantTask
    extra = 0


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ("common_name", "scientific_name", "garden", "created_at")
    list_filter = ("garden",)
    search_fields = ("common_name", "scientific_name")
    inlines = [PlantTaskInline]


@admin.register(PlantTask)
class PlantTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "plant", "priority", "done", "due_date")
    list_filter = ("done", "priority")
