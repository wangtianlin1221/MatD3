# This file is covered by the BSD license. See LICENSE in the root directory.
import logging
import os
import shutil

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
from django.utils.html import escape

from mainproject import settings

logger = logging.getLogger(__name__)


class Base(models.Model):
    """Basic meta information that all models must have."""
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(default=timezone.now)
    this = '%(app_label)s_%(class)s'
    created_by = models.ForeignKey(get_user_model(),
                                   related_name=f'{this}_created_by',
                                   on_delete=models.PROTECT)
    updated_by = models.ForeignKey(get_user_model(),
                                   related_name=f'{this}_updated_by',
                                   on_delete=models.PROTECT)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'created_by' in kwargs and 'updated_by' not in kwargs:
            self.updated_by = self.created_by

    def __str__(self):
        return f'ID: {self.pk}'


class Compound(Base):
    """Primary information about compound."""
    # compound_name = models.CharField(max_length=1000)
    formula = models.CharField(max_length=200)
    # group = models.CharField(max_length=100, blank=True)  # aka Alternate names
    # organic = models.CharField(max_length=100, blank=True)
    # inorganic = models.CharField(max_length=100, blank=True)
    # last_update = models.DateField(auto_now=True)
    # description = models.TextField(max_length=1000, blank=True)
    # tags = models.ManyToManyField(Tag, blank=True)

    def __str__(self):
        return self.formula

    # def listAlternateNames(self):
    #     return self.group.replace(',', ' ').split()

class Property(Base):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'properties'

    def __str__(self):
        return self.name


class Unit(Base):
    label = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.label


class Reference(models.Model):
    title = models.CharField(max_length=1000)
    journal = models.CharField(max_length=500, blank=True)
    vol = models.CharField(max_length=100)
    pages_start = models.CharField(max_length=10)
    pages_end = models.CharField(max_length=10)
    year = models.CharField(max_length=4)
    doi_isbn = models.CharField(max_length=100, blank=True)

    def __str__(self):
        text = (f'{self.year} {"- " if self.year else ""} '
                f'{self.getAuthorsAsString()} {self.journal} {self.vol} '
                f'{"," if self.vol and self.pages_start else ""} '
                f'{self.pages_start} "{self.title}"')
        return text

    def getAuthorsAsString(self):
        names = ', '.join([f'{x.first_name[0]}. {x.last_name}' for
                           x in self.authors.all()])
        if names:
            names += ','
        return names

    def getAuthors(self):
        return self.authors.all()


class Author(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    institution = models.CharField(max_length=600, blank=True)
    references = models.ManyToManyField(Reference, related_name='authors')

    def __str__(self):
        value = (self.first_name + ' ' + self.last_name + ', ' +
                 self.institution)
        if len(value) > 45:
            value = value[:42] + '...'
        return value

    def splitFirstName(self):
        return self.first_name.split()


class Dataset(Base):
    """A dataset represents data per property per compound.
    """
    # Define sample type choices
    SINGLE_CRYSTAL = 0
    POWDER = 1
    FILM = 2
    BULK_POLYCRYSTALLINE = 3
    PELLET = 4
    NANOFORM = 5
    UNKNOWN = 6
    SAMPLE_TYPES = (
        (SINGLE_CRYSTAL, 'single crystal'),
        (POWDER, 'powder'),
        (FILM, 'film'),
        (BULK_POLYCRYSTALLINE, 'bulk polycrystalline'),
        (PELLET, 'pellet'),
        (NANOFORM, 'nanoform'),
        (UNKNOWN, 'unknown'),
    )
    # Define crystal system choices
    TRICLINIC = 0
    MONOCLINIC = 1
    ORTHORHOMBIC = 2
    TETRAGONAL = 3
    TRIGONAL = 4
    HEXAGONAL = 5
    CUBIC = 6
    UNKNOWN_SYSTEM = 7
    CRYSTAL_SYSTEMS = (
        (TRICLINIC, 'triclinic'),
        (MONOCLINIC, 'monoclinic'),
        (ORTHORHOMBIC, 'orthorhombic'),
        (TETRAGONAL, 'tetragonal'),
        (TRIGONAL, 'trigonal'),
        (HEXAGONAL, 'hexagonal'),
        (CUBIC, 'cubic'),
        (UNKNOWN_SYSTEM, 'unknown'),
    )
    compound = models.ForeignKey(Compound, related_name='datasets', on_delete=models.CASCADE)
    primary_property = models.ForeignKey(
        Property, on_delete=models.PROTECT, related_name='primary_property')
    is_experimental = models.BooleanField()  # theoretical if false
    sample_type = models.PositiveSmallIntegerField(choices=SAMPLE_TYPES)
    crystal_system = models.PositiveSmallIntegerField(choices=CRYSTAL_SYSTEMS)
    space_group = models.CharField(max_length=20, blank=True)
    representative = models.BooleanField(default=False)
    verified_by = models.ManyToManyField(get_user_model())

    class Meta:
        verbose_name_plural = 'data sets'

    def __str__(self):
        return f'{self.compound}: {self.primary_property} (ID: {self.pk})'

    def save(self, *args, **kwargs):
        if self.representative:
            # Unset the representative flag of the dataset that was
            # previously representative
            Dataset.objects.filter(compound=self.compound).filter(
                primary_property=self.primary_property).update(
                    representative=False)
        if self.pk and self.verified_by.exists():
            email_addresses = self.verified_by.all().values_list('email',
                                                                 flat=True)
            dataset_location = (
                f'{settings.MATD3_URL}/materials/dataset/{self.pk}')
            body = (
                f'<p>A data set with ID = <a href="{dataset_location}">'
                f'{self.pk}</a>, which you have previously verified, has been '
                f'modified by {escape(self.updated_by.first_name)} '
                f'{escape(self.updated_by.last_name)} '
                f'({escape(self.updated_by.email)}). As a result, its '
                'verified status has been revoked. See the '
                f'<a href="{settings.MATD3_URL}/admin/materials/dataset/'
                f'{self.pk}/history/">history</a> of what has been changed. '
                f'If you consider the entered data to be correct, please go '
                'to the website and re-verify the data.</p>'
                '<p>This is an automated email. Please do not respond!</p>')
            send_mail(
                f'{settings.MATD3_NAME} data set verified by you has been '
                'modified',
                '',
                'matd3info',
                email_addresses,
                fail_silently=False,
                html_message=body,
            )
            for user in self.verified_by.all():
                self.verified_by.remove(user)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Additionally remove all files uploaded by the user."""
        if self.representative:
            Dataset.objects.filter(compound=self.compound).filter(
                primary_property=self.primary_property).exclude(
                    pk=self.pk).update(representative=True)
        super().delete(*args, **kwargs)

    def num_all_entries(self):
        return Dataset.objects.filter(compound=self.compound).filter(
            primary_property=self.primary_property).count()

    def get_all_fixed_temperatures(self):
        """Return a formatted list of all fixed temperatures."""
        values = []
        for value in NumericalValueFixed.objects.filter(
                subset__dataset=self).filter(
                    physical_property__name='temperature'):
            values.append(f'{value.formatted()} {value.unit}')
        return ('(T = ' + ', '.join(values) + ')' if values else '')

    def get_geometry_file_location(self):
        if self.primary_property.name != 'atomic structure':
            for file_ in self.files.all():
                if os.path.basename(file_.dataset_file.name) == 'geometry.in':
                    return os.path.join(settings.MEDIA_URL,
                                        file_.dataset_file.name)
        return ''


class SynthesisMethod(Base):
    dataset = models.ForeignKey(
        Dataset, on_delete=models.CASCADE, related_name='synthesis')
    starting_materials = models.TextField(blank=True)
    product = models.TextField(blank=True)
    description = models.TextField(blank=True)


class ExperimentalDetails(Base):
    dataset = models.ForeignKey(
        Dataset, on_delete=models.CASCADE, related_name='experimental')
    method = models.TextField()
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'experimental details'   


class ComputationalDetails(Base):
    dataset = models.ForeignKey(
        Dataset, on_delete=models.CASCADE, related_name='computational')
    code = models.TextField(blank=True)
    level_of_theory = models.TextField(blank=True)
    xc_functional = models.TextField(blank=True)
    k_point_grid = models.TextField(blank=True)
    level_of_relativity = models.TextField(blank=True)
    basis_set_definition = models.TextField(blank=True)
    numerical_accuracy = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'computational details'


class Comment(Base):
    synthesis_method = models.OneToOneField(
        SynthesisMethod, null=True, on_delete=models.CASCADE)
    computational_details = models.OneToOneField(
        ComputationalDetails, null=True, on_delete=models.CASCADE)
    experimental_details = models.OneToOneField(
        ExperimentalDetails, null=True, on_delete=models.CASCADE)
    text = models.TextField()

    def __str__(self):
        return self.text


class ExternalRepository(Base):
    computational_details = models.ForeignKey(ComputationalDetails,
                                              on_delete=models.CASCADE,
                                              related_name='repositories')
    url = models.TextField(blank=True)


def data_file_path(instance, filename):
    return os.path.join(
        'data_files', f'dataset_{instance.dataset.pk}_subset_{instance.title}', filename)


class Subset(Base):
    """Subset of data.

    A data set always has at least one subset. It may have more if it
    makes sense to split up data into several subsets (e.g., several
    curves in a figure).

    """
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE,
                                related_name='subsets')
    title = models.CharField(max_length=100)
    input_data_file = models.FileField(upload_to=data_file_path, null=True)
    reference = models.ForeignKey(
        Reference, on_delete=models.PROTECT, related_name='subsets', null=True)
    # crystal_system = models.PositiveSmallIntegerField(choices=CRYSTAL_SYSTEMS)

    class Meta:
        verbose_name_plural = 'data subsets'

    def __str__(self):
        return f'ID: {self.pk} {self.title}'

    def delete(self, *args, **kwargs):
        """Additionally remove all files uploaded by the user."""
        if self.additional_files.exists():
            shutil.rmtree(
                os.path.dirname(self.additional_files.first().additional_file.path))
        # if self.input_files.exists():
        #     shutil.rmtree(
        #         os.path.dirname(self.input_files.first().dataset_file.path))
        super().delete(*args, **kwargs)

    def get_fixed_values(self):
        """Return all fixed properties for the given subset."""
        values = self.fixed_values.all()
        output = []
        for value in values:
            value_str = value.formatted()
            output.append([
                value.physical_property.name, value_str, value.unit.label])
        return output

    def get_lattice_constants(self):
        """Return three lattice constants and angles."""
        symbols = Symbol.objects.filter(datapoint__subset=self).annotate(
            num=models.Count('datapoint__symbols')).filter(num=1).order_by(
                'datapoint_id').values_list('value', flat=True)
        values_float = NumericalValue.objects.filter(
            datapoint__subset=self).annotate(
                num=models.Count('datapoint__values')).filter(
                    num=1).select_related('error').select_related(
                        'upperbound').order_by('datapoint_id')
        if self.dataset.primary_unit:
            units = 3*[f' {self.dataset.primary_unit.label}'] + 3*['°']
        else:
            units = 3*[' '] + 3*['°']
        values = []
        for value in values_float:
            values.append(value.formatted('.10g'))
        return zip(symbols, values, units)

    def first_with_atomic_coordinates(self):
        """Whether this is the first subset to contain atomic coordinates.

        Return True if out of all subsets belonging to a given data
        set, this is the first one to contain the full set of atomic
        coordinates (lattice vectors and absolute/fractional
        coordinates).

        """
        for subset in self.dataset.subsets.all():
            if subset.datapoints.count() > 6:
                return subset.pk == self.pk
        return False


def additional_file_path(instance, filename):
    return os.path.join('uploads', f'dataset_{instance.subset.dataset.pk}_subset_{instance.subset.pk}', filename)


class AdditionalFile(Base):
    """Additional files uploaded with the subset."""
    subset = models.ForeignKey(Subset, on_delete=models.CASCADE,
                                related_name='additional_files')
    additional_file = models.FileField(upload_to=additional_file_path)


class FixedPropertyValue(Base):
    """Values that are constant within a data subset."""
    ACCURATE = 0
    APPROXIMATE = 1
    GREATER_THAN = 2
    GREATER_EQUAL = 3
    LESS_THAN = 4
    LESS_EQUAL = 5
    VALUE_TYPES = (
        (ACCURATE, '='),
        (APPROXIMATE, '≈'),
        (GREATER_THAN, '>'),
        (GREATER_EQUAL, '≥'),
        (LESS_THAN, '<'),
        (LESS_EQUAL, '≤')
    )

    subset = models.ForeignKey(
        Subset, on_delete=models.CASCADE, related_name='fixed_values')
    fixed_property = models.ForeignKey(Property, on_delete=models.PROTECT)
    value = models.FloatField()
    value_type = models.PositiveSmallIntegerField(
        default=ACCURATE, choices=VALUE_TYPES)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    counter = models.PositiveSmallIntegerField(default=0)

    def formatted(self):
        """Same as for NumericalValue but error is now a class member."""
        value_str = f'{self.VALUE_TYPES[self.value_type][1]}{self.value}'
        # if self.error:
        #     value_str += f' (±{self.error})'
        # if self.upper_bound:
        #     value_str += f'...{self.upper_bound}'
        return value_str


class Chart(Base):
    """General chart elements for a subset.
    Each record represents a curve.
    """
    subset = models.ForeignKey(
        Subset, on_delete=models.CASCADE, related_name='lines')
    x_title = models.CharField(max_length=100)
    x_unit = models.CharField(max_length=20, blank=True)
    y_title = models.CharField(max_length=100)
    y_unit = models.CharField(max_length=20, blank=True)
    legend = models.CharField(max_length=100, blank=True)
    curve_counter = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return f'{self.y_title} - {self.x_title} (legend: {self.legend})'


class Datapoint(Base):
    """Container for the data points for chart.
    """
    chart = models.ForeignKey(
        Chart, on_delete=models.CASCADE, related_name='datapoints')
    x_value = models.FloatField()
    y_value = models.FloatField()
    point_counter = models.PositiveSmallIntegerField(default=0)


class LatticeConstant(Base):
    """Store lattice constants of atomic structure.
    """
    subset = models.ForeignKey(
        Subset, on_delete=models.CASCADE, related_name='lattice_constants')
    a = models.FloatField()
    b = models.FloatField()
    c = models.FloatField()
    alpha = models.FloatField()
    beta = models.FloatField()
    gamma = models.FloatField()


class AtomicCoordinate(Base):
    subset = models.ForeignKey(
        Subset, on_delete=models.CASCADE, related_name='atomic_coordinates')
    # label: label of coordinate
    label = models.CharField(max_length=20)
    coord_1 = models.FloatField()
    coord_2 = models.FloatField()
    coord_3 = models.FloatField()
    element = models.CharField(max_length=20, blank=True)


class ShannonIonicRadii(Base):
    # Define element labels
    I = 0
    II = 1
    IV = 2
    X = 3
    ELEMENT_LABELS = (
        (I, 'element I'),
        (II, 'element II'),
        (IV, 'element IV'),
        (X, 'element X')
    )
    compound = models.ForeignKey(
        Compound, on_delete=models.CASCADE, related_name='shannon_ionic_radiis')
    subset = models.ForeignKey(
        Subset, on_delete=models.CASCADE, related_name='shannon_ionic_radiis')
    element_label = models.PositiveSmallIntegerField(default=I, choices=ELEMENT_LABELS)
    charge = models.PositiveSmallIntegerField(null=True, blank=True)
    coordination = models.CharField(blank=True, max_length=20)
    ionic_radius = models.FloatField(null=True, blank=True)
    key = models.CharField(blank=True, max_length=20)    


class ToleranceFactor(Base):
    # Define data sources
    SHANNON = 0
    EXPERIMENTAL = 1
    AVERAGED = 2
    DATA_SOURCES = (
        (SHANNON, 'Based on Shannon Radii'),
        (EXPERIMENTAL, 'Experimental'),
        (AVERAGED, 'Averaged')
    )
    compound = models.ForeignKey(
        Compound, on_delete=models.CASCADE, related_name='tolerance_factors')
    subset = models.ForeignKey(
        Subset, on_delete=models.CASCADE, related_name='tolerance_factors')
    data_source = models.PositiveSmallIntegerField(default=SHANNON, choices=DATA_SOURCES)
    t_I = models.FloatField(null=True, blank=True)
    t_IV_V = models.FloatField(null=True, blank=True)


class BondLength(Base):
    # Define data sources
    EXPERIMENTAL = 0
    AVERAGED = 1
    DATA_SOURCES = (
        (EXPERIMENTAL, 'Experimental'),
        (AVERAGED, 'Averaged')
    )
    # Define r labels
    I_X = 0
    II_X = 1
    IV_X = 2
    R_LABELS = (
        (I_X, 'I-X'),
        (II_X, "II,I'-X"),
        (IV_X, 'IV,V-X')
    )
    compound = models.ForeignKey(
        Compound, on_delete=models.CASCADE, related_name='bond_length')   
    subset = models.ForeignKey(
        Subset, on_delete=models.CASCADE, related_name='bond_length')
    data_source = models.PositiveSmallIntegerField(default=EXPERIMENTAL, choices=DATA_SOURCES)
    r_label = models.PositiveSmallIntegerField(default=I_X, choices=R_LABELS)
    element_a = models.CharField(max_length=20)
    element_b = models.CharField(max_length=20)
    bond_id = models.CharField(blank=True, max_length=20)
    bond_length = models.FloatField(null=True, blank=True)
    

# class NumericalValueBase(Base):
#     ACCURATE = 0
#     APPROXIMATE = 1
#     LOWER_BOUND = 2
#     UPPER_BOUND = 3
#     VALUE_TYPES = (
#         (ACCURATE, ''),
#         (APPROXIMATE, '≈'),
#         (LOWER_BOUND, '>'),
#         (UPPER_BOUND, '<'),
#     )
#     value = models.FloatField()
#     value_type = models.PositiveSmallIntegerField(
#         default=ACCURATE, choices=VALUE_TYPES)
#     counter = models.PositiveSmallIntegerField(default=0)

#     class Meta:
#         abstract = True


# class NumericalValue(NumericalValueBase):
#     """Numerical value(s) associated with a data point."""
#     PRIMARY = 0
#     SECONDARY = 1
#     QUALIFIER_TYPES = (
#         (PRIMARY, 'primary'),
#         (SECONDARY, 'secondary'),
#     )
#     datapoint = models.ForeignKey(Datapoint, on_delete=models.CASCADE,
#                                   related_name='values')
#     qualifier = models.PositiveSmallIntegerField(
#         default=PRIMARY, choices=QUALIFIER_TYPES)

#     def formatted(self, F=''):
#         """Return the value as a formatted string.

#         In particular, the value type and an error, if present, are
#         attached to the value, e.g., ">12.3 (±0.4)".

#         """
#         value_str = f'{self.VALUE_TYPES[self.value_type][1]}{self.value:{F}}'
#         if hasattr(self, 'error'):
#             value_str += f' (±{self.error.value:{F}})'
#         if hasattr(self, 'upperbound'):
#             value_str += f'...{self.upperbound.value:{F}}'
#         return value_str
