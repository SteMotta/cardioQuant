import io
import json
from itertools import groupby
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
import pandas as pd
from django.views.decorators.http import require_POST, require_GET, require_http_methods
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
        for day, items in groupby(datasets, key=lambda d: timezone.localtime(d.created_at).date())
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
        csv_data = pd.read_csv(io.BytesIO(csv_file), on_bad_lines='error', sep=";", decimal=",")
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
               'calc_id': calc.id,
               'v_max': calc.v_max
               }
        else:
            return HttpResponse(status=403, content="Error: not authorized")
    else:
        csv_file = request.FILES['csv_file'].read()
        csv_checked = _csv_check(csv_file)
        if isinstance(csv_checked, HttpResponse):
            return csv_checked
        csv_data, time_column, voltage_column, time_step = csv_checked

        curve, v_max = _get_curve(csv_data, voltage_column, time_column)
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
                result_simpson = simpson_result,
                v_max = v_max,
            )
            status = 201

        context = {'curve': json.dumps(curve),
                   'rects_result': rects_result,
                   'rects': json.dumps(rects),
                   'trapezius_result': trapezius_result,
                   'trapezius': json.dumps(trapezius),
                   'simpson_result': simpson_result,
                   'simpson': json.dumps(simpson),
                   'requested_method': request.POST.get('integral_type'),
                   'v_max': v_max,
               }

    response = render(request, "calculator/chart.html", context, status=status)
    average = _get_average_result(context['rects_result'], context['trapezius_result'], context['simpson_result'])
    response['X-Average'] = average

    return response


@require_POST
def calculate_example(request):
    path = settings.BASE_DIR / 'calculator' / 'data' / 'ecg_example.csv'
    csv_data = pd.read_csv(path)
    time_column, voltage_column  = _get_columns(csv_data)
    time_step = _get_time_step(csv_data, time_column)
    curve, v_max = _get_curve(csv_data, voltage_column, time_column)
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
               'requested_method': request.POST.get('integral_type'),
               'v_max': v_max,
               }

    response = render(request, "calculator/chart.html", context)
    average = _get_average_result(context['rects_result'], context['trapezius_result'], context['simpson_result'])
    response['X-Average'] = average

    return response

@login_required
@require_http_methods(['DELETE'])
def delete_dataset(request, pk):
    dataset = get_object_or_404(Dataset, pk=pk, user=request.user)
    dataset.delete()
    response = HttpResponse(status=204)
    response['HX-Trigger'] = 'delete-collapse'
    return response

@login_required
@require_POST
def update_dataset(request, calc_id):
    dataset = get_object_or_404(Dataset, id=calc_id, user=request.user)

    try:
        voltage_values = json.loads(request.POST.get('voltage_values', '[]'))
        integral_type = request.POST.get('integral_type', 'Rectangles')
    except json.JSONDecodeError:
        return HttpResponse("Error: Invalid data", status=400)

    # Tempi immutabili: li prende direttamente dal database
    time_values = dataset.time_values

    if len(voltage_values) != len(dataset.voltage_values):
        return HttpResponse("Error: Cannot add or remove values", status=422)

    try:
        T = np.array(time_values, dtype=float)
        V = np.array(voltage_values, dtype=float)
    except (TypeError, ValueError):
        return HttpResponse("Error: All values must be numeric", status=422)

    mV_max = 10.0  # mV

    if np.any(V > mV_max):
        return HttpResponse(f"Error: Voltage values cannot exceed {mV_max} mV", status=422)

    # Controlli solo su V, T è già validato
    if np.any(V < 0):
        return HttpResponse("Error: Values cannot be negative", status=422)

    if V[-1] != 0:
        return HttpResponse("Error: Last voltage value must be 0", status=422)

    h = dataset.step

    dataset.time_values    = T.tolist()
    dataset.voltage_values = V.tolist()
    dataset.is_modified = True
    dataset.save()

    df = pd.DataFrame({'time': time_values, 'voltage': voltage_values})
    curve, v_max = _get_curve(df, 'voltage', 'time')
    rects,  rects_result  = _rectangle_method(df, h, 'voltage', 'time')
    traps,  traps_result  = _trapezius_method(df, h, 'voltage', 'time')
    simps,  simps_result  = _simpson_method(df, h, 'voltage', 'time')

    calc = dataset.calculation
    calc.curve = curve
    calc.v_max = v_max
    calc.rects = rects
    calc.trapezius = traps
    calc.simpson = simps
    calc.result_rectangles = rects_result
    calc.result_trapezius  = traps_result
    calc.result_simpson    = simps_result
    calc.save()

    context = {
        'calc_id':          calc.id,
        'rects':            json.dumps(rects),
        'trapezius':        json.dumps(traps),
        'simpson':          json.dumps(simps),
        'curve':            json.dumps(curve),
        'rects_result':     rects_result,
        'trapezius_result': traps_result,
        'simpson_result':   simps_result,
        'v_max':            v_max,
        'requested_method': integral_type,
    }
    response = render(request, 'calculator/chart.html', context)
    response['X-Average'] = str(round((rects_result + traps_result + simps_result) / 3, 4))
    response['X-Dataset-Updated'] = 'true'
    return response

def _is_step_list(time_values: list, tol: float = 1e-9) -> bool:
    t = np.array(time_values)
    if len(t) < 2:
        return False
    diffs = np.diff(t)
    return bool(np.all(np.abs(diffs - diffs[0]) < tol))

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
    T = csv_data[time_column].to_numpy()
    V = csv_data[voltage_column].to_numpy()
    return np.column_stack([T, V]).tolist(), float(V.max())

def _rectangle_method(csv_data, time_step, voltage_column, time_column):
    T = csv_data[time_column].to_numpy()
    V = csv_data[voltage_column].to_numpy()
    rects  = np.column_stack([T[:-1], T[1:], V[:-1]]).tolist()
    # Regola sinistra: somma solo V[0..n-1], non V[n]
    result = time_step * V[:-1].sum()
    return rects, result

def _trapezius_method(csv_data, time_step, voltage_column, time_column):
    T = csv_data[time_column].to_numpy()
    V = csv_data[voltage_column].to_numpy()
    traps  = np.column_stack([T[:-1], T[1:], V[:-1], V[1:]]).tolist()
    # Formula corretta: h/2 * (V[0] + 2*V[1..n-1] + V[n])
    result = time_step / 2 * (V[0] + 2 * V[1:-1].sum() + V[-1])
    return traps, result

def _simpson_method(csv_data, time_step, voltage_column, time_column):
    T = csv_data[time_column].to_numpy()
    V = csv_data[voltage_column].to_numpy()
    simpson = np.column_stack([T[0:-2:2], T[1:-1:2], T[2::2],
                               V[0:-2:2], V[1:-1:2], V[2::2]]).tolist()
    # Formula corretta: h/3 * (V[0] + 4*dispari + 2*pari_interni + V[n])
    result = time_step / 3 * (V[0] + 4 * V[1:-1:2].sum() + 2 * V[2:-2:2].sum() + V[-1])
    return simpson, result

def _get_average_result(rects_result, traps_result, simpson_result):
    return round(np.mean([rects_result, traps_result, simpson_result]), 4)