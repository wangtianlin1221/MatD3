# This file is covered by the BSD license. See LICENSE in the root directory.
from django import forms
from django.utils.safestring import mark_safe

from materials import models


class SearchForm(forms.Form):
    search_text = forms.CharField(label='Search term', max_length=100)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['search_text'].widget.attrs['class'] = 'form-control'


class AutoCharField(forms.CharField):
    """Like regular CharField but max_length is automatically determined."""
    def __init__(self, model=None, field=None, *args, **kwargs):
        if model:
            max_length = model._meta.get_field(field).max_length
        else:
            max_length = None
        super().__init__(required=False, max_length=max_length,
                         *args, **kwargs)


class AddReferenceForm(forms.Form):
    title = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        max_length=1000,
        help_text='Article title')
    journal = forms.CharField(
        label='Journal or Publisher',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        max_length=1000,
        help_text='Full name of the journal or publisher')
    vol = forms.CharField(
        required=False,
        label='Volume',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        max_length=1000,
        help_text='')
    pages_start = forms.CharField(
        label='Starting page',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        max_length=1000,
        help_text='Number of the first page of the publication')
    pages_end = forms.CharField(
        label='Ending page',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        max_length=1000,
        help_text='Number of the last page of the publication')
    year = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        max_length=1000,
        help_text='Year of publication')
    doi_isbn = forms.CharField(
        required=False,
        label='DOI or ISBN',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        max_length=1000,
        help_text='Enter DOI or ISBN if applicable.')


class AddPropertyForm(forms.Form):
    name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        max_length=100,
        help_text='Name of the physical property')


class AddUnitForm(forms.Form):
    label = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        max_length=100,
        help_text='Label of the unit')


class AddSpaceGroupForm(forms.Form):
    name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_space_group_name'}),
        max_length=100,
        help_text='Name of space group') 


class AddDataForm(forms.Form):
    """Main form for submitting data."""

    # Where to redirect after successfully submitting data
    return_url = forms.CharField(required=False, widget=forms.HiddenInput())

    # General fields
    formula = AutoCharField(
        model=models.Compound,
        field='formula',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Chemical formula of the compound'
    )
    number_of_datasets = forms.IntegerField(
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control',
                                        'min': 1}),
        help_text=''
        'Enter the number of properties for this compound. '
        'For each property, a dataset is created. '
    )

    # Dataset (Property) level fields
    # General
    primary_property = forms.ModelChoiceField(
        required=False,
        queryset=models.Property.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text=''
        'Define the primary property of interest (in a figure, this typically '
        'denotes the y-axis). If the property of interest is missing here, '
        'add it under "Define new property".'
    )
    origin_of_data = forms.ChoiceField(
        required=False,
        initial='is_experimental',
        choices=(
            ('is_experimental', 'experimental'),
            ('is_theoretical', 'theoretical'),
        ),
        widget=forms.RadioSelect(),
        help_text=''
        'Select whether the origin of data is experimental or theoretical.'
    )
    sample_type = forms.ChoiceField(
        required=False,
        initial=models.Dataset.SAMPLE_TYPES[0],
        choices=(models.Dataset.SAMPLE_TYPES),
        widget=forms.RadioSelect(),
        help_text='Select the type of the sample.'
    )
    crystal_system = forms.ChoiceField(
        required=False,
#        initial=models.Subset.CRYSTAL_SYSTEMS[0],
        choices=(models.Dataset.CRYSTAL_SYSTEMS),
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Select the crystal system.'
    )  
    space_group = forms.ModelChoiceField(
        required=False,
        queryset=models.SpaceGroup.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Choose or add a space group.'
    )

    # Synthesis
    with_synthesis_details = forms.BooleanField(
        required=False, initial=False, widget=forms.HiddenInput())
    starting_materials = AutoCharField(
        model=models.SynthesisMethod, field='starting_materials',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Specify the starting materials.')
    product = AutoCharField(
        model=models.SynthesisMethod, field='product',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Specify the final product of synthesis.')
    synthesis_description = AutoCharField(
        label='Description',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': '3'}),
        help_text='Describe the steps of the synthesis process.')
    synthesis_comment = AutoCharField(
        label='Comments',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text=''
        'Additional information not revelant or suitable for the description '
        'part.')

    # Experimental
    with_experimental_details = forms.BooleanField(
        required=False, initial=False, widget=forms.HiddenInput())
    experimental_method = AutoCharField(
        label='Method',
        model=models.ExperimentalDetails, field='method',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Short name of the method used, e.g., "X-ray diffraction".')
    experimental_description = AutoCharField(
        label='Description',
        model=models.ExperimentalDetails, field='description',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': '3'}),
        help_text='Describe all experimental steps here.')
    experimental_comment = AutoCharField(
        label='Comments',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text=''
        'Additional information not revelant or suitable for the description '
        'part.')

    # Computational
    with_computational_details = forms.BooleanField(
        required=False, initial=False, widget=forms.HiddenInput())
    code = AutoCharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Abinit, Quantum espresso...',
        }),
        help_text=''
        'Name of the code(s) used for calculations. It is recommended to also '
        'include other identifiers such as version number, branch name, or '
        'even the commit number if applicable.')
    level_of_theory = AutoCharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder':
            'DFT, Hartree-Fock, tight-binding, empirical model...',
        }),
        help_text=''
        'Level of theory summarizes the collection of physical approximations '
        'used in the calculation. It gives an overall picture of the physics '
        'involved. Finer details of the level of theory such as the level of '
        'relativity should be filled separately.')
    xc_functional = AutoCharField(
        label='Exchange-correlation functional',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'PBE, PW91...',
        }),
        help_text=''
        'Level of approximation used to treat the electron-electron '
        'interaction.')
    k_point_grid = AutoCharField(
        label='K-point grid',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '3x3x3, 4x5x4 (Monkhorst-Pack)...',
        }),
        help_text=''
        'Details of the k-point mesh.')
    level_of_relativity = AutoCharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder':
            'non-relativistic, atomic ZORA with SOC, Koelling-Harmon...',
        }),
        help_text=''
        'Specify the level of relativity. Note that this also includes the '
        'description of spin-orbit coupling!')
    basis_set_definition = AutoCharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'JTH PAW, TM PP with semicore...',
        }),
        help_text=''
        'Details of the basis set or of the algorithms directly related to '
        'the basis set. For example, in case of a plane wave calculation, '
        'also include details of the pseudopotential here if applicable.')
    numerical_accuracy = AutoCharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder':
            'SCF tol. 1 meV/atom, Lebedev grids for angular integration...',
        }),
        help_text=''
        'Include all parameters here that describe the accuracy of the '
        'calculation (tolerance parameters for an SCF cycle, quality of '
        'integration grids, number of excited states included, ...).')
    external_repositories = AutoCharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder':
            'http://dx.doi.org/00.00000/NOMAD/2000.01.30-5 ...',
        }),
        help_text=''
        'Provide link(s) to external repositories such as NOMAD, which host '
        'additional data related to the data entered here.')
    computational_comment = AutoCharField(
        label='Comments',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text=''
        'Additional information not revelant or suitable for the description '
        'part.')

    # Subset level fields
    # General
    number_of_subsets = forms.IntegerField(
        required=False,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control mx-sm-3',
                                        'min': 1,
                                        'style': 'width:8em'}),
        help_text='Enter the number of data subgroups.')
    sub_title = AutoCharField(
        label='Title',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Enter the subset title. This will be the chart title.')
    with_additional_files = forms.BooleanField(
        required=False, initial=False, widget=forms.HiddenInput())
    additional_files = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'multiple': True}),
        help_text=''
        'Upload files containing anything that is relevant to the current '
        'data (input files to a calculation, image of the sample, ...). '
        'Multiple files can be selected here.')
    with_reference = forms.BooleanField(
        required=False, initial=False, widget=forms.HiddenInput())
    select_reference = forms.ModelChoiceField(
        required=False,
        queryset=models.Reference.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text=''
        'Select the reference that is associated with the inserted data. If '
        'the data is unpublished or no reference is applicable, leave empty.')
    # Property specific fields
    # Normal properties
    with_data_for_chart = forms.BooleanField(
        required=False, initial=False, widget=forms.HiddenInput())
    with_fixed_property = forms.BooleanField(
        required=False, initial=False, widget=forms.HiddenInput())
    number_of_curves = forms.IntegerField(
        required=False,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control mx-sm-3',
                                        'min': 1,
                                        'style': 'width:8em'}),
        help_text=''
        'Enter the number of curves in chart.'
        'This should equal to (number of columns of datapoints - 1).'
        )
    x_title = forms.CharField(
        required=False,
        label='x title',
        widget=forms.TextInput(
            attrs={'class': 'form-control'}),
        help_text='Enter x-axis title here.')
    x_unit = forms.CharField(
        required=False,
        label='x unit',
        widget=forms.TextInput(
            attrs={'class': 'form-control'}),
        help_text='Enter x-axis unit here.')
    y_title = forms.CharField(
        required=False,
        label="y title",
        widget=forms.TextInput(
            attrs={'class': 'form-control'}),
        help_text='Enter y-axis title here.')
    y_unit = forms.CharField(
        required=False,
        label='y unit',
        widget=forms.TextInput(
            attrs={'class': 'form-control'}),
        help_text='Enter y-axis unit here.')
    import_file_name = forms.CharField(
        required=False, widget=forms.HiddenInput())
    datapoints = forms.CharField(
        required=False,
        label='Data points',
        widget=forms.Textarea(
        attrs={'class': 'form-control datapoints', 'rows': '10',
               'placeholder': 'x y1 y2 ...'}),
        help_text=''
        'Insert data points here. The first column has value of x-axis'
        'and each of the following column corresponds to y-axis.')
    fixed_sign = forms.ChoiceField(
        required=False,
        label="Sign",
        choices=(models.FixedPropertyValue.VALUE_TYPES),
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Choose the sign.')

    # Atomic structure specific
    with_data_for_atomic_structure = forms.BooleanField(
        required=False, initial=False, widget=forms.HiddenInput())
    import_file_name_atomic = forms.CharField(
        required=False, widget=forms.HiddenInput())
    lattice_constant_a = forms.CharField(
        label='Lattice constants',
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'a'}),
        help_text=''
        'Units of lattice constants are given by "Primary unit" above. When '
        'importing from file, two formats are allowed. In the first format, '
        'include "a", "b", "c", "alpha", "beta", and "gamma" followed by '
        'their respective values. This can be either on one line or on '
        'separate lines (e.g., "a val1 b val2 ..."). For the second format, '
        'see the help text of "Atomic coordinates" below.')
    lattice_constant_b = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'b'})
    )
    lattice_constant_c = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'c'})
    )
    lattice_constant_alpha = forms.CharField(
        label='Angles (deg)',
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'α'})
    )
    lattice_constant_beta = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'β'})
        )
    lattice_constant_gamma = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'γ'})
    )
    placeholder_ = (
        '# Enter data here in any format\n# that JMol can read')
    atomic_coordinates = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={'class': 'form-control', 'rows': '10',
                   'placeholder': mark_safe(placeholder_)}),
        help_text=''
        'Enter atomic structure data in any format accepted by JMol. Note: to '
        'resize this box, drag from the corner.')
    geometry_format = forms.CharField(
        required=False, initial='aims', widget=forms.HiddenInput())
    

    # Tolerance factor related parameters
    # Shannon ironic radii
    element_I = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'element'})
        )
    charge_I = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'charge'})
        )
    coord_I = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'coordination'})
        )
    spin_state_I = forms.ChoiceField(
        required=False,
        initial=models.ShannonRadiiTable.SPIN_STATES[0],
        choices=(models.ShannonRadiiTable.SPIN_STATES),
        widget=forms.Select(attrs={'class': 'form-control'})
        )
    element_II = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'element'})
        )
    charge_II = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'charge'})
        )
    coord_II = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'coordination'})
        )
    spin_state_II = forms.ChoiceField(
        required=False,
        initial=models.ShannonRadiiTable.SPIN_STATES[0],
        choices=(models.ShannonRadiiTable.SPIN_STATES),
        widget=forms.Select(attrs={'class': 'form-control'})
        )
    element_IV = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'element'})
        )
    charge_IV = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'charge'})
        )
    coord_IV = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'coordination'})
        )
    spin_state_IV = forms.ChoiceField(
        required=False,
        initial=models.ShannonRadiiTable.SPIN_STATES[0],
        choices=(models.ShannonRadiiTable.SPIN_STATES),
        widget=forms.Select(attrs={'class': 'form-control'})
        )
    element_X = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'element'})
        )
    charge_X = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'charge'})
        )
    coord_X = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'coordination'})
        )
    spin_state_X = forms.ChoiceField(
        required=False,
        initial=models.ShannonRadiiTable.SPIN_STATES[0],
        choices=(models.ShannonRadiiTable.SPIN_STATES),
        widget=forms.Select(attrs={'class': 'form-control'})
        )

    # Experimental R
    element_I_X_a = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'element Ⅰ'})
        )
    element_I_X_b = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'element X'})
        )
    R_I_X = forms.FloatField(
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'R'})
        )
    element_II_X_a = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': "element Ⅱ,Ⅰ'"})
        )
    element_II_X_b = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'element X'})
        )
    R_II_X = forms.FloatField(
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'R'})
        )
    element_IV_X_a = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'element Ⅳ,Ⅴ'})
        )
    element_IV_X_b = AutoCharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'element X'})
        )
    R_IV_X = forms.FloatField(
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'R'})
        )

    # Qresp related
    qresp_fetch_url = forms.CharField(required=False,
                                      widget=forms.HiddenInput())
    qresp_chart_nr = forms.IntegerField(required=False,
                                        widget=forms.HiddenInput())
    qresp_search_url = forms.CharField(required=False,
                                       widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        """Dynamically add datasets and subsets."""
        super().__init__(*args, **kwargs)
        self.label_suffix = ''
        if args:
            for key, value in args[0].items():
                # Dataset level fields
                # General
                if key.startswith('primary_property_'):
                    self.fields[key] = forms.ModelChoiceField(
                        queryset=models.Property.objects.all(),
                        initial=value
                    )
                elif key.startswith('origin_of_data_'):
                    self.fields[key] = forms.ChoiceField(
                        initial=value,
                        choices=(
                            ('is_experimental', 'experimental'),
                            ('is_theoretical', 'theoretical'),
                        ),
                        widget=forms.RadioSelect()
                    )
                elif key.startswith('sample_type_'):
                    self.fields[key] = forms.ChoiceField(
                        initial=value,
                        choices=(models.Dataset.SAMPLE_TYPES),
                        widget=forms.RadioSelect()
                    )
                elif key.startswith('crystal_system_'):
                    self.fields[key] = forms.ChoiceField(
                        initial=value,
                        choices=(models.Dataset.CRYSTAL_SYSTEMS),
                        widget=forms.Select()
                    )
                elif key.startswith('space_group_'):
                    self.fields[key] = forms.ModelChoiceField(
                        queryset=models.SpaceGroup.objects.all(),
                        initial=value
                    )

                # Synthesis
                elif key.startswith('with_synthesis_details_'):
                    self.fields[key] = forms.BooleanField(
                        required=False, initial=value, widget=forms.HiddenInput())
                elif key.startswith('starting_materials_'):
                    self.fields[key] = AutoCharField(
                        model=models.SynthesisMethod, field='starting_materials',
                        initial=value,
                        widget=forms.TextInput()
                    )
                elif key.startswith('product_'):
                    self.fields[key] = AutoCharField(
                        model=models.SynthesisMethod, field='product',
                        initial=value,
                        widget=forms.TextInput()
                    )
                elif key.startswith('synthesis_description_'):
                    self.fields[key] = AutoCharField(
                        label='Description',
                        widget=forms.Textarea(),
                        initial=value
                    )
                elif key.startswith('synthesis_comment_'):
                    self.fields[key] = AutoCharField(
                        label='Comments',
                        widget=forms.TextInput(),
                        initial=value
                    )

                # Experimental
                elif key.startswith('with_experimental_details_'):
                    self.fields[key] = forms.BooleanField(
                        required=False, initial=value, widget=forms.HiddenInput())
                elif key.startswith('experimental_method_'):
                    self.fields[key] = AutoCharField(
                        label='Method',
                        model=models.ExperimentalDetails, field='method',
                        initial=value,
                        widget=forms.TextInput(),
                    )
                elif key.startswith('experimental_description_'):
                    self.fields[key] = AutoCharField(
                        label='Description',
                        model=models.ExperimentalDetails, field='description',
                        widget=forms.Textarea(),
                        initial=value
                    )
                elif key.startswith('experimental_comment_'):
                    self.fields[key] = AutoCharField(
                        label='Comments',
                        widget=forms.TextInput(),
                        initial=value
                    )

                # Computational
                elif key.startswith('with_computational_details_'):
                    self.fields[key] = forms.BooleanField(
                        required=False, initial=value, widget=forms.HiddenInput())
                elif key.startswith('code_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value
                    )
                elif key.startswith('level_of_theory_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value
                    )
                elif key.startswith('xc_functional_'):
                    self.fields[key] = AutoCharField(
                        label='Exchange-correlation functional',
                        widget=forms.TextInput(),
                        initial=value
                    )
                elif key.startswith('k_point_grid_'):
                    self.fields[key] = AutoCharField(
                        label='K-point grid',
                        widget=forms.TextInput(),
                        initial=value
                    )
                elif key.startswith('level_of_relativity_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value
                    )
                elif key.startswith('basis_set_definition_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value
                    )
                elif key.startswith('numerical_accuracy_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value
                    )
                elif key.startswith('external_repositories_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value
                    )
                elif key.startswith('computational_comment_'):
                    self.fields[key] = AutoCharField(
                        label='Comments',
                        widget=forms.TextInput(),
                        initial=value
                    )
                elif key.startswith('number_of_subsets_'):
                    self.fields[key] = forms.CharField(
                        initial=value,
                        widget=forms.NumberInput()
                    )


                # Subset level fields
                # General
                elif key.startswith('sub_title_'):
                    self.fields[key] = AutoCharField(
                        initial=value,
                        widget=forms.TextInput(),
                     )
                elif key.startswith('with_additonal_files_'):
                    self.fields[key] = forms.BooleanField(
                        required=False, 
                        initial=value, 
                        widget=forms.HiddenInput())
                elif key.startswith('additional_files_'):
                    self.fields[key] = forms.FileField(
                        required=False,
                        widget=forms.ClearableFileInput())
                elif key.startswith('with_reference_'):
                    self.fields[key] = forms.BooleanField(
                        required=False, 
                        initial=value, 
                        widget=forms.HiddenInput())
                elif key.startswith('select_reference_'):
                    self.fields[key] = forms.ModelChoiceField(
                        required=False,
                        queryset=models.Reference.objects.all(),
                        initial=value)
                # Normal primary properties
                # Data for chart
                elif key.startswith('with_data_for_chart_'):
                    self.fields[key] = forms.BooleanField(
                        required=False, 
                        initial=value, 
                        widget=forms.HiddenInput())
                elif key.startswith('x_title_'):
                    self.fields[key] = forms.CharField(
                        required=False,
                        initial=value)
                elif key.startswith('x_unit_'):
                    self.fields[key] = forms.CharField(
                        required=False,
                        initial=value)  
                elif key.startswith('y_title_'):
                    self.fields[key] = forms.CharField(
                        required=False,
                        initial=value)
                elif key.startswith('y_unit_'):
                    self.fields[key] = forms.CharField(
                        required=False,
                        initial=value)
                elif key.startswith('number_of_curves_'):
                    self.fields[key] = forms.CharField(
                        required=False,
                        initial=value,
                        widget=forms.NumberInput())
                elif key.startswith('legend_'):
                    self.fields[key] = forms.CharField(
                        required=False,
                        initial=value)
                elif key.startswith('import_file_name_'):
                    self.fields[key] = forms.CharField(
                        required=False,
                        initial=value,
                        widget=forms.HiddenInput())
                elif key.startswith('datapoints_'):
                    self.fields[key] = forms.CharField(
                        required=False, widget=forms.Textarea, initial=value)
                # Fixed properties
                elif key.startswith('with_fixed_property_'):
                    self.fields[key] = forms.BooleanField(
                        required=False, 
                        initial=value, 
                        widget=forms.HiddenInput())
                elif key.startswith('fixed_property_'):
                    self.fields[key] = forms.ModelChoiceField(
                        queryset=models.Property.objects.all(), initial=value)
                elif key.startswith('fixed_unit_'):
                    self.fields[key] = forms.ModelChoiceField(
                        queryset=models.Unit.objects.all(),
                        initial=value,
                        required=False)
                elif key.startswith('fixed_sign_'):
                    self.fields[key] = forms.ChoiceField(
                        required=False,
                        label="Sign",
                        initial=value,
                        choices=(models.FixedPropertyValue.VALUE_TYPES),
                        widget=forms.Select())
                elif key.startswith('fixed_value_'):
                    self.fields[key] = forms.CharField(initial=value)
                # Data for atomic structure
                elif key.startswith('with_data_for_atomic_structure_'):
                    self.fields[key] = forms.BooleanField(
                        required=False, 
                        initial=False, 
                        widget=forms.HiddenInput())
                elif key.startswith('import_file_name_atomic_'):
                    self.fields[key] = forms.CharField(
                        required=False,
                        initial=value,
                        widget=forms.HiddenInput())
                elif key.startswith('lattice_constant_'):
                    self.fields[key] = forms.CharField(required=False,
                                                       initial=value)
                elif key.startswith('atomic_coordinates_'):
                    self.fields[key] = forms.CharField(
                        required=False, widget=forms.Textarea, initial=value)
                elif key.startswith('geometry_format_'):
                    self.fields[key] = forms.CharField(
                        required=False,
                        widget=forms.HiddenInput(),
                        initial=value)

                # Tolerance factor related parameters
                # Shannon ironic radii
                elif key.startswith('element_I_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value)
                elif key.startswith('charge_I_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value)
                elif key.startswith('coord_I_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value)
                elif key.startswith('spin_state_I_'):
                    self.fields[key] = models.ChoiceField(
                        initial=value,
                        choices=(models.ShannonIonicRadii.SPIN_STATES),
                        widget=forms.Select())
                elif key.startswith('element_II_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value)
                elif key.startswith('charge_II_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value)
                elif key.startswith('coord_II_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value)
                elif key.startswith('spin_state_II_'):
                    self.fields[key] = models.ChoiceField(
                        initial=value,
                        choices=(models.ShannonIonicRadii.SPIN_STATES),
                        widget=forms.Select())
                elif key.startswith('element_IV_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value)
                elif key.startswith('charge_IV_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value)
                elif key.startswith('coord_IV_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value)
                elif key.startswith('spin_state_IV_'):
                    self.fields[key] = models.ChoiceField(
                        initial=value,
                        choices=(models.ShannonIonicRadii.SPIN_STATES),
                        widget=forms.Select())
                elif key.startswith('element_X_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value)
                elif key.startswith('charge_X_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value)
                elif key.startswith('coord_X_'):
                    self.fields[key] = AutoCharField(
                        widget=forms.TextInput(),
                        initial=value)
                elif key.startswith('spin_state_X_'):
                    self.fields[key] = models.ChoiceField(
                        initial=value,
                        choices=(models.ShannonIonicRadii.SPIN_STATES),
                        widget=forms.Select())
                # Experimental bond length
                elif key.startswith('element_I_X_a_'):
                        self.fields[key] = AutoCharField(
                            widget=forms.TextInput(),
                            initial=value)
                elif key.startswith('element_I_X_b_'):
                        self.fields[key] = AutoCharField(
                            widget=forms.TextInput(),
                            initial=value)
                elif key.startswith('R_I_X_'):
                        self.fields[key] = AutoCharField(
                            widget=forms.TextInput(),
                            initial=value)
                elif key.startswith('element_II_X_a_'):
                        self.fields[key] = AutoCharField(
                            widget=forms.TextInput(),
                            initial=value)
                elif key.startswith('element_II_X_b_'):
                        self.fields[key] = AutoCharField(
                            widget=forms.TextInput(),
                            initial=value)
                elif key.startswith('R_II_X_'):
                        self.fields[key] = AutoCharField(
                            widget=forms.TextInput(),
                            initial=value)
                elif key.startswith('element_IV_X_a_'):
                        self.fields[key] = AutoCharField(
                            widget=forms.TextInput(),
                            initial=value)
                elif key.startswith('element_IV_X_b_'):
                        self.fields[key] = AutoCharField(
                            widget=forms.TextInput(),
                            initial=value)
                elif key.startswith('R_IV_X_'):
                        self.fields[key] = AutoCharField(
                            widget=forms.TextInput(),
                            initial=value)
                elif key.startswith('update_comments_'):
                    self.fields[key] = AutoCharField(
                            widget=forms.TextInput(),
                            initial=value)
                


#     def clean(self):
#         """Set secondary property conditionally required."""
#         data = self.cleaned_data
#         if data.get('two_axes') and not data.get('secondary_property'):
#             self.add_error('secondary_property', 'This field is required.')
#         if not all(map(lambda x: x.isdigit(),
#                        data.get('related_data_sets').split())):
#             self.add_error('related_data_sets',
#                            'This must be a list of space separated integers.')

    def get_dataset(self):
        """Return a list of initial values for dataset."""
        results = []   
        for field in self.fields:
            if field.split('_')[-1].isnumeric() and (not field.split('_')[-2].isnumeric()):
                results.append([field.split('_')[-1], field, self.fields[field].initial])
        # results.sort(key=lambda x: x[0].split['_'][-1])
        return results


    def get_subset(self):
        """Return a list of initial values for data subset.
        Handle legends, reference, fixed property and bond length separtely in functions below.
        """
        results = []
        for field in self.fields:
            if len(field.split('_')) > 2 and field.split('_')[-1].isnumeric() and field.split('_')[-2].isnumeric()\
            and (not field.split('_')[-3].isnumeric()) and 'select_reference_' not in field and 'additional_files_' not in field:
                results.append([field.split('_')[-2], 
                                field.split('_')[-1],
                                field,
                                self.fields[field].initial])
        return results
    

    def get_reference(self):
        """Return selected reference in a list of list."""
        field_list = [field for field in self.fields if field.startswith('select_reference_')]
        field_list.sort(key=lambda x: (x.split('_')[-2], x.split('_')[-1]))
        results = {}
        for field in field_list:
            i_dataset = field.split('_')[-2]
            if i_dataset not in results:
                results[i_dataset] = [self.fields[field].initial]
            else:
                results[i_dataset].append(self.fields[field].initial)
        results_list = [[k, v] for k, v in results.items()]
        results_list.sort(key=lambda x: x[0])
        return [v for k, v in results_list]


    def get_legends(self):
        """Return a list of legends"""
        results = []
        for field in self.fields:
            if field.startswith('legend_'):
                results.append([field, self.fields[field].initial])
        return results


    def get_fixed_properties(self):
        """Return a list of fixed properties and their current values."""
        results = []
        for field in self.fields:
            if field.startswith('fixed_property_'):
                suffix = field.split('fixed_property_')[1]
                i_dataset, i_subset, counter = suffix.split('_')
                results.append([i_dataset, i_subset, counter,
                                self.fields[field].initial,
                                self.fields[f'fixed_unit_{suffix}'].initial,
                                self.fields[f'fixed_sign_{suffix}'].initial,
                                self.fields[f'fixed_value_{suffix}'].initial])
        return results

