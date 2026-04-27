import os
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv
from geopy.distance import geodesic

load_dotenv()

class Tools:
    @staticmethod
    def get_uf_value():
        """Obtiene el último valor de la UF desde el Banco Central usando credenciales en variables de entorno."""
        user = os.getenv("BCCH_USER")
        password = os.getenv("BCCH_PASS")
        serie = os.getenv("BCCH_SERIE_UF")

        if user and password and serie:
            return Tools._get_uf_value_bcch(user, password, serie)

        # Fallback a API SBIF si no hay credenciales de Banco Central configuradas.
        return Tools._get_uf_value_sbif()

    @staticmethod
    def _get_uf_value_bcch(user: str, password: str, serie: str):
        url = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"
        last_date = datetime.now().date()
        first_date = last_date - timedelta(days=14)
        params = {
            "user": user,
            "pass": password,
            "function": "GetSeries",
            "timeseries": serie,
            "firstdate": first_date.strftime("%Y-%m-%d"),
            "lastdate": last_date.strftime("%Y-%m-%d"),
        }

        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            return None

        data = response.json()
        series = data.get("Series", {})
        observations = series.get("Obs") or []

        for obs in reversed(observations):
            value = obs.get("value")
            if value not in (None, "", "-"):
                return value

        return None

    @staticmethod
    def _get_uf_value_sbif():
        url = "https://api.cmfchile.cl/api-sbifv3/recursos_api/uf?apikey=your_api_key&formato=json"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data['UFs'][0]['Valor']
        return None

    @staticmethod
    def calculate_distance(coord1, coord2):
        # coord1 y coord2 como tuplas (lat, lon)
        return geodesic(coord1, coord2).km