from django.contrib import admin
from weather.models import LawnAssessment, LawnProfile


@admin.register(LawnProfile)
class LawnProfileAdmin(admin.ModelAdmin):
    list_display = ("garden", "grass_type", "goal", "lawn_state", "updated_at")
    list_filter = ("grass_type", "goal", "lawn_state")
    readonly_fields = ("created_at", "updated_at")


@admin.register(LawnAssessment)
class LawnAssessmentAdmin(admin.ModelAdmin):
    list_display = ("lawn_profile", "date", "overall_rating")
    list_filter = ("overall_rating",)
    readonly_fields = ("created_at",)
