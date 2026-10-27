"""Supply Airflow's metadata URL through its supported _CMD configuration."""
import os
import sys
from urllib.parse import quote_plus

if __name__ == '__main__':
    password = quote_plus(os.environ['AIRFLOW_APP_PASSWORD'])
    sys.stdout.write(f'postgresql+psycopg2://airflow_app:{password}@postgres:5432/airflow_meta')
