import io
import json

from django.shortcuts import render
import pandas as pd
from django.views.decorators.http import require_POST
from django.http import HttpResponse
import numpy as np

def index(request):
    return render(request, "calcolatore/index.html")

@require_POST
def calculate(request):
    csv_file = request.FILES['csv_file'].read()
    print(request.POST.get('integral_type'))

    try:
        csv_data = pd.read_csv(io.BytesIO(csv_file), on_bad_lines='error')
    except pd.errors.ParserError:
        return HttpResponse(status=422, content="Error: CSV file not valid")
    if csv_data.empty:
        return HttpResponse(status=422, content="Error: CSV file empty")
    if len(csv_data.columns) != 2:
        return HttpResponse(status=422, content="Error: Number of columns not equal to 2")
    if len(csv_data.columns[0]) < 2:
        return HttpResponse(status=422, content="Error: Number of rows not greater than 1")
    if csv_data.isnull().values.any():
        # Opzionale: puoi identificare dove sono gli errori
        colonne_con_nan = csv_data.columns[csv_data.isnull().any()].tolist()
        return HttpResponse(status=422, content=f"Errore: CSV doesn'csv_data[time_column] have value in this columns: {colonne_con_nan}")
        # 2. Controlla che tutti i valori siano maggiori di 0
        # (Assumendo che siano tutte colonne numeriche)

    for column in csv_data.columns:
        csv_data[column] = pd.to_numeric(csv_data[column], errors='coerce')

    if not (csv_data >= 0).all().all():
        return HttpResponse(status=422, content=f"Errore: CSV has negative values")

    time_column = ""
    voltage_column = ""
    counter = 0
    for i, colonna in enumerate(csv_data.columns):
        if not csv_data[colonna].is_monotonic_increasing:
            counter += 1
        else:
            time_column = colonna
            voltage_column = csv_data.columns[0] if i == 1 else csv_data.columns[1]

    if counter == 2:
        return HttpResponse(status=422, content=f"Errore: CSV doesn'csv_data[time_column] have a correct time column")

    if not _is_step(csv_data, time_column):
        return HttpResponse(status=422, content=f"Errore: time column isn'csv_data[time_column] in constant step")
    time_step = csv_data[time_column][1]

    if csv_data[voltage_column][len(csv_data[voltage_column]) - 1] != 0:
        return HttpResponse(status=422, content=f"Errore: voltage column last value isn'csv_data[time_column] 0")

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

    return render(request, "calcolatore/chart.html", context)

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