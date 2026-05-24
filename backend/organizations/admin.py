from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'fiscal_year_start', 'is_active', 'created_at']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'org', 'role', 'is_staff']
    list_filter = ['role', 'org']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('ESG Profile', {'fields': ('org', 'role')}),
    )
