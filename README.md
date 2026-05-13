# CardioQuant

**CardioQuant** is a web application for numerical integration of ECG (electrocardiogram) signals. It allows users to upload CSV files containing time–voltage data, compute the area under the curve using three different numerical methods, and visualise the results interactively. Authenticated users can save and revisit past calculations from a personal dashboard, **edit voltage values** and recompute integrals on the fly. After each computation the app provides **clinical feedback** indicating whether the ECG integral falls within a physiological range.

---

## Table of Contents

- [Purpose](#purpose)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Core Features](#core-features)
- [Data Model](#data-model)
- [URL Routes](#url-routes)
- [Numerical Methods](#numerical-methods)
- [Authentication](#authentication)
- [Frontend & UI](#frontend--ui)
- [Deployment](#deployment)
- [Getting Started (Local Development)](#getting-started-local-development)

---

## Purpose

CardioQuant computes the **integral of an ECG signal** — i.e., the area under a voltage–time curve — using three classical numerical integration methods:

| Method       | Description                                        |
|--------------|----------------------------------------------------|
| Rectangles   | Left-endpoint Riemann sum                          |
| Trapezius    | Trapezoidal rule                                   |
| Simpson      | Simpson's 1/3 rule (parabolic approximation)       |

The result is expressed in **mV·s** (millivolt-seconds) and is visualised alongside the ECG curve in an interactive chart, with the corresponding mathematical formula rendered in LaTeX.

---

## Tech Stack

### Backend

| Technology | Version | Role |
|---|---|---|
| **Python** | 3.x | Runtime language |
| **Django** | 6.0.4 | Web framework (MVT pattern) |
| **pandas** | 3.0.2 | CSV parsing and data validation |
| **NumPy** | 2.4.4 | Vectorised numerical operations (integration, `np.isclose`) |
| **SQLite** | — | Default database (`db.sqlite3`) |
| **Gunicorn** | 26.0.0 | WSGI server for production |
| **Whitenoise** | 6.12.0 | Static file serving in production |
| **django-allauth** | 65.16.1 | Authentication (email + Google OAuth2) |
| **django-htmx** | 1.27.0 | HTMX middleware integration |
| **django-extensions** | 4.1 | Development utilities |
| **PyJWT** | 2.12.1 | JWT token support |
| **python-dotenv** | 1.2.2 | Loads environment variables from `.env` file |

### Frontend

| Technology | Role |
|---|---|
| **Tailwind CSS** (via `django-tailwind`) | Utility-first CSS framework |
| **DaisyUI** | Tailwind component library (Nord theme) |
| **HTMX** | Partial page updates without full reloads |
| **Alpine.js** | Lightweight client-side reactivity |
| **Apache ECharts 5** | Interactive chart rendering (with DataZoom) |
| **MathJax 3** | LaTeX formula rendering in the browser |

---

## Project Structure

```
cardioQuant/
├── manage.py                    # Django CLI entry point (loads .env via python-dotenv)
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables (not committed)
├── db.sqlite3                   # SQLite database
│
├── cardioQuant/                 # Django project configuration
│   ├── settings.py              # Settings (installed apps, auth, static, etc.)
│   ├── urls.py                  # Root URL dispatcher
│   ├── views.py                 # Splash page view
│   ├── wsgi.py / asgi.py        # WSGI / ASGI interfaces
│
├── calculator/                  # Main Django application
│   ├── models.py                # Dataset & Calculation models
│   ├── views.py                 # Business logic & numerical methods
│   ├── urls.py                  # Calculator URL patterns
│   ├── admin.py                 # Admin registration
│   ├── data/
│   │   └── ecg_example.csv      # Built-in example ECG data
│   ├── management/commands/     # Custom management commands
│   └── templates/calculator/
│       ├── index.html           # CSV upload page
│       ├── chart.html           # Chart + result partial (HTMX target)
│       ├── example.html         # Interactive example page
│       └── dashboard.html       # User calculation history + edit modal
│
├── templates/                   # Global templates
│   ├── base.html                # Base layout (navbar, footer, curtain animation)
│   ├── splashpage.html          # Landing page
│   └── account/
│       ├── login.html           # Login page
│       └── signup.html          # Sign-up page
│
└── theme/                       # django-tailwind theme app
    ├── static/                  # Compiled static assets (CSS, favicon)
    └── static_src/              # Tailwind source (input CSS, config)
```

---

## Core Features

### 1. CSV Upload & Validation
Users upload a two-column CSV file (time, voltage). The file uses **semicolon** (`;`) as the column separator and **comma** (`,`) as the decimal separator. The backend (`_csv_check`) validates:
- Exactly 2 columns with no null values
- All values are non-negative numbers
- One column is strictly monotonically increasing (identified as the **time axis**)
- The time axis has a **constant step** (uniform sampling)
- The voltage column's **last value is 0** (signal returns to baseline)

### 2. Numerical Integration
After validation, three integrals are computed simultaneously using **vectorised NumPy operations** and sent to the template:
- **Rectangles** — left Riemann sum (`V[:-1].sum() * h`)
- **Trapezius** — trapezoidal rule (`h/2 * (V[0] + 2*V[1:-1].sum() + V[-1])`)
- **Simpson** — composite Simpson's 1/3 rule (`h/3 * (V[0] + 4*odd.sum() + 2*even_inner.sum() + V[-1])`)

Results and shape data (rectangles, trapezoids, parabolic areas) are returned as JSON for client-side chart rendering.

### 3. Interactive Chart
Built with **Apache ECharts**, the chart displays:
- The smooth ECG signal curve
- The geometric shapes representing the selected integration method (rectangles, trapezoids, or parabolic segments), colour-coded per method
- **DataZoom** — mouse-scroll/pinch zoom and a slider bar for panning along the time axis
- **Dynamic Y-axis** — automatically scaled based on `v_max` (the peak voltage of the signal)
- A **custom tooltip** showing precise time and voltage values on hover
- Switching between methods updates the chart and formula **without a page reload** (via Alpine.js + HTMX partial swap)
- A **curtain-down CSS animation** plays each time the chart partial is loaded

### 4. LaTeX Formula Display
**MathJax** renders the mathematical formula for the selected integration method inline with the result, e.g.:

$$I_R \approx h \sum_{i=0}^{n-1} y_i$$

### 5. Clinical Feedback
After each calculation the server returns a custom `X-Average` HTTP header containing the **average integral** across all three methods. The frontend evaluates this value and displays an inline alert:

| Average range (mV·s)  | Feedback                                                        | Alert type |
|-----------------------|-----------------------------------------------------------------|------------|
| 0.05 ≤ avg ≤ 0.20    | **Physiological Value** (Value within normal range)             | Success    |
| avg < 0.05            | **AT RISK** (Excessively low voltage) — Consult a Physician    | Warning    |
| avg > 0.20            | **AT RISK** (Suspected Hypertrophy or conduction abnormality) — Consult a Physician | Warning |

### 6. Built-in Example
A pre-loaded ECG dataset (`ecg_example.csv`) is available for users who want to try the tool without their own data.

### 7. User Dashboard
Authenticated users can:
- Have their calculations **automatically saved** after upload (duplicate detection prevents repeated saves — a duplicate upload returns **HTTP 409**)
- Access a **dashboard** showing all past calculations grouped by date, with creation time and modification timestamp displayed on each card
- **Re-open** any past calculation and switch between integration methods via HTMX — no data re-upload required
- **Edit** a saved dataset: an edit button (pencil icon) opens a **modal dialog** with an editable table of voltage values (time values are read-only); upon submission the backend validates the new voltages (non-negative, ≤ 10 mV, last value = 0, same count) and **recomputes all three integrals**, updating the chart in-place; the server responds with an `X-Dataset-Updated` header and the dataset is flagged as modified
- **Delete** a saved dataset via an inline delete button (trash icon) that triggers an HTMX `DELETE` request with a confirmation dialog; upon success the card is removed from the DOM without a page reload

### 8. Splash Page
A landing page with two primary call-to-action buttons — **"Start to calculate"** (goes to the calculator) and **"Go to Dashboard"** (goes to the user's saved datasets) — plus a disclaimer that the software is for educational purposes only.

---

## Data Model

### `Dataset`
Stores the raw signal data uploaded by a user.

| Field | Type | Description |
|---|---|---|
| `user` | ForeignKey → User | Owner of the dataset |
| `csv_name` | CharField | Original filename |
| `step` | FloatField | Constant time step between samples |
| `time_values` | JSONField | List of time sample values |
| `voltage_values` | JSONField | List of voltage sample values |
| `created_at` | DateTimeField | Auto-set on creation |
| `updated_at` | DateTimeField | Auto-updated on every save |
| `is_modified` | BooleanField | `True` if the dataset has been edited by the user (default: `False`) |

**Property**: `n` — returns the number of intervals (`len(time_values) - 1`).

### `Calculation`
Stores the computed integration results linked 1-to-1 with a Dataset.

| Field | Type | Description |
|---|---|---|
| `dataset` | OneToOneField → Dataset | Parent dataset |
| `curve` | JSONField | `[time, voltage]` pairs for charting |
| `rects` | JSONField | Rectangle shape data |
| `trapezius` | JSONField | Trapezoid shape data |
| `simpson` | JSONField | Simpson parabolic shape data |
| `result_rectangles` | FloatField | Area via rectangles (mV·s) |
| `result_trapezius` | FloatField | Area via trapezius (mV·s) |
| `result_simpson` | FloatField | Area via Simpson (mV·s) |
| `v_max` | FloatField | Peak voltage of the signal (mV), used for dynamic Y-axis scaling |
| `created_at` | DateTimeField | Auto-set on creation |
| `updated_at` | DateTimeField | Auto-updated on every save |

---

## URL Routes

| Method | URL | View | Description |
|---|---|---|---|
| GET | `/` | `index` | Splash / landing page |
| GET/POST | `/accounts/…` | allauth | Login, signup, Google OAuth |
| GET | `/calculator/` | `calculator:index` | CSV upload form |
| POST | `/calculator/calculate` | `calculator:calculate` | Process CSV & return chart partial |
| POST | `/calculator/calculate/<pk>` | `calculator:calculate` | Load saved calculation |
| GET | `/calculator/example` | `calculator:example` | Example page |
| POST | `/calculator/calculate_example` | `calculator:calculate_example` | Run example calculation |
| GET | `/calculator/dashboard` | `calculator:dashboard` | User history (login required) |
| POST | `/calculator/update/<calc_id>/` | `calculator:update_dataset` | Edit voltage values & recompute (login required) |
| DELETE | `/calculator/delete_dataset/<pk>` | `calculator:delete_dataset` | Delete a saved dataset (login required) |
| GET | `/admin/` | Django Admin | Admin panel |

---

## Numerical Methods

All methods are implemented with **vectorised NumPy** operations for performance and correctness.

### Rectangle Method (Left Riemann Sum)
$$I_R \approx h \sum_{i=0}^{n-1} y_i$$

Implementation: `time_step * V[:-1].sum()` — sums only the first *n* voltage values (left endpoints).

### Trapezoidal Rule
$$I_T \approx \frac{h}{2} \left[ y_0 + 2\sum_{i=1}^{n-1} y_i + y_n \right]$$

Implementation: `time_step / 2 * (V[0] + 2 * V[1:-1].sum() + V[-1])`

### Simpson's 1/3 Rule
$$I_S \approx \frac{h}{3} \left[ y_0 + 4\sum_{\text{odd}} y_i + 2\sum_{\text{even}} y_i + y_n \right]$$

Implementation: `time_step / 3 * (V[0] + 4 * V[1:-1:2].sum() + 2 * V[2:-2:2].sum() + V[-1])`

Where `h` is the constant time step between samples.

### Average Result
After computing all three integrals, the server calculates the **mean** of the three results (`_get_average_result`) and returns it in the `X-Average` response header for clinical feedback purposes.

---

## Authentication

Authentication is handled by **django-allauth** with:
- **Email-based** login and signup (`ACCOUNT_LOGIN_METHODS = {'email'}`)
- **Google OAuth2** social login (requires `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` env vars)
- Email verification set to `optional` (can be changed to `mandatory` for production)
- After login, users are redirected to `/` (`LOGIN_REDIRECT_URL = '/'`)

The user's Google profile picture is displayed in the navbar and dashboard.

---

## Frontend & UI

- **Theme**: DaisyUI **Nord** theme (`data-theme="nord"`)
- **Layout**: Sticky navbar with a Calculator dropdown, responsive main content area, and a copyright footer
- **Favicon**: Custom favicon served as PNG (16×16 and 32×32) plus an ICO icon in the navbar brand
- **HTMX**: Form submissions post to `/calculator/calculate` and swap only the `#calc-chart` div — no full page reload
- **Alpine.js**: Manages the selected integration method state, toast notification visibility, inline clinical feedback alerts, and the dataset edit modal on the client side
- **Chart animation**: A `curtain-down` CSS `clip-path` animation reveals the chart container when it is loaded via HTMX swap
- **DataZoom**: The chart includes both an `inside` zoom (mouse scroll / pinch) and a `slider` zoom bar, enabling users to pan and zoom along the time axis
- **Custom Tooltip**: Hovering over the chart displays precise time (s) and voltage (mV) values in a formatted tooltip with a crosshair pointer
- **Toast Notifications**: Error messages (HTTP 4xx) and success messages (HTTP 201 – calculation saved, HTTP 204 – dataset deleted) are surfaced via an Alpine-powered toast component
- **Clinical Feedback Alerts**: An inline alert banner (success / warning) is displayed after each calculation, showing whether the integral is within physiological range; the alert is dismissible with a close button
- **Dataset Editing Modal**: Each dashboard card includes an edit button (pencil icon) that opens a fullscreen modal with a scrollable table; time values are displayed as read-only, voltage values are editable `<input type="number">` fields (min 0, max 10, step 0.001); submitting the form triggers an HTMX POST to `update_dataset` and the chart is re-rendered in-place with updated results
- **Dataset Deletion**: Each dashboard card includes a delete button (trash icon) that triggers an HTMX `DELETE` request with a confirmation dialog; upon success the card is removed from the DOM via the `HX-Trigger: delete-collapse` mechanism; if the day group has no remaining cards, the entire group is also removed

---

## Deployment

The project is deployed at **[cardioquant.onrender.com](https://cardioquant.onrender.com)** using Render.

Key production settings:
- `SECRET_KEY` — set via environment variable
- `DEBUG=False` — set via environment variable
- `SITE_ID` — set via environment variable
- Static files served by **Whitenoise** with `CompressedManifestStaticFilesStorage`
- Production WSGI server: **Gunicorn**

---

## Getting Started (Local Development)

### Prerequisites
- Python 3.10+
- Node.js & npm (for Tailwind CSS compilation)

### Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd cardioQuant

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Create a .env file with your environment variables
# (see table below)

# 5. Apply database migrations
python manage.py migrate

# 6. Install Tailwind CSS dependencies
python manage.py tailwind install

# 7. (Optional) Create a superuser for the Django admin
python manage.py createsuperuser
```

### Running the Development Server

Open **two terminals**:

```bash
# Terminal 1 — Tailwind CSS watcher
python manage.py tailwind start

# Terminal 2 — Django dev server
python manage.py runserver
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

### Environment Variables (for Google OAuth & production)

Environment variables are loaded automatically from the `.env` file via **python-dotenv** (called in `manage.py`).

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` or `False` |
| `SITE_ID` | django.contrib.sites ID (default: `1`) |
| `GOOGLE_CLIENT_ID` | Google OAuth2 client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 client secret |

### CSV File Format

Upload a two-column CSV with **semicolon** (`;`) as the separator and **comma** (`,`) as the decimal separator:
- **Column 1**: time values in seconds, starting at `0`, with a **constant step** (e.g. `0,02`)
- **Column 2**: voltage values in mV, all non-negative, with the **last value equal to `0`**

Example:

```csv
time;voltage
0;0
0,02;0,1
0,04;0,5
...
0,40;0
```
