# CardioQuant

**CardioQuant** is a web application for numerical integration of ECG (electrocardiogram) signals. It allows users to upload CSV files containing time–voltage data, compute the area under the curve using three different numerical methods, and visualise the results interactively. Authenticated users can save and revisit past calculations from a personal dashboard.

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
| **NumPy** | 2.4.4 | Numerical operations (e.g. `np.isclose`) |
| **SQLite** | — | Default database (`db.sqlite3`) |
| **Gunicorn** | 26.0.0 | WSGI server for production |
| **Whitenoise** | 6.12.0 | Static file serving in production |
| **django-allauth** | 65.16.1 | Authentication (email + Google OAuth2) |
| **django-htmx** | 1.27.0 | HTMX middleware integration |
| **django-extensions** | 4.1 | Development utilities |
| **PyJWT** | 2.12.1 | JWT token support |

### Frontend

| Technology | Role |
|---|---|
| **Tailwind CSS** (via `django-tailwind`) | Utility-first CSS framework |
| **DaisyUI** | Tailwind component library (Nord theme) |
| **HTMX** | Partial page updates without full reloads |
| **Alpine.js** | Lightweight client-side reactivity |
| **Apache ECharts 5** | Interactive chart rendering |
| **MathJax 3** | LaTeX formula rendering in the browser |

---

## Project Structure

```
cardioQuant/
├── manage.py                    # Django CLI entry point
├── requirements.txt             # Python dependencies
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
│       └── dashboard.html       # User calculation history
│
├── templates/                   # Global templates
│   ├── base.html                # Base layout (navbar, footer)
│   ├── splashpage.html          # Landing page
│   └── account/
│       ├── login.html           # Login page
│       └── signup.html          # Sign-up page
│
└── theme/                       # django-tailwind theme app
    ├── static/                  # Compiled static assets
    └── static_src/              # Tailwind source (input CSS, config)
```

---

## Core Features

### 1. CSV Upload & Validation
Users upload a two-column CSV file (time, voltage). The backend (`_csv_check`) validates:
- Exactly 2 columns with no null values
- All values are non-negative numbers
- One column is strictly monotonically increasing (identified as the **time axis**)
- The time axis has a **constant step** (uniform sampling)
- The voltage column's **last value is 0** (signal returns to baseline)

### 2. Numerical Integration
After validation, three integrals are computed simultaneously and sent to the template:
- **Rectangles** — left Riemann sum
- **Trapezius** — trapezoidal rule
- **Simpson** — composite Simpson's 1/3 rule

Results and shape data (rectangles, trapezoids, parabolic areas) are returned as JSON for client-side chart rendering.

### 3. Interactive Chart
Built with **Apache ECharts**, the chart displays:
- The smooth ECG signal curve
- The geometric shapes representing the selected integration method (rectangles, trapezoids, or parabolic segments), colour-coded per method
- Switching between methods updates the chart and formula **without a page reload** (via Alpine.js + HTMX partial swap)

### 4. LaTeX Formula Display
**MathJax** renders the mathematical formula for the selected integration method inline with the result, e.g.:

$$I_R \approx h \sum_{i=0}^{n-1} y_i$$

### 5. Built-in Example
A pre-loaded ECG dataset (`ecg_example.csv`) is available for users who want to try the tool without their own data.

### 6. User Dashboard
Authenticated users can:
- Have their calculations **automatically saved** after upload (duplicate detection prevents repeated saves)
- Access a **dashboard** showing all past calculations grouped by date
- **Re-open** any past calculation and switch between integration methods via HTMX — no data re-upload required

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
| GET | `/admin/` | Django Admin | Admin panel |

---

## Numerical Methods

### Rectangle Method (Left Riemann Sum)
$$I_R \approx h \sum_{i=0}^{n-1} y_i$$

### Trapezoidal Rule
$$I_T \approx \frac{h}{2} \left[ y_0 + 2\sum_{i=1}^{n-1} y_i + y_n \right]$$

### Simpson's 1/3 Rule
$$I_S \approx \frac{h}{3} \left[ y_0 + 4\sum_{\text{odd}} y_i + 2\sum_{\text{even}} y_i + y_n \right]$$

Where `h` is the constant time step between samples.

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
- **HTMX**: Form submissions post to `/calculator/calculate` and swap only the `#calc-chart` div — no full page reload
- **Alpine.js**: Manages the selected integration method state and toast notification visibility on the client side
- **Toast Notifications**: Error messages (HTTP 4xx) and success messages (HTTP 201 – calculation saved) are surfaced via an Alpine-powered toast component

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

# 4. Apply database migrations
python manage.py migrate

# 5. Install Tailwind CSS dependencies
python manage.py tailwind install

# 6. (Optional) Create a superuser for the Django admin
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

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` or `False` |
| `SITE_ID` | django.contrib.sites ID (default: `1`) |
| `GOOGLE_CLIENT_ID` | Google OAuth2 client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 client secret |

### CSV File Format

Upload a two-column CSV with:
- **Column 1**: time values in seconds, starting at `0`, with a **constant step** (e.g. `0.02`)
- **Column 2**: voltage values in mV, all non-negative, with the **last value equal to `0`**

Example:

```csv
time,voltage
0,0
0.02,0.1
0.04,0.5
...
0.40,0
```
