# This file is covered by the BSD license. See LICENSE in the root directory.
from functools import reduce
import io
import json
import logging
import operator
import os
import re
import requests
import zipfile
import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.uploadedfile import UploadedFile
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import BooleanField
from django.db.models import Case
from django.db.models import Q
from django.db.models import Value
from django.db.models import When
from django.db.models import Avg
from django.db.models import Max
from django.db.models.fields import TextField, FloatField
from django.forms import ModelChoiceField
from django.forms.models import model_to_dict
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.shortcuts import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views import generic
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


from . import forms
from . import models
from . import permissions
from . import qresp
from . import serializers
from . import utils

logger = logging.getLogger(__name__)

def dataset_author_check(view):
    """Test whether the logged on user is the creator of the data set."""
    @login_required
    def wrap(request, *args, **kwargs):
        dataset = get_object_or_404(models.Dataset, pk=kwargs['dataset_pk'])
        if dataset.created_by == request.user:
            return view(request, *args, **kwargs)
        else:
            logger.warning(f'Data set was created by {dataset.created_by} but '
                           'an attempt was made to delete it by '
                           f'{request.user}',
                           extra={'request': request})
            return HttpResponseForbidden()
    wrap.__doc__ = view.__doc__
    wrap.__name__ = view.__name__
    return wrap


def staff_status_required(view):
    @login_required
    def wrap(request, *args, **kwargs):
        if request.user.is_staff:
            return view(request, *args, **kwargs)
        else:
            logger.warning(f'{request.user.username} is trying to submit data '
                           'but does not have staff status.',
                           extra={'request': request})
            return HttpResponseForbidden()
    wrap.__doc__ = view.__doc__
    wrap.__name__ = view.__name__
    return wrap


class StaffStatusMixin(LoginRequiredMixin):
    """Verify that the current user is at least staff."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


# class ReferenceDetailView(generic.DetailView):
#     model = models.Reference
    

class SearchFormView(generic.TemplateView):
    """Search for system page."""
    template_name = 'materials/search.html'
    search_terms = [
        ['formula', 'Formula'],
        ['primary_property', 'Primary property'],
        ['author', 'Author'],
    ]

    def get(self, request):
        # material_ids = models.System.objects.all().values_list(
        #     'pk', 'compound_name')
        # dataset_ids = models.Dataset.objects.all().values_list(
        #     'pk', 'system__compound_name', 'primary_property__name')
        return render(request, self.template_name, {
            'search_terms': self.search_terms,
            # 'material_ids': material_ids,
            # 'dataset_ids': dataset_ids,
        })

    def post(self, request):
        template_name = 'materials/search_results.html'
        form = forms.SearchForm(request.POST)
        search_text = ''
        # default search_term
        search_term = 'formula'
        if form.is_valid():
            search_text = form.cleaned_data['search_text']
            search_term = request.POST.get('search_term')
            systems_info = []
            if search_term == 'formula':
                compounds = models.Compound.objects.filter(
                    formula__icontains=search_text).exclude(
                    datasets__isnull=True).order_by(
                        'formula')
            elif search_term == 'primary_property':
                compounds = models.Compound.objects.filter(
                    datasets__primary_property__name__icontains=search_text).exclude(
                    datasets__isnull=True).order_by(
                    'formula')
            elif search_term == 'author':
                keywords = search_text.split()
                query = reduce(operator.or_, (
                    Q(datasets__subsets__reference__authors__last_name__icontains=x) for
                    x in keywords))
                compounds = models.Compound.objects.filter(query).exclude(
                    datasets__isnull=True).distinct()
            else:
                raise KeyError('Invalid search term.')
            compounds_map = []
            for compound in compounds:
                primary_properties = models.Property.objects.filter(
                    datasets__compound__formula=compound.formula).values_list('name', flat=True).distinct()
                authors = ""
                for reference in models.Reference.objects.filter(
                    subsets__dataset__compound__formula=compound.formula):
                    authors += reference.getAuthorsAsString()
                compounds_map.append([compound, primary_properties, authors])
        args = {
            'compounds_map': compounds_map,
            'search_term': search_term,
        }
        return render(request, template_name, args)


class CompoundView(generic.ListView):
    template_name = 'materials/compound.html'
    context_object_name = 'dataset_list'

    def get_queryset(self, **kwargs):
        conditions = models.Dataset.objects.filter(
            compound__pk=self.kwargs['pk']).values(
            'primary_property').annotate(
            last_updated=Max('updated'))
        dataset_list = []
        for c in conditions:
            dataset = models.Dataset.objects.filter(
                compound__pk=self.kwargs['pk'],
                primary_property__pk=c['primary_property'],
                updated=c['last_updated'])[0]
            dataset_list.append(dataset)
        return dataset_list


def dataset_versions(request, compound_pk=None, property_pk=None):
    obj_list = list(models.Dataset.objects.filter(
        compound__pk=compound_pk, primary_property__pk=property_pk).values('pk', 'updated', 'updated_by__username'))
    response = {'data': obj_list}
    return JsonResponse(response)


def dataset_details(request, pk=None):
    obj = get_object_or_404(models.Dataset, pk=pk)
    response = {
        'general': {},
        'synthesis': {},
        'experimental': {},
        'computational': {},
        'data': [],
    }
    # general info
    response['general']['Origin'] = 'experimental' if obj.is_experimental else 'theoretical'
    response['general']['Sample type'] = models.Dataset.SAMPLE_TYPES[obj.sample_type][1]
    response['general']['Crystal system'] = models.Dataset.CRYSTAL_SYSTEMS[obj.crystal_system][1]
    response['general']['Space group'] = obj.space_group.name

    # synthesis method
    if obj.synthesis.exists():
        synthesis = response['synthesis']
        synthesis['Starting materials'] = obj.synthesis.first().starting_materials
        synthesis['Product'] = obj.synthesis.first().product
        synthesis['Description'] = obj.synthesis.first().description
        synthesis['Comment'] = obj.synthesis.first().comment.text if hasattr(obj.synthesis.first(), 'comment') else ''

    # experimental details
    if obj.experimental.exists():
        experimental = response['experimental']
        experimental['Method'] = obj.experimental.first().method
        experimental['Description'] = obj.experimental.first().description
        experimental['Comment'] = obj.experimental.first().comment.text if hasattr(obj.experimental.first(), 'comment') else ''

    # computational details
    if obj.computational.exists():
        computational = response['computational']
        computational['Code'] = obj.computational.first().code
        computational['Level of theory'] = obj.computational.first().level_of_theory
        computational['Exchange-correlation functional'] = obj.computational.first().xc_functional
        computational['K-point grid'] = obj.computational.first().k_point_grid
        computational['Level of relativity'] = obj.computational.first().level_of_relativity
        computational['Basis set definition'] = obj.computational.first().basis_set_definition
        computational['Numerical accuracy'] = obj.computational.first().numerical_accuracy
        if obj.computational.first().repositories.exists():
            computational['External repositories'] = [x.url for x in obj.computational.first().repositories.all()]
        computational['Comment'] = obj.computational.first().comment.text if hasattr(obj.computational.first(), 'comment') else ''

    # subset data
    if obj.subsets.exists():
        data = response['data']
        for s in obj.subsets.all():
            subset = {
                'pk': s.pk,
                'primary property': s.dataset.primary_property.name,
                'title': s.title,
                'reference': model_to_dict(s.reference) if s.reference else {},
                'authors': list(s.reference.authors.values()) if s.reference and s.reference.authors else [],
                'additional files': [],
            }
            for x in s.get_additional_files_path():
                ext = os.path.splitext(x)
                subset['additional files'].append({
                    'path': x,
                    'name': x.split('/')[-1],
                    'extension': ext,
                })
            if s.dataset.primary_property.name == 'atomic structure':
                subset['lattice constants'] = []
                subset['atomic coordinates'] = []
                if s.lattice_constants.first():
                    for x in s.get_lattice_constants():
                        subset['lattice constants'].append({
                            'symbol': x[0],
                            'value': x[1],
                            'unit': x[2],
                        })
                if s.atomic_coordinates.first():
                    subset['atomic coordinates'] = s.get_atomic_coordinates()
            elif s.dataset.primary_property.name == 'tolerance factor related parameters':
                subset['bond lengths'] = []
                if s.bond_length.first():
                    subset['bond lengths'] = s.get_bond_lengths()
                subset['tolerance factors'] = []
                if s.tolerance_factors.first():
                    subset['tolerance factors'] = s.get_tolerance_factors()
            else:
                if s.fixed_values.first():
                    subset['fixed properties'] = s.get_fixed_properties()  
            data.append(subset)         

    return JsonResponse(response)


def get_jsmol_input(request, pk):
    """Return a statement to be executed by JSmol."""
    subset = models.Subset.objects.get(pk=pk)
    if not subset:
        return HttpResponse()
    if subset.input_data_file:
        subsets = subset.dataset.subsets.all()
        subsets_with_file = []
        for s in subsets:
            if s.input_data_file:
                subsets_with_file.append(s)
        if subset.input_data_file.path == subsets_with_file[0].input_data_file.path:
            filename = os.path.basename(
                subset.input_data_file.path)
            return HttpResponse(
                f'load /media/data_files/dataset_{subset.dataset.pk}/{filename} '
                '{1 1 1}')
    return HttpResponse()


def data_for_chart(request, pk):
    subset = models.Subset.objects.get(pk=pk)
    if subset.curves.first():
        obj = subset.curves.first()
        response = {'x title': obj.x_title,
                    'x unit': obj.x_unit,
                    'y title': obj.y_title,
                    'y unit': obj.y_unit,
                    'data': []}
    for curve in subset.curves.all():
        if curve.datapoints.exists():
            data = {
                'legend': curve.legend,
                'values': []
            }
            for value in curve.datapoints.all():
                data['values'].append({
                    'x': value.x_value,
                    'y': value.y_value,
                })
            response['data'].append(data)
    return JsonResponse(response)


class AddDataView(StaffStatusMixin, generic.TemplateView):
    """View for adding new data."""
    template_name = 'materials/add_data.html'

    def get(self, request, *args, **kwargs):
        main_form = forms.AddDataForm()
        if request.GET.get('return-url'):
            return_url = request.META['HTTP_REFERER'].replace('/qrespcurator',
                                                              '')
            return_url = return_url + request.GET.get('return-url')
            base_template = 'mainproject/base.html'
            main_form.fields['return_url'].initial = return_url
        else:
            base_template = 'materials/base.html'
        if request.GET.get('qresp-server-url'):
            qresp_paper_id = request.GET.get('qresp-paper-id')
            qresp_fetch_url = request.GET.get("qresp-server-url")
            qresp_fetch_url += f'/api/paper/{qresp_paper_id}'
            qresp_chart_nr = int(request.GET.get('qresp-chart-nr'))
            paper_detail = requests.get(qresp_fetch_url, verify=False).json()
            main_form.fields['qresp_fetch_url'].initial = qresp_fetch_url
            main_form.fields['qresp_chart_nr'].initial = qresp_chart_nr
            main_form.fields['caption'].initial = (
                paper_detail['charts'][qresp_chart_nr]['caption'])
        if request.GET.get('qresp-search-url'):
            qresp_search_url = request.GET.get('qresp-search-url')
            main_form.fields['qresp_search_url'].initial = qresp_search_url
        return render(request, self.template_name, {
            'main_form': main_form,
            'reference_form': forms.AddReferenceForm(),
            'property_form': forms.AddPropertyForm(),
            'unit_form': forms.AddUnitForm(),
            'space_group_form': forms.AddSpaceGroupForm(),
            'base_template': base_template,
        })


class UpdateDatasetView(StaffStatusMixin, generic.TemplateView):
    """View for editing data of a dataset."""
    template_name = 'materials/update_dataset.html'

    def get(self, request, *args, **kwargs):
        main_form = forms.AddDataForm()
        base_template = 'materials/base.html'
        dataset_pk = self.kwargs['pk']
        dataset = get_object_or_404(models.Dataset, pk=dataset_pk)
        formula = dataset.compound.formula
        primary_property = dataset.primary_property.name

        # Prefill the form with current instance data
        # General
        main_form.fields['formula'].initial = formula
        main_form.fields['primary_property'].initial = dataset.primary_property.pk
        main_form.fields['origin_of_data'].initial = 'is_experimental' if dataset.is_experimental \
                                            else 'is_theoretical'
        main_form.fields['sample_type'].initial = dataset.sample_type
        main_form.fields['crystal_system'].initial = dataset.crystal_system
        main_form.fields['space_group'].initial = dataset.space_group.pk

        # Synthesis
        if dataset.synthesis.exists():
            synthesis = dataset.synthesis.first()
            main_form.fields['with_synthesis_details'].initial = 'True'
            for field in filter(lambda field: type(field) is TextField,
                            models.SynthesisMethod._meta.get_fields()):
                if field.name == 'description':
                    main_form.fields['synthesis_description'].initial = synthesis.description
                else:
                    main_form.fields[field.name].initial = getattr(synthesis, field.name)
            if hasattr(synthesis, 'comment'):
                main_form.fields['synthesis_comment'].initial = synthesis.comment.text

        # Experimental
        if dataset.experimental.exists():
            experimental = dataset.experimental.first()
            for field in filter(lambda field: type(field) is TextField,
                                models.ExperimentalDetails._meta.get_fields()):
                if field.name == 'method':
                    main_form.fields['experimental_method'].initial = experimental.method
                elif field.name == 'description':
                    main_form.fields['experimental_description'].initial = experimental.description
                else:
                    main_form.fields[field.name] = getattr(experimental, field.name)
            if hasattr(experimental, 'comment'):
                main_form.fields['experimental_comment'] = experimental.comment.text

        # Computational
        if dataset.computational.exists():
            comp = dataset.computational.first()
            for field in filter(lambda field: type(field) is TextField,
                                models.ComputationalDetails._meta.get_fields()):
                main_form.fields[field.name] = getattr(comp, field.name)
            if hasattr(comp, 'comment'):
                main_form.fields['computational_comment'] = comp.comment.text

        # Subset data
        subsets = dataset.subsets.all()
        main_form.fields['number_of_subsets'].initial = len(subsets)
        data = []
        for i, subset in enumerate(subsets):
            if subset.reference:
                main_form.fields[f'select_reference_1_{i+1}'] = ModelChoiceField(
                                                        required=False,
                                                        queryset=models.Reference.objects.all(),
                                                        initial=subset.reference.pk)
            d = {}
            if dataset.primary_property.name == 'atomic structure':
                lattice = subset.lattice_constants.first()
                if lattice:
                    for field in filter(lambda field: type(field) is FloatField,
                                    models.LatticeConstant._meta.get_fields()):
                        d[f'lattice_constant_{field.name}_1_{i+1}'] = getattr(lattice, field.name)
                coords = subset.atomic_coordinates.all()
                if coords:
                    lines = ""
                    for coord in coords:
                        line = coord.label + ' ' + str(coord.coord_1) + ' ' + str(coord.coord_2) \
                             + ' ' + str(coord.coord_3) + ' ' + coord.element + '\n'
                        lines += line
                    d[f'atomic_coordinates_1_{i+1}'] = lines
            elif dataset.primary_property.name == 'tolerance factor related parameters':
                for shannon in subset.shannon_ionic_radiis.all():
                    element_label = models \
                                    .ShannonIonicRadii \
                                    .ELEMENT_LABELS[shannon.element_label][1] \
                                    .split(" ")[1]
                    d[f'element_{element_label}_1_{i+1}'] = shannon.element
                    d[f'charge_{element_label}_1_{i+1}'] = shannon.charge
                    d[f'coord_{element_label}_1_{i+1}'] = shannon.coordination
                    d[f'spin_state_{element_label}_1_{i+1}'] = shannon.spin_state
                labels = ['I', 'II', 'IV']
                for bond in subset.bond_length.all():
                    label = labels[bond.r_label]
                    d[f'element_{label}_X_a_1_{i+1}'] = bond.element_a
                    d[f'element_{label}_X_b_1_{i+1}'] = bond.element_b
                    d[f'R_{label}_X_1_{i+1}'] = bond.experimental_r if bond.experimental_r else ""
                print(d)
            else:
                # data for chart
                chart = subset.curves.first()
                if chart:
                    d[f'x_title_1_{i+1}'] = chart.x_title
                    d[f'x_unit_1_{i+1}'] = chart.x_unit
                    d[f'y_title_1_{i+1}'] = chart.y_title
                    d[f'y_unit_1_{i+1}'] = chart.y_unit
                    d[f'number_of_curves_1_{i+1}'] = len(subset.curves.all())
                for curve in subset.curves.all():
                    d[f'legend_1_{i+1}_{curve.curve_counter}'] = curve.legend
                    y_list = list(curve.datapoints.all().values_list('y_value', flat=True))
                    y_values = ['%.5g' % y for y in y_list]
                    if curve.curve_counter == 1:
                        x_list = list(curve.datapoints.all().values_list('x_value', flat=True))
                        x_values = ['%.5g' % x for x in x_list]
                        datapoints = [" ".join(t) for t in zip(x_values, y_values)]
                    else:
                        datapoints = [" ".join(t) for t in zip(datapoints, y_values)]
                        
                d[f'datapoints_1_{i+1}'] = "\n".join(datapoints)

                # fixed properties
                # i_dataset, i_subset, counter, prop, unit, sign, value
                if subset.fixed_values.exists():
                    fixed_values = []
                    for fixed in subset.fixed_values.all():
                        fixed_values.append({
                            'i_subset': i + 1,
                            'counter': fixed.counter,
                            'property': fixed.fixed_property.pk,
                            'unit': fixed.unit.pk,
                            'sign': fixed.value_type,
                            'value': fixed.value,
                        })

                    d['fixed_values'] = fixed_values

            data.append(d)
            print(data)

        return render(request, self.template_name, {
            'formula': formula,
            'primary_property': primary_property,
            'dataset_pk': dataset_pk,
            'main_form': main_form,
            'reference_form': forms.AddReferenceForm(),
            'property_form': forms.AddPropertyForm(),
            'unit_form': forms.AddUnitForm(),
            'space_group_form': forms.AddSpaceGroupForm(),
            'data': data,
            'base_template': base_template,
        })


class ImportDataView(StaffStatusMixin, generic.TemplateView):
    template_name = 'materials/import_data.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {
            'base_template': 'materials/base.html',
        })


class ToleranceFactorView(StaffStatusMixin, generic.TemplateView):
    template_name='materials/tolerance_factor.html'

    def get(self, request):
        compounds = models.ToleranceFactor.objects.all().values_list('compound__formula', 'compound__pk').distinct()
        return render(request, self.template_name, {
            'compounds': compounds,
            'base_template': 'materials/base.html',
            })


class ReferenceViewSet(viewsets.ModelViewSet):
    queryset = models.Reference.objects.all()
    serializer_class = serializers.ReferenceSerializer
    permission_classes = (permissions.IsStaffOrReadOnly,)

    @transaction.atomic
    def perform_create(self, serializer):
        """Save reference and optionally create authors.

        The combination first name/last name/institution must be
        unique. If not, the given author is not in the database
        yet. Note that this constraint can't be enforced at the
        database level because of the limitations of the length of the
        key.

        """
        reference = serializer.save()
        for name in self.request.POST:
            if name.startswith('first-name-'):
                counter = name.split('first-name-')[1]
                first_name = self.request.POST[name]
                last_name = self.request.POST[f'last-name-{counter}']
                institution = self.request.POST[f'institution-{counter}']
                authors = models.Author.objects.filter(
                    first_name=first_name).filter(last_name=last_name).filter(
                        institution=institution)
                if authors:
                    author = authors[0]
                else:
                    author = models.Author.objects.create(
                        first_name=first_name,
                        last_name=last_name,
                        institution=institution)
                author.references.add(reference)


class PropertyViewSet(viewsets.ModelViewSet):
    queryset = models.Property.objects.all()
    serializer_class = serializers.PropertySerializer
    permission_classes = (permissions.IsStaffOrReadOnly,)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class UnitViewSet(viewsets.ModelViewSet):
    queryset = models.Unit.objects.all()
    serializer_class = serializers.UnitSerializer
    permission_classes = (permissions.IsStaffOrReadOnly,)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class SpaceGroupViewSet(viewsets.ModelViewSet):
    queryset = models.SpaceGroup.objects.all()
    serializer_class = serializers.SpaceGroupSerializer
    permission_classes = (permissions.IsStaffOrReadOnly,)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@staff_status_required
@transaction.atomic
def submit_data(request):
    """Primary function for submitting data from the user."""

    def error_and_return(form, dataset=None, text=None):
        """Shortcut for returning with info about the error."""
        if form.cleaned_data['return_url']:
            base_template = 'mainproject/base.html'
        else:
            base_template = 'materials/base.html'
        if dataset:
            dataset.delete()
        if text:
            messages.error(request, text)
        return render(request, AddDataView.template_name, {
            'main_form': form,
            'reference_form': forms.AddReferenceForm(),
            'property_form': forms.AddPropertyForm(),
            'unit_form': forms.AddUnitForm(),
            'base_template': base_template
        })


    def skip_this_line(line):
        """Test whether the line is empty or a comment."""
        return re.match(r'\s*#', line) or not line or line == '\r'


    def create_input_file(subset, import_file_name, data_as_str, i_dataset, i_subset):
        """Read data points from the input form and save as file.

        If the name of the original file from which the data was
        imported is on the form, use that name for creating the
        file. If not and if multiple_subsets, then the files are named
        data1.txt, data2.txt, etc. Otherwise, a single file called
        data.txt is created and i_subset is ignored.

        """
        if data_as_str:
            if import_file_name:
                file_name = import_file_name
            # elif multiple_subsets:
            #     file_name = f'data{i_subset}.txt'
            else:
                file_name = f'data_{i_dataset}_{i_subset}.txt'
            f = SimpleUploadedFile(file_name, data_as_str.encode())
            subset.input_data_file = f
    

    # Submit data to database
    form = forms.AddDataForm(request.POST)
    if not form.is_valid():
        # Show formatted field labels in the error message, not the
        # dictionary keys
        errors_save = form._errors.copy()
        for field in form:
            if field.name in form._errors:
                form._errors[field.label] = form._errors.pop(field.name)
        messages.error(request, form.errors)
        form._errors = errors_save
        return error_and_return(form)

    # Create compound
    compound_list = [x[0] for x in models.Compound.objects.all().values_list('formula')]
    cur_compound = form.cleaned_data['formula']
    if cur_compound in compound_list:
        compound = models.Compound.objects.filter(formula=cur_compound)[0]
    else:
        compound = models.Compound.objects.create(
            created_by=request.user,
            formula=form.cleaned_data['formula'])
    # Create dataset
    for i_dataset in range(1, int(form.cleaned_data['number_of_datasets']) + 1):
        dataset = models.Dataset(created_by=request.user, compound=compound)
        dataset.primary_property = form.cleaned_data[f'primary_property_{i_dataset}']
        dataset.is_experimental = (
            form.cleaned_data[f'origin_of_data_{i_dataset}'] == 'is_experimental')
        dataset.sample_type = form.cleaned_data[f'sample_type_{i_dataset}']
        dataset.crystal_system = form.cleaned_data[f'crystal_system_{i_dataset}']
        dataset.space_group = form.cleaned_data[f'space_group_{i_dataset}']
        if f'update_comments_{i_dataset}' in form.cleaned_data:
            dataset.update_comments = form.cleaned_data[f'update_comments_{i_dataset}']
        dataset.save()
        logger.info(f'Create dataset #{dataset.pk}')
        if form.cleaned_data[f'with_synthesis_details_{i_dataset}']:
            synthesis = models.SynthesisMethod(created_by=request.user,
                                               dataset=dataset)
            synthesis.starting_materials = form.cleaned_data[f'starting_materials_{i_dataset}']
            synthesis.product = form.cleaned_data[f'product_{i_dataset}']
            synthesis.description = form.cleaned_data[f'synthesis_description_{i_dataset}']
            synthesis.save()
            logger.info(f'Creating synthesis details #{synthesis.pk}')
            if form.cleaned_data[f'synthesis_comment_{i_dataset}']:
                models.Comment.objects.create(
                    synthesis_method=synthesis,
                    created_by=request.user,
                    text=form.cleaned_data[f'synthesis_comment_{i_dataset}'])
        # Experimental details
        if form.cleaned_data[f'with_experimental_details_{i_dataset}']:
            experimental = models.ExperimentalDetails(created_by=request.user,
                                                      dataset=dataset)
            experimental.method = form.cleaned_data[f'experimental_method_{i_dataset}']
            experimental.description = form.cleaned_data[
                f'experimental_description_{i_dataset}']
            experimental.save()
            logger.info(f'Creating experimental details #{experimental.pk}')
            if form.cleaned_data[f'experimental_comment_{i_dataset}']:
                models.Comment.objects.create(
                    experimental_details=experimental,
                    created_by=request.user,
                    text=form.cleaned_data[f'experimental_comment_{i_dataset}'])
        # Computational details
        if form.cleaned_data[f'with_computational_details_{i_dataset}']:
            computational = models.ComputationalDetails(created_by=request.user,
                                                        dataset=dataset)
            computational.code = form.cleaned_data[f'code_{i_dataset}']
            computational.level_of_theory = form.cleaned_data[f'level_of_theory_{i_dataset}']
            computational.xc_functional = form.cleaned_data[f'xc_functional_{i_dataset}']
            computational.k_point_grid = form.cleaned_data[f'k_point_grid_{i_dataset}']
            computational.level_of_relativity = form.cleaned_data[
                f'level_of_relativity_{i_dataset}']
            computational.basis_set_definition = form.cleaned_data[
                f'basis_set_definition_{i_dataset}']
            computational.numerical_accuracy = form.cleaned_data[
                f'numerical_accuracy_{i_dataset}']
            computational.save()
            logger.info(f'Creating computational details #{computational.pk}')
            if form.cleaned_data[f'computational_comment_{i_dataset}']:
                models.Comment.objects.create(
                    computational_details=computational,
                    created_by=request.user,
                    text=form.cleaned_data[f'computational_comment_{i_dataset}'])
            if form.cleaned_data[f'external_repositories_{i_dataset}']:
                for url in form.cleaned_data[f'external_repositories_{i_dataset}'].split():
                    if not requests.head(url).ok:
                        return error_and_return(form, dataset,
                                                'Could not process url for the '
                                                f'external repository: "{url}"')
                    models.ExternalRepository.objects.create(
                        computational_details=computational,
                        created_by=request.user,
                        url=url)
        # For best performance, the main data should be inserted with
        # calls to bulk_create. The following work arrays are are
        # populated with data during the loop over subsets and then
        # inserted into the database after the main loop.
        datapoints = []
        lattice_constants = []
        atomic_coordinates = []
        # multiple_subsets = int(form.cleaned_data['number_of_subsets' + '_' + i_dataset]) > 1
        for i_subset in range(1, int(form.cleaned_data[f'number_of_subsets_{i_dataset}']) + 1):
            suffix = str(i_dataset) + '_' + str(i_subset)
            # Create data subset
            subset = models.Subset(created_by=request.user, dataset=dataset)
            subset.title = form.cleaned_data[f'sub_title_{suffix}']
            subset.reference = form.cleaned_data[f'select_reference_{suffix}']
            # Atomic structure data
            if dataset.primary_property.name == 'atomic structure':
                create_input_file(
                    subset,
                    form.cleaned_data[f'import_file_name_atomic_{suffix}'],
                    form.cleaned_data[f'atomic_coordinates_{suffix}'],
                    i_dataset,
                    i_subset
                )
                subset.save()
                # Store lattice constants into database
                lattice_constant = models.LatticeConstant(
                    created_by=request.user,
                    subset=subset)
                for key in ['a', 'b', 'c', 'alpha', 'beta', 'gamma']:
                    try:
                        value = float(form.cleaned_data[f'lattice_constant_{key}_{suffix}'])
                        setattr(lattice_constant, key, value)
                    except ValueError:
                        return error_and_return(form, dataset, f'Could not process lattice constant {key}.')
                lattice_constants.append(lattice_constant)
                # Store atomic coordinates into database
                lattice_vectors = []
                for line in form.cleaned_data[
                        f'atomic_coordinates_{suffix}'].split('\n'):
                    if form.cleaned_data[f'geometry_format_{suffix}'] != 'aims':
                        break
                    try:
                        m = re.match(r'\s*lattice_vector' +
                                     3*r'\s+(-?\d+(?:\.\d+)?)' + r'\b', line)
                        if m:
                            atomic_coordinate = models.AtomicCoordinate(
                                    created_by=request.user,
                                    subset=subset,
                                    label='lattice_vector'
                                    )
                            coords = m.groups()
                            for i, coord in enumerate(coords):
                                setattr(atomic_coordinate, f'coord_{i+1}', coord)
                        else:
                            m = re.match(
                                r'\s*(atom|atom_frac)\s+' +
                                3*r'(-?\d+(?:\.\d+)?(?:\(\d+\))?)\s+' +
                                r'(\w+)\b', line)
                            atomic_coordinate = models.AtomicCoordinate(
                                    created_by=request.user,
                                    subset=subset
                                    )
                            coord_type, *coords, element = m.groups()
                            atomic_coordinate.label = coord_type
                            atomic_coordinate.element = element
                            for i, coord in enumerate(coords):
                                setattr(atomic_coordinate, f'coord_{i+1}', coord)
                        atomic_coordinates.append(atomic_coordinate)
                    except AttributeError:
                        # Skip comments and empty lines
                        if not re.match(r'(?:\r?$|#|//)', line):
                            return error_and_return(
                                form, dataset, f'Could not process line: {line}')
            # Tolerance factor related parameters
            elif dataset.primary_property.name == 'tolerance factor related parameters':
                subset.save()
                label_list = ['I', 'II', 'IV', 'X']
                # Query for Shannon ionic radii
                r_dict = {}
                for i in range(4):
                    label = label_list[i]
                    shannon_r = models.ShannonIonicRadii(
                                    created_by=request.user,
                                    compound=compound,
                                    subset=subset,
                                    element_label=i)
                    shannon_r.element = form.cleaned_data[f'element_{label}_' + suffix]
                    shannon_r.charge = form.cleaned_data[f'charge_{label}_' + suffix]
                    shannon_r.coordination = form.cleaned_data[f'coord_{label}_' + suffix]
                    if f'spin_state_{label}_' + suffix in form.cleaned_data:
                        shannon_r.spin_state = form.cleaned_data[f'spin_state_{label}_' + suffix]
                    try:
                        if shannon_r.element and shannon_r.charge and shannon_r.coordination:
                            shannon_r.ionic_radius = models.ShannonRadiiTable.objects.filter(
                                element=shannon_r.element,
                                charge=shannon_r.charge,
                                coordination=shannon_r.coordination,
                                spin_state=shannon_r.spin_state)[0].ionic_radius
                            r_dict[f'r_{label}'] = shannon_r.ionic_radius
                        shannon_r.save()
                    except:
                        return error_and_return(form, dataset, 
                            f'Query for Shannon ionic radii of element {label}: {shannon_r.element} failed.')
                
                # Create bond length object for each bond
                for i in range(3):
                    label = label_list[i]
                    # If element_a, element_b is not filled, pad it with shannon inputs.
                    if form.cleaned_data[f'element_{label}_X_a_' + suffix]:
                        element_a = form.cleaned_data[f'element_{label}_X_a_' + suffix]
                    else:
                        element_a = form.cleaned_data[f'element_{label}_' + suffix]
                    if form.cleaned_data[f'element_{label}_X_b_' + suffix]:
                        element_b = form.cleaned_data[f'element_{label}_X_b_' + suffix]
                    else:
                        element_b = form.cleaned_data[f'element_X_' + suffix]
                    bond_obj = models.BondLength(
                        created_by=request.user,
                        compound=compound,
                        subset=subset,
                        r_label=i,
                        element_a=element_a,
                        element_b=element_b,
                        bond_id=element_a + '-' + element_b)
                    if form.cleaned_data[f'R_{label}_X_{suffix}']:
                        try:
                            # Experimental R assignment
                            bond_obj.experimental_r = float(form.cleaned_data[f'R_{label}_X_{suffix}'])
                            bond_obj.save()
                            bond_objs = models.BondLength.objects.filter(
                                bond_id=bond_obj.bond_id,
                                experimental_r__isnull=False)
                            # Averaged R assignment
                            avg_r = bond_objs.aggregate(Avg('experimental_r'))['experimental_r__avg']
                            count_r = bond_objs.count()
                            bond_objs.update(averaged_r=avg_r, counter=count_r)
                        except:
                            return error_and_return(form, dataset, f'Can not process experimental_r of {bond_obj.bond_id}.')
                    elif models.BondLength.objects.filter(
                                bond_id=bond_obj.bond_id,
                                experimental_r__isnull=False):
                        bond_objs = models.BondLength.objects.filter(
                                bond_id=bond_obj.bond_id,
                                experimental_r__isnull=False)
                        bond_obj.averaged_r = bond_objs[0].averaged_r
                        count_r = bond_objs.count()
                        count_r += 1
                        bond_objs.update(counter=count_r)
                        bond_obj.counter = count_r
                        bond_obj.save()
                    else:
                        bond_obj.save()

                # Shannon R assignment
                bond_obj_list = models.BondLength.objects.filter(
                                compound=compound, 
                                subset=subset).order_by('r_label')
                if 'r_I' in r_dict and 'r_X' in r_dict:
                    bond_obj_list.filter(r_label=0).update(shannon_r=r_dict['r_I']+r_dict['r_X'])
                if 'r_II' in r_dict and 'r_X' in r_dict:
                    bond_obj_list.filter(r_label=1).update(shannon_r=r_dict['r_II']+r_dict['r_X'])
                if 'r_IV' in r_dict and 'r_X' in r_dict:
                    bond_obj_list.filter(r_label=2).update(shannon_r=r_dict['r_IV']+r_dict['r_X'])


                # Create tolerance factor objects
                R_I_X_obj = models.BondLength.objects.filter(compound=compound, subset=subset, r_label=0)[0]
                R_II_X_obj = models.BondLength.objects.filter(compound=compound, subset=subset, r_label=1)[0]
                R_IV_X_obj = models.BondLength.objects.filter(compound=compound, subset=subset, r_label=2)[0]
                fields = ['shannon_r', 'experimental_r', 'averaged_r']
                for i in range(3):
                    field = fields[i]
                    tf_obj = models.ToleranceFactor(
                        created_by=request.user,
                        compound=compound,
                        subset=subset,
                        data_source=i,
                        space_group=dataset.space_group)
                    if getattr(R_I_X_obj, field) and getattr(R_II_X_obj, field):
                        t_I = math.sqrt((4 + math.sqrt(2)) / 3) * getattr(R_I_X_obj, field) / getattr(R_II_X_obj, field)
                        setattr(tf_obj, 't_I', t_I)
                    if getattr(R_IV_X_obj, field) and getattr(R_II_X_obj, field):
                        t_IV_V = math.sqrt((4 + math.sqrt(2)) / 3) * getattr(R_IV_X_obj, field) / getattr(R_II_X_obj, field)
                        setattr(tf_obj, 't_IV_V', t_IV_V)
                    tf_obj.save()              


            # Normal properties data
            else:
                create_input_file(
                    subset,
                    form.cleaned_data[f'import_file_name_{suffix}'],
                    form.cleaned_data[f'datapoints_{suffix}'],
                    i_dataset,
                    i_subset
                    )
                subset.save()
                # Create chart objects
                charts = []
                for i_curve in range(1, int(form.cleaned_data[f'number_of_curves_{suffix}'])+1):
                    charts.append(models.Chart(
                        created_by=request.user,
                        subset=subset,
                        x_title=form.cleaned_data[f'x_title_{suffix}'],
                        x_unit=form.cleaned_data[f'x_unit_{suffix}'],
                        y_title=form.cleaned_data[f'y_title_{suffix}'],
                        y_unit=form.cleaned_data[f'y_unit_{suffix}'],
                        legend=form.cleaned_data[f'legend_{suffix}_{i_curve}'],
                        curve_counter=i_curve
                        )
                    )
                models.Chart.objects.bulk_create(charts)
                charts_q = models.Chart.objects.filter(subset=subset)

                # Create datapoint objects
                try:
                    for i_line, line in enumerate(form.cleaned_data[f'datapoints_{suffix}'].splitlines()):
                        if skip_this_line(line):
                            continue
                        for i_col, value in enumerate(line.split()):
                            if i_col == 0:
                                x_value = float(value)
                            else:
                                datapoints.append(models.Datapoint(
                                    created_by=request.user,
                                    chart=charts_q[i_col-1],
                                    x_value=x_value,
                                    y_value=float(value),
                                    point_counter=i_line + 1)
                                )
                except ValueError:
                    return error_and_return(
                        form, dataset, f'Could not process line: {line}')

                # Fixed properties
                counter = 1
                for key in form.cleaned_data:
                    if key.startswith(f'fixed_property_{i_dataset}_{i_subset}_'):
                        suffix = key.split('fixed_property_')[1]
                        value = float(form.cleaned_data['fixed_value_' + suffix])
                        subset.fixed_values.create(
                            created_by=request.user,
                            fixed_property=form.cleaned_data[
                                'fixed_property_' + suffix],
                            value=value,
                            value_type=form.cleaned_data['fixed_sign_' + suffix],
                            unit=form.cleaned_data['fixed_unit_' + suffix],
                            counter=counter)
                        counter += 1
            
            # Additional files
            for f in request.FILES.getlist(f'additional_files_{i_dataset}_{i_subset}'):
                subset.additional_files.create(
                    created_by=request.user, 
                    additional_file=f)

        # Insert the main data into the database
        models.Datapoint.objects.bulk_create(datapoints)
        models.LatticeConstant.objects.bulk_create(lattice_constants)
        models.AtomicCoordinate.objects.bulk_create(atomic_coordinates)

        # # Create static files for Qresp
        # qresp.create_static_files(request, dataset)
        # # Import data from Qresp
        # if form.cleaned_data['qresp_fetch_url']:
        #     paper_detail = requests.get(
        #         form.cleaned_data['qresp_fetch_url'], verify=False).json()
        #     download_url = paper_detail['fileServerPath']
        #     chart_detail = paper_detail['charts'][
        #         form.cleaned_data['qresp_chart_nr']]
        #     chart = requests.get(f'{download_url}/{chart_detail["imageFile"]}',
        #                          verify=False)
        #     file_name = chart_detail["imageFile"].replace('/', '_')
        #     f = SimpleUploadedFile(file_name, chart.content)
        #     dataset.files.create(created_by=dataset.created_by, dataset_file=f)
        # If all went well, let the user know how much data was successfully added
        # n_data_points = 0
        # for subset in dataset.subsets.all():
        #     n_data_points += subset.datapoints.count()
        # if n_data_points > 0:
        #     message = (f'{n_data_points} new '
        #                f'data point{"s" if n_data_points != 1 else ""} '
        #                'successfully added to the database.')
        # else:
        #     message = 'New data successfully added to the database.'
        # dataset_url = reverse('materials:dataset', kwargs={'pk': dataset.pk})
        # message = mark_safe(message +
        #                     f' <a href="{dataset_url}">View</a> the data set.')
    if form.cleaned_data['qresp_search_url']:
        messages.success(request, message)
        return redirect('/materials/import-data', kwargs={
            'qresp_search_url': form.cleaned_data['qresp_search_url'],
            'qresp_chart_nr': form.cleaned_data['qresp_chart_nr'],
        })
    elif form.cleaned_data['return_url']:
        return redirect(
            f'{form.cleaned_data["return_url"]}?pk={dataset.pk}')
    else:
        message = 'New data successfully added to the database.'
        messages.success(request, message)
        return redirect(reverse('materials:add_data'))


def resolve_return_url(pk, view_name):
    """Determine URL from the view name and other arguments.

    This is useful for the data set buttons such as delete, which can
    then return to the same address.

    """
    if view_name == 'compound':
        return redirect(reverse('materials:compound', kwargs={'pk': pk}))
    # elif view_name == 'reference':
    #     ref_pk = models.Dataset.objects.get(pk=pk).reference.pk
    #     return redirect(reverse('materials:reference', kwargs={'pk': ref_pk}))
    else:
        return Http404


@dataset_author_check
def delete_dataset(request, compound_pk, dataset_pk, view_name):
    """Delete current data set and all associated files."""
    return_url = resolve_return_url(compound_pk, view_name)
    dataset = models.Dataset.objects.get(pk=dataset_pk)
    dataset.delete()
    return return_url


# @staff_status_required
# def verify_dataset(request, pk, view_name):
#     """Verify the correctness of the data."""
#     return_url = resolve_return_url(pk, view_name)
#     dataset = models.Dataset.objects.get(pk=pk)
#     if request.user in dataset.verified_by.all():
#         dataset.verified_by.remove(request.user)
#     else:
#         dataset.verified_by.add(request.user)
#     return return_url


def autofill_input_data(request):
    """Process an AJAX request to autofill the data textareas."""
    content = UploadedFile(request.FILES['file']).read().decode('utf-8')
    lines = content.splitlines()
    for i_line, line in enumerate(lines):
        if re.match(r'\s*#', line) or not line or line == '\r':
            del lines[i_line]
    return HttpResponse('\n'.join(lines))


def data_for_tf(request, data_source, compound_pk):
    response = {'data-source': data_source,
                'data': []}
    for space_group in models.SpaceGroup.objects.all():
        if compound_pk:
            datapoints = models.ToleranceFactor.objects.filter(
                data_source=data_source,
                space_group=space_group,
                compound__pk=compound_pk)
        else:  
            datapoints = models.ToleranceFactor.objects.filter(data_source=data_source, space_group=space_group)
        if datapoints:  
            response['data'].append({})
            dataset = response['data'][-1]
            dataset['space-group'] = space_group.name
            dataset['compounds'] = list(datapoints.values_list('compound__formula', 'compound__pk'))
            dataset['values'] = []
            for datapoint in datapoints:
                dataset['values'].append({
                    'x': '%.4f' % datapoint.t_I if datapoint.t_I else None, 
                    'y': '%.4f' % datapoint.t_IV_V if datapoint.t_IV_V else None,
                })

    return JsonResponse(response)


# def get_subset_values(request, pk):
#     """Return the numerical values of a subset as a formatted list."""
#     values = models.NumericalValue.objects.filter(
#         datapoint__subset__pk=pk).select_related(
#             'error').select_related('upperbound').order_by(
#                 'qualifier', 'datapoint__pk')
#     total_len = len(values)
#     y_len = total_len
#     # With both x- and y-values, the y-values make up half the list.
#     if values.last().qualifier == models.NumericalValue.SECONDARY:
#         y_len = int(y_len/2)
#     response = []
#     for i in range(y_len):
#         response.append({'y': values[i].formatted()})
#     for i in range(y_len, total_len):
#         response[i-y_len]['x'] = values[i].formatted()
#     return JsonResponse(response, safe=False)


# def report_issue(request):
#     pk = request.POST['pk']
#     description = request.POST['description']
#     user = request.user
#     if user.is_authenticated:
#         body = (f'Description:<blockquote>{description}</blockquote>'
#                 f'This report was issued by {escape(user.username)} '
#                 f'({escape(user.email)}).<br>'
#                 f'Data set location: {request.scheme}://'
#                 f'{request.get_host()}/materials/dataset/{pk}.')
#         email_addresses = list(User.objects.filter(
#             is_superuser=True).values_list('email', flat=True))
#         send_mail(
#             f'Issue report about dataset {pk}', '', 'matd3info',
#             email_addresses,
#             fail_silently=False,
#             html_message=body,
#         )
#         messages.success(request, 'Your report has been registered.')
#     else:
#         messages.error(request,
#                        'You must be logged in to perform this action.')
#     return redirect(request.POST['return-path'])





# class MintDoiView(StaffStatusMixin, generic.TemplateView):
#     """Authenticate user on Figshare."""

#     def get(self, request, *args, **kwargs):
#         request.session['MINT_DOI_RETURN_URL'] = request.META.get(
#             'HTTP_REFERER')
#         request.session['MINT_DOI_DATASET_PK'] = self.kwargs['pk']
#         if 'FIGSHARE_ACCESS_TOKEN' in request.session:
#             return redirect(reverse('materials:figshare_callback'))
#         else:
#             return render(request, 'materials/figshare_client_id.html', {
#                 'host_url': request.get_host()
#             })

#     def post(self, request, *args, **kwargs):
#         return redirect(
#             'https://figshare.com/account/applications/authorize?'
#             'response_type=token&'
#             f'client_id={request.POST["consumer-id"]}')


# def figshare_callback(request):
#     """"Upload data to Figshare and generate a DOI."""
#     def error_and_return(result):
#         messages.error(request, result.json())
#         return redirect(request.session['MINT_DOI_RETURN_URL'])

#     if 'FIGSHARE_ACCESS_TOKEN' not in request.session:
#         request.session['FIGSHARE_ACCESS_TOKEN'] = request.GET['access_token']
#     headers = {
#         'Authorization': f'token {request.session["FIGSHARE_ACCESS_TOKEN"]}'
#     }
#     dataset = models.Dataset.objects.get(
#         pk=request.session['MINT_DOI_DATASET_PK'])
#     title = dataset.caption
#     data_location = (
#         f'https://{request.get_host()}/materials/dataset/{dataset.pk}')
#     data = {
#         'title': title if title else f'Data set {dataset.pk}',
#         'description': f'Data location: {data_location}',
#         'keywords': [dataset.primary_property.name],
#         'categories': [110],
#         'defined_type': 'dataset',
#     }
#     result = requests.post('https://api.figshare.com/v2/account/articles',
#                            headers=headers,
#                            data=json.dumps(data))
#     if result.status_code >= 400:
#         return error_and_return(result)
#     article_location = result.json()['location']
#     data = {'link': data_location}
#     result = requests.post(
#         f'{article_location}/files', headers=headers, data=json.dumps(data))
#     # Generate and publish DOI
#     result = requests.post(f'{article_location}/reserve_doi', headers=headers)
#     if result.status_code >= 400:
#         return error_and_return(result)
#     dataset.doi = result.json()['doi']
#     dataset.save()
#     result = requests.post(f'{article_location}/publish', headers=headers)
#     if result.status_code >= 400:
#         return error_and_return(result)
#     messages.success(request,
#                      'A DOI was generated and the data set was published.')
#     return redirect(request.session['MINT_DOI_RETURN_URL'])
