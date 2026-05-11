import io
import json
from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
import pandas as pd
from django.views.decorators.http import require_POST, require_GET
from django.conf import settings
from django.http import HttpResponse
import numpy as np
from calculator.models import Dataset, Calculation

def index(request):
    return render(request, "calculator/index.html")

def example(request):
    return render(request, "calculator/example.html")

@login_required
def dashboard(request):
    datasets = Dataset.objects.filter(user=request.user).order_by('-created_at')
    grouped = [
        (day, list(items))
        for day, items in groupby(datasets, key=lambda d: d.created_at.date())
    ]
    context = { 'grouped': grouped }

    return render(request, "calculator/dashboard.html", context)

def _get_columns(csv_data):
    time_column = ""
    voltage_column = ""
    counter = 0
    for i, colonna in enumerate(csv_data.columns):
        if not csv_data[colonna].is_monotonic_increasing:
            counter += 1
        else:
            time_column = colonna
            voltage_column = csv_data.columns[0] if i == 1 else csv_data.columns[1]

    return [time_column, voltage_column] if counter == 1 else None

def _get_time_step(csv_data, time_column):
    return csv_data[time_column][1]

def _csv_check(csv_file):
    try:
        csv_data = pd.read_csv(io.BytesIO(csv_file), on_bad_lines='error')
    except pd.errors.ParserError:
        return HttpResponse(status=422, content="Error: CSV file not valid")
    if csv_data.empty:
        return HttpResponse(status=422, content="Error: CSV file empty")
    if len(csv_data.columns) != 2:
        return HttpResponse(status=422, content="Error: Number of columns not equal to 2")
    if csv_data.isnull().values.any():
        # Opzionale: puoi identificare dove sono gli errori
        colonne_con_nan = csv_data.columns[csv_data.isnull().any()].tolist()
        return HttpResponse(status=422, content=f"Error: CSV doesn't have value in this columns: {colonne_con_nan}")
    if len(csv_data.columns[0]) < 2:
        return HttpResponse(status=422, content="Error: Number of rows not greater than 1")

    for column in csv_data.columns:
        csv_data[column] = pd.to_numeric(csv_data[column], errors='coerce')

    if not (csv_data >= 0).all().all():
        return HttpResponse(status=422, content=f"Error: CSV has negative values")

    time_column = ""
    voltage_column = ""
    counter = 0
    for i, colonna in enumerate(csv_data.columns):
        if not csv_data[colonna].is_monotonic_increasing:
            counter += 1
        else:
            time_column = colonna
            voltage_column = csv_data.columns[0] if i == 1 else csv_data.columns[1]

    if counter == 2 or counter == 0:
        return HttpResponse(status=422, content=f"Error: CSV doesn't have a valid time column")

    if not _is_step(csv_data, time_column):
        return HttpResponse(status=422, content=f"Error: time column isn't in constant step")
    time_step = csv_data[time_column][1]

    if csv_data[voltage_column][len(csv_data[voltage_column]) - 1] != 0:
        return HttpResponse(status=422, content=f"Error: voltage column last value isn't 0")

    return [csv_data, time_column, voltage_column, time_step]
@require_POST
def calculate(request, pk=None):
    context = {}
    status = 200

    if pk:
        if request.user.is_authenticated:
            calc = Calculation.objects.get(dataset=pk)
            context = {'curve': json.dumps(calc.curve),
               'rects_result': calc.result_rectangles,
               'rects': json.dumps(calc.rects),
               'trapezius_result': calc.result_trapezius,
               'trapezius': json.dumps(calc.trapezius),
               'simpson_result': calc.result_simpson,
               'simpson': json.dumps(calc.simpson),
               'requested_method': request.POST.get('integral_type'),
               'calc_id': calc.id
               }
        else:
            return HttpResponse(status=403, content="Error: not authorized")
    else:
        csv_file = request.FILES['csv_file'].read()
        csv_checked = _csv_check(csv_file)
        if isinstance(csv_checked, HttpResponse):
            return csv_checked
        csv_data, time_column, voltage_column, time_step = csv_checked

        curve = _get_curve(csv_data, voltage_column, time_column)
        rects, rects_result = _rectangle_method(csv_data, time_step, voltage_column, time_column)
        trapezius, trapezius_result = _trapezius_method(csv_data, time_step, voltage_column, time_column)
        simpson, simpson_result = _simpson_method(csv_data, time_step, voltage_column, time_column)

        if request.user.is_authenticated:
            duplicato = Dataset.objects.filter(
                user=request.user,
                step=time_step,
                time_values=csv_data[time_column].tolist(),
                voltage_values=csv_data[voltage_column].tolist()
            ).exists()
            if duplicato:
                return HttpResponse(status=409, content=f"Error: Dataset already exists")
            dataset = Dataset.objects.create(
                user = request.user,
                csv_name = request.FILES['csv_file'].name,
                step = time_step,
                time_values = csv_data[time_column].tolist(),
                voltage_values = csv_data[voltage_column].tolist()
            )
            Calculation.objects.create(
                dataset=dataset,
                curve = curve,
                rects = rects,
                trapezius = trapezius,
                simpson = simpson,
                result_rectangles = rects_result,
                result_trapezius = trapezius_result,
                result_simpson = simpson_result
            )
            status = 201

        context = {'curve': json.dumps(curve),
                   'rects_result': rects_result,
                   'rects': json.dumps(rects),
                   'trapezius_result': trapezius_result,
                   'trapezius': json.dumps(trapezius),
                   'simpson_result': simpson_result,
                   'simpson': json.dumps(simpson),
                   'requested_method': request.POST.get('integral_type')
               }
    return render(request, "calculator/chart.html", context, status=status)

@require_POST
def calculate_example(request):
    path = settings.BASE_DIR / 'calculator' / 'data' / 'ecg_example.csv'
    csv_data = pd.read_csv(path)
    time_column, voltage_column  = _get_columns(csv_data)
    time_step = _get_time_step(csv_data, time_column)
    curve = _get_curve(csv_data, voltage_column, time_column)
    rects, rects_result = _rectangle_method(csv_data, time_step, voltage_column, time_column)
    trapezius, trapezius_result = _trapezius_method(csv_data, time_step, voltage_column, time_column)
    simpson, simpson_result = _simpson_method(csv_data, time_step, voltage_column, time_column)

    context = {'curve': json.dumps(curve),
               'rects_result': rects_result,
               'rects': json.dumps(rects),
               'trapezius_result': trapezius_result,
               'trapezius': json.dumps(trapezius),
               'simpson_result': simpson_result,
               'simpson': json.dumps(simpson),
               'requested_method': request.POST.get('integral_type')
               }

    return render(request, "calculator/chart.html", context)

def _is_step(data_frame, time_column):
    step = data_frame[time_column][1]
    difference = data_frame[time_column].diff().dropna()

    # 3. Controlliamo se tutte le differenze sono uguali allo step atteso
    # Usiamo un margine di errore minimo (tol) se lavoriamo con float,
    # per gli interi il confronto diretto == è perfetto.
    confronto_bool = np.isclose(difference, step)
    valid = confronto_bool.all()
    return valid

def _get_curve(csv_data, voltage_column, time_column):
    return [[csv_data[time_column][i], csv_data[voltage_column][i]] for i in range(len(csv_data[time_column]))]

def _rectangle_method(csv_data, time_step, voltage_column, time_column):
    n = len(csv_data[time_column]) - 1
    rects = [[csv_data[time_column][i], csv_data[time_column][i + 1], csv_data[voltage_column][i]] for i in range(n)]
    voltage_total = csv_data[voltage_column].sum()
    return rects, time_step * voltage_total

def _trapezius_method(csv_data, time_step, voltage_column, time_column):
    n = len(csv_data[time_column]) - 1
    traps = [[csv_data[time_column][i], csv_data[time_column][i + 1], csv_data[voltage_column][i], csv_data[voltage_column][i + 1]] for i in range(n)]
    voltage_total = csv_data[voltage_column].sum()
    return traps, time_step/2 * (2*voltage_total)

def _simpson_method(csv_data, time_step, voltage_column, time_column):
    n = len(csv_data[time_column]) - 1
    simpson = [[csv_data[time_column][i], csv_data[time_column][i + 1], csv_data[time_column][i + 2], csv_data[voltage_column][i], csv_data[voltage_column][i + 1], csv_data[voltage_column][i + 2]] for i in range(0, n, 2)]
    even_voltage_total = 0
    for i in range(0, n, 2):
        even_voltage_total += csv_data[voltage_column][i]
    odd_voltage_total = 0
    for i in range(1, n, 2):
        odd_voltage_total += csv_data[voltage_column][i]
    return simpson, time_step/3 * (2*even_voltage_total + 4*odd_voltage_total)
