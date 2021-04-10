# This file is covered by the BSD license. See LICENSE in the root directory.
"""Helper functions for this project."""
import io
import matplotlib
import numpy
import re

from django.core.files.uploadedfile import SimpleUploadedFile

from . import models

matplotlib.use('Agg')  # noqa

from matplotlib import pyplot


def atomic_coordinates_as_json(pk):
    """Get atomic coordinates from database."""
    subset = models.Subset.objects.get(pk=pk)
    vectors = models.NumericalValue.objects.filter(
        datapoint__subset=subset).filter(
            datapoint__symbols__isnull=True).order_by(
                'datapoint_id', 'counter')
    data = {'vectors':
            [[x.formatted('.10g') for x in vectors[:3]],
             [x.formatted('.10g') for x in vectors[3:6]],
             [x.formatted('.10g') for x in vectors[6:9]]]}
    # Here counter=1 filters out the first six entries
    symbols = models.Symbol.objects.filter(
        datapoint__subset=subset).filter(counter=1).order_by(
            'datapoint_id').values_list('value', flat=True)
    coords = models.NumericalValue.objects.filter(
        datapoint__subset=subset).filter(
            datapoint__symbols__counter=1).select_related('error').order_by(
                'counter', 'datapoint_id')
    tmp = models.Symbol.objects.filter(
        datapoint__subset=subset).annotate(
            num=models.models.Count('datapoint__symbols')).filter(
                num=2).first()
    if tmp:
        data['coord-type'] = tmp.value
    data['coordinates'] = []
    N = int(len(coords)/3)
    for symbol, coord_x, coord_y, coord_z in zip(
            symbols, coords[:N], coords[N:2*N], coords[2*N:3*N]):
        data['coordinates'].append((symbol,
                                    coord_x.formatted('.9g'),
                                    coord_y.formatted('.9g'),
                                    coord_z.formatted('.9g')))
    return data


def dataset_info(dataset, server):
    """Return the data set contents as human-readable plain text."""
    data = io.StringIO()
    data.write(
        f'Data available at {server}/materials/dataset/{dataset.pk}\n')
    data.write('\n')
    if dataset.reference:
        ref = dataset.reference
        data.write(f'Reference: {ref.getAuthorsAsString()} "{ref.title}", '
                   f'{ref.journal} {ref.vol}')
        if ref.pages_start:
            data.write(f', {ref.pages_start} ')
        data.write(f' ({ref.year})\n')
        data.write('\n')
    data.write(
        'Origin: '
        f'{"experimental" if dataset.experimental else "theoretical"}\n')
    data.write(f'Dimensionality: {dataset.dimensionality}D\n')
    sample = models.Dataset.SAMPLE_TYPES[dataset.sample_type][1]
    data.write(f'Sample type: {sample}\n')
    data.write('\n')
    if dataset.secondary_property:
        data.write(f'Column 1: {dataset.secondary_property}')
        if dataset.secondary_unit:
            data.write(f', {dataset.secondary_unit}')
        data.write('\n')
        data.write('Column 2: ')
    else:
        data.write('Physical property: ')
    data.write(dataset.primary_property.name)
    if dataset.primary_unit:
        data.write(f', {dataset.primary_unit}')
    data.write('\n\n')
    for subset in dataset.subsets.all():
        if subset.label:
            data.write(f'{subset.label}\n')
        fixed_values = subset.fixed_values.all()
        if fixed_values:
            data.write('Fixed parameters:\n')
        for v in fixed_values:
            data.write(f'  {v.physical_property} = {v.value} {v.unit}\n')
        if dataset.primary_property.name == 'atomic structure':
            for symbol, value, unit in subset.get_lattice_constants():
                data.write(f'{symbol} {value}{unit}\n')
        elif dataset.primary_property.name.startswith('phase transition '):
            pt = subset.phase_transitions.first()
            CS = models.Subset.CRYSTAL_SYSTEMS
            data.write('Initial crystal system: '
                       f'{CS[subset.crystal_system][1]}\n')
            if pt.crystal_system_final:
                data.write('Final crystal system: '
                           f'{CS[pt.crystal_system_final][1]}\n')
            if pt.space_group_initial:
                data.write(f'Space group initial: {pt.space_group_initial}\n')
            if pt.space_group_final:
                data.write(f'Space group final: {pt.space_group_final}\n')
            if pt.direction:
                data.write(f'Direction: {pt.direction}\n')
            if pt.hysteresis:
                data.write(f'Hysteresis: {pt.hysteresis}\n')
            data.write(f'Value: {pt.formatted()}\n')
        data.write('\n\n')
    return data.getvalue()
