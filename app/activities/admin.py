from django.contrib import admin

from activities.models import FertilizationTask, Activity, Fertilizer


# Register your models here.

@admin.register(Fertilizer)
class FertilizerAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'organic', 'n_rate', 'p_rate', 'k_rate')


@admin.register(FertilizationTask)
class FertilizationAdmin(admin.ModelAdmin):
    list_display = ('quantity_as_float',)
    search_fields = ('quantity_as_float',)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('creation', 'garden', 'fertilization')
    # search_fields = ('activity',)
    readonly_fields = ('updated',)
