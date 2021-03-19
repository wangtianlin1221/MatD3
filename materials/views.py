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
from django.db.models.fields import TextField
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
        dataset = get_object_or_404(models.Dataset, pk=kwargs['pk'])
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


# class CompoundView(generic.ListView):
    # template_name = 'materials/system.html'
    # context_object_name = 'dataset_list'

    # def get_queryset(self, **kwargs):
    #     return models.Dataset.objects.filter(
    #         system__pk=self.kwargs['pk']).annotate(is_atomic_structure=Case(
    #             When(primary_property__name='atomic structure',
    #                  then=Value(True)),
    #             default=Value(False), output_field=BooleanField())).order_by(
    #                 '-is_atomic_structure')


# class PropertyAllEntriesView(generic.ListView):
#     """Display all data sets for a given property and system."""
#     template_name = 'materials/property_all_entries.html'

#     def get_queryset(self, **kwargs):
#         return models.Dataset.objects.filter(
#             system__pk=self.kwargs['system_pk']).filter(
#                 primary_property__pk=self.kwargs['prop_pk'])


# class ReferenceDetailView(generic.DetailView):
#     model = models.Reference


# class DatasetView(generic.ListView):
#     """Display information about a single data set.

#     This is defined as a ListView so that we can reuse the same
#     template as for PropertyAllEntriesView. Otherwise, this is really
#     a DetailView.

#     """
#     template_name = 'materials/property_all_entries.html'

#     def get_queryset(self, **kwargs):
#         return models.Dataset.objects.filter(pk=self.kwargs['pk'])


# class LinkedDataView(generic.ListView):
#     """Returns data sets that are linked to each other."""
#     template_name = 'materials/linked_data.html'

#     def get_queryset(self, **kwargs):
#         dataset = models.Dataset.objects.get(pk=self.kwargs['pk'])
#         datasets = dataset.linked_to.all()
#         return list(datasets) + [dataset]

# Just for testing
def create_post(request):
    form = forms.AddDataForm()
    print("output:", form['number_of_subsets'].value())
    return HttpResponse()
    

class SearchFormView(generic.TemplateView):
    """Search for system page"""
    template_name = 'materials/search.html'
    search_terms = [
        ['formula', 'Formula'],
        ['physical_property', 'Physical property'],
        ['author', 'Author'],
    ]

    def get(self, request):
        material_ids = models.System.objects.all().values_list(
            'pk', 'compound_name')
        dataset_ids = models.Dataset.objects.all().values_list(
            'pk', 'system__compound_name', 'primary_property__name')
        return render(request, self.template_name, {
            'search_terms': self.search_terms,
            'material_ids': material_ids,
            'dataset_ids': dataset_ids,
        })

    def post(self, request):
        template_name = 'materials/search_results.html'
        form = forms.SearchForm(request.POST)
        search_text = ''
        # default search_term
        search_term = 'formula'
        physical_properties = [2]
        if form.is_valid():
            search_text = form.cleaned_data['search_text']
            search_term = request.POST.get('search_term')
            systems_info = []
            if search_term == 'formula':
                systems = models.System.objects.filter(
                    Q(formula__icontains=search_text) |
                    Q(group__icontains=search_text) |
                    Q(compound_name__icontains=search_text)).order_by(
                        'formula')
            elif search_term == 'physical_property':
                physical_properties = models.Property.objects.filter(
                    name__icontains=search_text).values_list('name', flat=True)
                systems = models.System.objects.filter(
                    dataset__primary_property__name__icontains=search_text)
            elif search_term == 'organic':
                systems = models.System.objects.filter(
                    organic__contains=search_text).order_by('organic')
            elif search_term == 'inorganic':
                systems = models.System.objects.filter(
                    inorganic__contains=search_text).order_by('inorganic')
            elif search_term == 'author':
                keywords = search_text.split()
                query = reduce(operator.or_, (
                    Q(dataset__reference__authors__last_name__icontains=x) for
                    x in keywords))
                systems = models.System.objects.filter(query).distinct()
            else:
                raise KeyError('Invalid search term.')
        args = {
            'systems': systems,
            'search_term': search_term,
            'systems_info': systems_info,
            'physical_properties': physical_properties,
        }
        return render(request, template_name, args)


class AddDataView(StaffStatusMixin, generic.TemplateView):
    """View for submitting user data.

    The arguments are only meant to be used when this view is called
    from external sites. Fields such as the reference can be prefilled
    then.

    """
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
        # if request.GET.get('reference'):
        #     main_form.fields['fixed_reference'].initial = (
        #         models.Reference.objects.get(pk=request.GET.get('reference')))
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
            'base_template': base_template,
        })


class ImportDataView(StaffStatusMixin, generic.TemplateView):
    template_name = 'materials/import_data.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {
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


# def dataset_to_zip(request, dataset):
#     """Generate a zip file from data set contents."""
#     in_memory_object = io.BytesIO()
#     zf = zipfile.ZipFile(in_memory_object, 'w')
#     # Header file to the data
#     zf.writestr('files/info.txt',
#                 utils.dataset_info(dataset, request.get_host()))
#     # Main data
#     for file_ in (f.dataset_file.path for f in dataset.input_files.all()):
#         zf.write(file_,
#                  os.path.join('files', os.path.basename(file_)))
#     # Additional files
#     for file_ in (f.dataset_file.path for f in dataset.files.all()):
#         zf.write(file_,
#                  os.path.join('files/additional', os.path.basename(file_)))
#     zf.close()
#     return in_memory_object


# class DatasetViewSet(viewsets.ReadOnlyModelViewSet):
#     queryset = models.Dataset.objects.all()
#     serializer_class = serializers.DatasetSerializer

#     @action(detail=True)
#     def info(self, request, pk):
#         dataset = self.get_object()
#         serializer = serializers.DatasetSerializerInfo(dataset)
#         return Response(serializer.data)

#     @action(detail=False)
#     def summary(self, request):
#         serializer = serializers.DatasetSerializerSummary(self.queryset,
#                                                           many=True)
#         return Response(serializer.data)

#     @action(detail=True)
#     def files(self, request, pk):
#         """Retrieve data set contents and uploaded files as zip."""
#         dataset = self.get_object()
#         in_memory_object = dataset_to_zip(request, dataset)
#         response = HttpResponse(in_memory_object.getvalue(),
#                                 content_type='application/x-zip-compressed')
#         response['Content-Disposition'] = 'attachment; filename=files.zip'
#         return response


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
    print(cur_compound)
    if cur_compound in compound_list:
        print("compound exists.")
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
        # Make representative by default if first entry of its kind
        dataset.representative = not bool(models.Dataset.objects.filter(
            compound=dataset.compound).filter(
                primary_property=dataset.primary_property))
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
                        return error_and_return(form, compound,
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
        tolerance_factors = []
        bond_lengths = []
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
                        return error_and_return(form, compound, f'Could not process lattice constant {key}.')
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
                                form, compound, f'Could not process line: {line}')
            # Tolerance factor
            elif dataset.primary_property.name == 'tolerance factor':
                subset.save()
                # Create tolerance factor objects
                tf_shannon = models.ToleranceFactor(
                    created_by=request.user,
                    subset=subset,
                    data_source=0)
                if form.cleaned_data['t1_shannon_' + suffix]:
                    try:
                        tf_shannon.t1 = float(form.cleaned_data['t1_shannon_' + suffix])
                    except ValueError:
                        return error_and_return(form=form, text=f'Could not process t1_shannon_{suffix}')
                if form.cleaned_data['t4_shannon_' + suffix]:
                    try:
                        tf_shannon.t4 = float(form.cleaned_data['t4_shannon_' + suffix])
                    except ValueError:
                        return error_and_return(form, compound, f'Could not process t4_shannon_{suffix}')
                tolerance_factors.append(tf_shannon)
                tf_exp = models.ToleranceFactor(
                    created_by=request.user,
                    subset=subset,
                    data_source=1)
                if form.cleaned_data['t1_experimental_' + suffix]:
                    try:
                        tf_exp.t1 = float(form.cleaned_data['t1_experimental_' + suffix])
                    except ValueError:
                        return error_and_return(form, compound, f'Could not process t1_experimental_{suffix}')
                if form.cleaned_data['t4_shannon_' + suffix]:
                    try:
                        tf_exp.t4 = float(form.cleaned_data['t4_experimental_' + suffix])
                    except ValueError:
                        return error_and_return(form, compound, f'Could not process t4_experimental_{suffix}')
                tolerance_factors.append(tf_exp)
                tf_avg = models.ToleranceFactor(
                    created_by=request.user,
                    subset=subset,
                    data_source=2)
                if form.cleaned_data['t1_averaged_' + suffix]:
                    try:
                        tf_avg.t1 = float(form.cleaned_data['t1_averaged_' + suffix])
                    except ValueError:
                        return error_and_return(form, compound, f'Could not process t1_averaged_{suffix}')
                if form.cleaned_data['t4_averaged_' + suffix]:
                    try:
                        tf_avg.t4 = float(form.cleaned_data['t4_averaged_' + suffix])
                    except ValueError:
                        return error_and_return(form, compound, f'Could not process t4_averaged_{suffix}')
                tolerance_factors.append(tf_avg)

            # Bond length
            elif dataset.primary_property.name == 'bond length':
                subset.save()
                counter = 1
                for key in form.cleaned_data:
                    if key.startswith(f'element_a_{suffix}_'):
                        bond_length = models.BondLength(
                            created_by=request.user,
                            subset=subset,
                            element_a = form.cleaned_data[f'element_a_{suffix}_{counter}'],
                            element_b = form.cleaned_data[f'element_b_{suffix}_{counter}'],
                            bond_counter=counter)
                        try:
                            if form.cleaned_data[f'r_avg_{suffix}_{counter}']:
                                bond_length.r_avg = float(form.cleaned_data[f'r_avg_{suffix}_{counter}'])
                            if form.cleaned_data[f'r_shannon_{suffix}_{counter}']:
                                bond_length.r_shannon = float(form.cleaned_data[f'r_shannon_{suffix}_{counter}'])
                            if form.cleaned_data[f'global_average_{suffix}_{counter}']:
                                bond_length.global_average = float(form.cleaned_data[f'global_average_{suffix}_{counter}'])
                            if form.cleaned_data[f'ravg_rglobal_{suffix}_{counter}']:
                                bond_length.ravg_rglobal = float(form.cleaned_data[f'ravg_rglobal_{suffix}_{counter}'])
                            if form.cleaned_data[f'ravg_rshannon_{suffix}_{counter}']:
                                bond_length.ravg_rshannon = float(form.cleaned_data[f'ravg_rshannon_{suffix}_{counter}'])
                            bond_lengths.append(bond_length)
                            counter += 1
                        except ValueError:
                            return error_and_return(form, compound, f'Could not process bond length {counter} in {subset}.')

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
                        form, compound, f'Could not process line: {line}')

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
    models.ToleranceFactor.objects.bulk_create(tolerance_factors)
    models.BondLength.objects.bulk_create(bond_lengths)

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


# def resolve_return_url(pk, view_name):
#     """Determine URL from the view name and other arguments.

#     This is useful for the data set buttons such as delete, which can
#     then return to the same address.

#     """
#     if view_name == 'dataset':
#         return redirect(reverse('materials:dataset', kwargs={'pk': pk}))
#     elif view_name == 'reference':
#         ref_pk = models.Dataset.objects.get(pk=pk).reference.pk
#         return redirect(reverse('materials:reference', kwargs={'pk': ref_pk}))
#     elif view_name == 'system':
#         sys_pk = models.Dataset.objects.get(pk=pk).system.pk
#         return redirect(reverse('materials:system', kwargs={'pk': sys_pk}))
#     elif view_name == 'property_all_entries':
#         sys_pk = models.Dataset.objects.get(pk=pk).system.pk
#         prop_pk = models.Dataset.objects.get(pk=pk).primary_property.pk
#         return redirect(reverse(
#             'materials:property_all_entries',
#             kwargs={'system_pk': sys_pk, 'prop_pk': prop_pk}))
#     elif view_name == 'linked_data':
#         return redirect(reverse('materials:linked_data', kwargs={'pk': pk}))
#     else:
#         return Http404


# @dataset_author_check
# def toggle_visibility(request, pk, view_name):
#     dataset = models.Dataset.objects.get(pk=pk)
#     dataset.visible = not dataset.visible
#     dataset.save()
#     return resolve_return_url(pk, view_name)


# @dataset_author_check
# def toggle_is_figure(request, pk, view_name):
#     dataset = models.Dataset.objects.get(pk=pk)
#     dataset.is_figure = not dataset.is_figure
#     dataset.save()
#     return resolve_return_url(pk, view_name)


# @dataset_author_check
# def delete_dataset(request, pk, view_name):
#     """Delete current data set and all associated files."""
#     return_url = resolve_return_url(pk, view_name)
#     dataset = models.Dataset.objects.get(pk=pk)
#     dataset.delete()
#     return return_url


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


# def data_for_chart(request, pk):
#     dataset = models.Dataset.objects.get(pk=pk)
#     if dataset.primary_unit:
#         primary_unit_label = dataset.primary_unit.label
#     else:
#         primary_unit_label = ''
#     if dataset.secondary_unit:
#         secondary_unit_label = dataset.secondary_unit.label
#     else:
#         secondary_unit_label = ''
#     response = {'primary-property': dataset.primary_property.name,
#                 'primary-unit': primary_unit_label,
#                 'secondary-property': dataset.secondary_property.name,
#                 'secondary-unit': secondary_unit_label,
#                 'data': []}
#     if dataset.primary_property_label:
#         response['primary-property'] = dataset.primary_property_label
#     if dataset.secondary_property_label:
#         response['secondary-property'] = (
#             f'{dataset.secondary_property.name} '
#             f'({dataset.secondary_property_label})')
#     for subset in dataset.subsets.all():
#         response['data'].append({})
#         this_subset = response['data'][-1]
#         this_subset['subset-label'] = subset.label
#         fixed_values = []
#         for value in models.NumericalValueFixed.objects.filter(subset=subset):
#             fixed_values.append(f' {value.physical_property} = '
#                                 f'{value.formatted()} {value.unit}')
#         if this_subset['subset-label']:
#             this_subset['subset-label'] = (
#                 f"{this_subset['subset-label']}:{','.join(fixed_values)}")
#         else:
#             this_subset['subset-label'] = (','.join(fixed_values)).lstrip()
#         this_subset['subset-label'] += (
#             f' ({models.Subset.CRYSTAL_SYSTEMS[subset.crystal_system][1]})')
#         values = models.NumericalValue.objects.filter(
#             datapoint__subset=subset).order_by(
#                 'datapoint_id', 'qualifier').values_list('value', flat=True)
#         this_subset['values'] = []
#         for i in range(0, len(values), 2):
#             this_subset['values'].append({'y': values[i], 'x': values[i+1]})
#     return JsonResponse(response)


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


# def get_atomic_coordinates(request, pk):
#     return JsonResponse(utils.atomic_coordinates_as_json(pk))


# def get_jsmol_input(request, pk):
#     """Return a statement to be executed by JSmol.

#     Go through the atomic structure data subsets of the representative
#     data set of the given system. Pick the first one that comes with a
#     geometry file and construct the "load data ..." statement for
#     JSmol. If there are no geometry files return an empty response.

#     """
#     dataset = models.Dataset.objects.get(pk=pk)
#     if not dataset:
#         return HttpResponse()
#     if dataset.input_files.exists():
#         filename = os.path.basename(
#             dataset.input_files.first().dataset_file.path)
#         return HttpResponse(
#             f'load /media/data_files/dataset_{dataset.pk}/{filename} '
#             '{1 1 1}')
#     return HttpResponse()


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


# def extract_k_from_control_in(request):
#     """Extract the k-point path from the provided control.in."""
#     content = UploadedFile(request.FILES['file']).read().decode('utf-8')
#     k_labels = []
#     for line in content.splitlines():
#         if re.match(r' *output\b\s* band', line):
#             words = line.split()
#             k_labels.append(f'{words[-2]} {words[-1]}')
#     return HttpResponse('\n'.join(k_labels))


# def prefilled_form(request, pk):
#     """Return a mostly filled form as json.

#     The form is filled based on data set pk. Fields such the actual
#     numerical values are not filled in.

#     """
#     def pk_or_none(obj):
#         if obj:
#             return obj.pk
#         return None

#     def bool_to_text(value):
#         """Return boolean as text.

#         Due to the way the templating system work, this is required
#         for certain inputs.

#         """
#         if value:
#             return 'True'
#         return 'False'
#     dataset = get_object_or_404(models.Dataset, pk=pk)
#     form = {
#         'values': {
#             'select_reference': pk_or_none(dataset.reference),
#             'select_system': dataset.system.pk,
#             'primary_property': dataset.primary_property.pk,
#             'primary_unit': pk_or_none(dataset.primary_unit),
#             'secondary_property': pk_or_none(dataset.secondary_property),
#             'secondary_unit': pk_or_none(dataset.secondary_unit),
#             'caption': dataset.caption,
#             'extraction_method': dataset.extraction_method,
#             'primary_property_label': dataset.primary_property_label,
#             'secondary_property_label': dataset.secondary_property_label,
#             'is_figure': dataset.is_figure,
#             'visible_to_public': dataset.visible,
#             'two_axes': bool(dataset.secondary_property),
#             'origin_of_data': ('is_experimental' if dataset.is_experimental
#                                else 'is_theoretical'),
#             'sample_type': dataset.sample_type,
#             'dimensionality_of_the_inorganic_component': (
#                 dataset.dimensionality),
#             'with_synthesis_details': bool_to_text(dataset.synthesis.exists()),
#             'with_experimental_details': bool_to_text(
#                 dataset.experimental.exists()),
#             'with_computational_details': bool_to_text(
#                 dataset.computational.exists())
#         },
#     }

#     def change_key(dictionary, key_old, key_new):
#         dictionary[key_new] = dictionary[key_old]
#         del dictionary[key_old]

#     if dataset.synthesis.exists():
#         synthesis = dataset.synthesis.first()
#         for field in filter(lambda field: type(field) is TextField,
#                             models.SynthesisMethod._meta.get_fields()):
#             form['values'][field.name] = getattr(synthesis, field.name)
#         change_key(form['values'], 'description', 'synthesis_description')
#         if hasattr(synthesis, 'comment'):
#             form['values']['synthesis_comment'] = synthesis.comment.text
#     if dataset.experimental.exists():
#         experimental = dataset.experimental.first()
#         for field in filter(lambda field: type(field) is TextField,
#                             models.ExperimentalDetails._meta.get_fields()):
#             form['values'][field.name] = getattr(experimental, field.name)
#         change_key(form['values'], 'method', 'experimental_method')
#         change_key(form['values'], 'description', 'experimental_description')
#         if hasattr(experimental, 'comment'):
#             form['values']['experimental_comment'] = experimental.comment.text
#     if dataset.computational.exists():
#         comp = dataset.computational.first()
#         for field in filter(lambda field: type(field) is TextField,
#                             models.ComputationalDetails._meta.get_fields()):
#             form['values'][field.name] = getattr(comp, field.name)
#         if hasattr(comp, 'comment'):
#             form['values']['computational_comment'] = comp.comment.text
#     return JsonResponse(form)


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
