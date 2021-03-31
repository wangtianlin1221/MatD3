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
    formula = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.formula


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


class SpaceGroup(Base):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


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
        Property, on_delete=models.PROTECT, related_name='datasets')
    is_experimental = models.BooleanField()  # theoretical if false
    sample_type = models.PositiveSmallIntegerField(choices=SAMPLE_TYPES)
    crystal_system = models.PositiveSmallIntegerField(choices=CRYSTAL_SYSTEMS)
    space_group = models.ForeignKey(
        SpaceGroup, on_delete=models.PROTECT, related_name='datasets')
    update_comments = models.CharField(blank=True, max_length=300) # reason for updating
    verified_by = models.ManyToManyField(get_user_model())


    def __str__(self):
        return f'{self.compound}: {self.primary_property}'

    def save(self, *args, **kwargs):
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

    def dataset_count(self):
        return Dataset.objects.filter(compound=self.compound).filter(
            primary_property=self.primary_property).count()


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
        'data_files', f'dataset_{instance.dataset.pk}', filename)


class Subset(Base):
    """Containing data. A dataset can have one or more subsets.
    """
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE,
                                related_name='subsets')
    title = models.CharField(max_length=100)
    input_data_file = models.FileField(upload_to=data_file_path, null=True)
    reference = models.ForeignKey(
        Reference, on_delete=models.PROTECT, related_name='subsets', null=True)

    def __str__(self):
        return f'ID: {self.pk} {self.title}'

    def delete(self, *args, **kwargs):
        """Additionally remove all additional files uploaded by the user."""
        if self.additional_files.exists():
            shutil.rmtree(
                os.path.dirname(self.additional_files.first().additional_file.path))
        super().delete(*args, **kwargs)

    def get_additional_files_path(self):
        paths = []
        for file_ in self.additional_files.all():
            paths.append(os.path.join(settings.MEDIA_URL, file_.additional_file.name))
        return paths

    def get_fixed_properties(self):
        """Return all fixed properties for the given subset."""
        fixed_properties = []
        for obj in self.fixed_values.all():
            fixed_properties.append({
                'fixed property': obj.fixed_property.name,
                'value type': FixedPropertyValue.VALUE_TYPES[obj.value_type][1],
                'value': obj.value,
                'unit': obj.unit.label,
                })
        return fixed_properties

    def get_lattice_constants(self):
        """Return lattice constants and angles."""
        symbols = ['a', 'b', 'c', 'α', 'β', 'γ']
        obj = self.lattice_constants.first()
        values_float = [obj.a, obj.b, obj.c, obj.alpha, obj.beta, obj.gamma]
        units = [' ', ' ', ' ', '°', '°', '°']
        values = []
        for value in values_float:
            values.append('%10g' % value)
        return zip(symbols, values, units)

    def get_atomic_coordinates(self):
        """Return atomic coordinates."""
        coords = []
        for obj in self.atomic_coordinates.all():
            coords.append({
                'label': obj.label,
                'coord_1': '%10g' % obj.coord_1,
                'coord_2': '%10g' % obj.coord_2,
                'coord_3': '%10g' % obj.coord_3,
                'element': obj.element,
            })
        return coords

    def get_bond_lengths(self):
        """Return bond lengths."""
        bond_lengths = []
        for obj in self.bond_length.all():
            bond_lengths.append({
                'bond label': BondLength.R_LABELS[obj.r_label][1],
                'bond id': obj.bond_id,
                'shannon R': obj.shannon_r,
                'experimental R': obj.experimental_r,
                'averaged R': obj.averaged_r,
            })
        return bond_lengths

    def get_tolerance_factors(self):
        """Return tolerance factors."""
        tfs = []
        for obj in self.tolerance_factors.all():
            tfs.append({
                'data source': ToleranceFactor.DATA_SOURCES[obj.data_source][1],
                'space group': obj.space_group.name,
                't_I': obj.t_I,
                't_IV/V': obj.t_IV_V,
                })
        return tfs


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
        value_str = f'{self.VALUE_TYPES[self.value_type][1]}{self.value}'
        return value_str


class Chart(Base):
    """General chart elements for a subset.
    Each record represents a curve.
    """
    subset = models.ForeignKey(
        Subset, on_delete=models.CASCADE, related_name='curves')
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
    coord_1 = models.FloatField(null=True, blank=True)
    coord_2 = models.FloatField(null=True, blank=True)
    coord_3 = models.FloatField(null=True, blank=True)
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
    # Define spin states
    NO_SPIN = 0
    HIGH_SPIN = 1
    LOW_SPIN = 2
    SPIN_STATES = (
        (NO_SPIN, 'no spin'),
        (HIGH_SPIN, 'high spin'),
        (LOW_SPIN, 'low spin')
    )
    compound = models.ForeignKey(
        Compound, on_delete=models.CASCADE, related_name='shannon_ionic_radiis')
    subset = models.ForeignKey(
        Subset, on_delete=models.CASCADE, related_name='shannon_ionic_radiis')
    element_label = models.PositiveSmallIntegerField(default=I, choices=ELEMENT_LABELS)
    element = models.CharField(blank=True, max_length=20)
    charge = models.CharField(blank=True, max_length=20)
    coordination = models.CharField(blank=True, max_length=20)
    spin_state = models.PositiveSmallIntegerField(default=NO_SPIN, choices=SPIN_STATES)
    ionic_radius = models.FloatField(null=True, blank=True)   


class ShannonRadiiTable(models.Model):
    """Stores Shannon ionic radii for user to query radius by (element, charge, coordination)
    """
    # Define spin states
    NO_SPIN = 0
    HIGH_SPIN = 1
    LOW_SPIN = 2
    SPIN_STATES = (
        (NO_SPIN, 'no spin'),
        (HIGH_SPIN, 'high spin'),
        (LOW_SPIN, 'low spin')
    )
    element = models.CharField(blank=True, max_length=20)
    charge = models.CharField(blank=True, max_length=20)
    coordination = models.CharField(blank=True, max_length=20)
    spin_state = models.PositiveSmallIntegerField(default=NO_SPIN, choices=SPIN_STATES)
    ionic_radius = models.FloatField(null=True, blank=True)
    key = models.CharField(null=True, blank=True, max_length=20)

    class Meta:
        unique_together = ("element", "charge", "coordination", "spin_state")


class BondLength(Base):
    """Stores experimental bond length.
    """
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
    r_label = models.PositiveSmallIntegerField(default=I_X, choices=R_LABELS)
    element_a = models.CharField(max_length=20)
    element_b = models.CharField(max_length=20)
    bond_id = models.CharField(blank=True, max_length=20)
    experimental_r = models.FloatField(null=True, blank=True)
    averaged_r = models.FloatField(null=True, blank=True)
    shannon_r = models.FloatField(null=True, blank=True)
    counter = models.PositiveSmallIntegerField(default=0)


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
    space_group = models.ForeignKey(
        SpaceGroup, on_delete=models.CASCADE, related_name='tolerance_factors')
    t_I = models.FloatField(null=True, blank=True)
    t_IV_V = models.FloatField(null=True, blank=True)