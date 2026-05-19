from app.tools import Tools


def test_calculate_distance_returns_float():
    """Verifica que el cálculo de distancia retorne un float positivo."""
    result = Tools.calculate_distance((-33.4489, -70.6693), (-33.4372, -70.6341))
    assert isinstance(result, float)
    assert result > 0


def test_calculate_distance_same_point():
    """Verifica que la distancia entre el mismo punto sea cero."""
    result = Tools.calculate_distance((-33.4489, -70.6693), (-33.4489, -70.6693))
    assert result == 0.0
