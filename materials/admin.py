# This file is covered by the BSD license. See LICENSE in the root directory.
import nested_admin

from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportModelAdmin

from . import models
from mainproject.settings import MATD3_NAME

admin.site.site_header = mark_safe(f'{MATD3_NAME} database')


class BaseMixin:
    readonly_fields = ('created_by', 'created', 'updated_by', 'updated')

    def check_perm(self, user, obj=None):
        return user.is_superuser or obj and (
            not hasattr(obj, 'created_by') or obj.created_by == user)

    def has_change_permission(self, request, obj=None):
        return self.check_perm(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        return self.check_perm(request.user, obj)


class BaseAdmin(BaseMixin, nested_admin.NestedModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        self.qs = qs
        return qs

    def row_id(self, obj):
        return len(self.qs) - list(self.qs).index(obj)

    def get_list_display(self, request):
        ld = list(super().get_list_display(request))
        return ['row_id'] + ld

    def save_model(self, request, obj, form, change):
        if not hasattr(obj, 'created_by'):
            obj.created_by = request.user
        obj.updated_by = request.user
        obj.updated = timezone.now()
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for instance in instances:
            if not hasattr(instance, 'created_by'):
                instance.created_by = request.user
            instance.updated_by = request.user
            instance.updated = timezone.now()
            instance.save()
        formset.save_m2m()


@admin.register(models.Compound)
class CompoundAdmin(BaseAdmin):
    pass


@admin.register(models.Property)
class PropertyAdmin(BaseAdmin):
    pass


@admin.register(models.Unit)
class UnitAdmin(BaseAdmin):
    pass


# Include authors in reference admin site
class AuthorInline(nested_admin.NestedTabularInline):
    model = models.Author.references.through
    extra = 0


@admin.register(models.Reference)
class ReferenceAdmin(BaseAdmin):
    readonly_fields = ()
    inlines = [AuthorInline,]


@admin.register(models.Author)
class AuthorAdmin(BaseAdmin):
    readonly_fields = ()
    filter_horizontal = ('references',)


@admin.register(models.Dataset)
class DatasetAdmin(BaseAdmin):
    list_display = ('compound', 'primary_property', 'created_by', 'updated_by', 'updated')
    list_filter = ('updated',)


# Include comments in synthesis, experimental, computational admin sites
class CommentInline(BaseMixin, nested_admin.NestedStackedInline):
    model = models.Comment
    verbose_name_plural = ''
    fields = ['text']

@admin.register(models.SynthesisMethod)
class SynthesisAdmin(BaseAdmin):
    list_display = ['dataset', 'created_by', 'created']
    inlines = [CommentInline,]

@admin.register(models.ExperimentalDetails)
class ExperimentalAdmin(BaseAdmin):
    list_display = ['dataset', 'created_by', 'created']
    inlines = [CommentInline,]

@admin.register(models.ComputationalDetails)
class ComputationalAdmin(BaseAdmin):
    list_display = ['dataset', 'created_by', 'created']
    inlines = [CommentInline,]


# Include data in subset admin site
class FilesInline(BaseMixin, nested_admin.NestedStackedInline):
    model = models.AdditionalFile
    extra = 0

# Normal properties
class DatapointInline(BaseMixin, nested_admin.NestedStackedInline):
    model = models.Datapoint
    fields = ['x_value', 'y_value']
    extra = 0

class ChartInline(BaseMixin, nested_admin.NestedStackedInline):
    model = models.Chart
    fields = ['x_title', 'x_unit', 'y_title', 'y_unit', 'legend']
    extra = 0
    inlines = [DatapointInline]

class FixedInline(BaseMixin, nested_admin.NestedStackedInline):
    model = models.FixedPropertyValue
    exclude = ['created_by', 'created', 'updated_by', 'updated']
    extra = 0

# Atomic structure
class LatticeConstInline(BaseMixin, nested_admin.NestedStackedInline):
    model = models.LatticeConstant
    exclude = ['created_by', 'created', 'updated_by', 'updated']
    extra = 0

class AtomicCoordInline(BaseMixin, nested_admin.NestedStackedInline):
    model = models.AtomicCoordinate
    exclude = ['created_by', 'created', 'updated_by', 'updated']
    extra = 0 

# Tolerance factor
class ShannonIonicRadiiInline(BaseMixin, nested_admin.NestedStackedInline):
    model = models.ShannonIonicRadii
    exclude = ['compound', 'created_by', 'created', 'updated_by', 'updated']
    extra = 0

class BondLengthInline(BaseMixin, nested_admin.NestedTabularInline):
    model = models.BondLength
    fields = ['r_label', 'bond_id', 'experimental_r', 'averaged_r', 'shannon_r', 'counter']
    extra = 0

class ToleranceFactorInline(BaseMixin, nested_admin.NestedTabularInline):
    model = models.ToleranceFactor
    exclude = ['compound', 'created_by', 'created', 'updated_by', 'updated']
    extra = 0

@admin.register(models.Subset)
class SubsetAdmin(BaseAdmin):
    list_display = ('dataset', 'title', 'created_by', 'updated_by', 'updated')
    inlines = [FilesInline, ChartInline, FixedInline, LatticeConstInline, AtomicCoordInline,
            ShannonIonicRadiiInline, BondLengthInline, ToleranceFactorInline]


@admin.register(models.ShannonRadiiTable)
class ShannonRadiiTableAdmin(ImportExportModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        self.qs = qs
        return qs

    def row_id(self, obj):
        return len(self.qs) - list(self.qs).index(obj)
        
    list_display = ('row_id', 'element', 'charge', 'coordination', 'spin_state', 'ionic_radius')


@admin.register(models.ShannonIonicRadii)
class ShannonIonicRadiiAdmin(BaseAdmin):
    pass

    
@admin.register(models.BondLength)
class BondLengthAdmin(BaseAdmin):
    pass


@admin.register(models.ToleranceFactor)
class ToleranceFactor(BaseAdmin):
    pass
