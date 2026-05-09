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
        return HttpResponse(status=422, content=f"Errore: CSV doesn't have value in this columns: {colonne_con_nan}")
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
        return HttpResponse(status=422, content=f"Errore: CSV doesn't have a correct time column")

    if not _is_step(csv_data, time_column):
        return HttpResponse(status=422, content=f"Errore: time column isn't in constant step")
    time_step = csv_data[time_column][1]

    if csv_data[voltage_column][len(csv_data[voltage_column]) - 1] != 0:
        return HttpResponse(status=422, content=f"Errore: voltage column last value isn't 0")

    curve = _get_curve(csv_data, voltage_column, time_column)
    rects, result = _rectangle_method(csv_data, time_step, voltage_column, time_column)
    context = {'curve': json.dumps(curve),
               'result': result,
               'rects': json.dumps(rects),}

    return render(request, "calcolatore/chart.html", context)

def _is_step(data_frame, time_column):
    step_atteso = data_frame[time_column][1]
    differenze = data_frame[time_column].diff().dropna()

    # 3. Controlliamo se tutte le differenze sono uguali allo step atteso
    # Usiamo un margine di errore minimo (tol) se lavoriamo con float,
    # per gli interi il confronto diretto == è perfetto.
    confronto_bool = np.isclose(differenze, step_atteso)
    valido = confronto_bool.all()
    return valido

def _get_curve(data_frame, voltage_column, time_column):
    return [[data_frame[time_column][i], data_frame[voltage_column][i]] for i in range(len(data_frame[time_column]))]

def _rectangle_method(data_frame, time_step, voltage_column, time_column):
    n = len(data_frame[time_column]) - 1
    rects = [[data_frame[time_column][i], data_frame[time_column][i+1], data_frame[voltage_column][i]] for i in range(n)]
    totale_voltaggio = data_frame[voltage_column].sum()
    return rects, time_step * totale_voltaggio

