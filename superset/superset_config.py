"""Local Superset configuration for DVA dashboards."""

SECRET_KEY = "dva-local-demo-secret-key-change-in-prod"

# Filter bar collapsed on dashboard load; user clicks to expand when needed.
FILTERBAR_CLOSED_BY_DEFAULT = True

FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
}

APP_NAME = "Data Validation Accelerator"
APP_ICON = "/static/assets/images/superset-logo-horiz.png"

TALISMAN_ENABLED = False
WTF_CSRF_ENABLED = False

SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://dva:dva@postgres:5432/superset"

# Allow Superset to query the DVA results database via bootstrap script.
ADDITIONAL_DATABASES = {
    "dva_results": "postgresql+psycopg2://dva:dva@postgres:5432/dva",
}
