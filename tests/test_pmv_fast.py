"""Garante que a rota rápida de PMV dá exatamente o mesmo resultado da original."""
import random

import pythermalcomfort
from ladybug_comfort.pmv import predicted_mean_vote

from confortimetro.control.base import _pmv


def test_pmv_igual_ao_modelo_completo():
    random.seed(0)
    for _ in range(200):
        ta = random.uniform(10.0, 35.0)
        tr = ta + random.uniform(-3.0, 3.0)
        vel = random.choice([0.0, 0.05, 0.1, 0.15, 0.3, 0.6, 1.2])
        rh = random.uniform(20.0, 90.0)
        clo = random.choice([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        esperado = predicted_mean_vote(
            ta=ta, tr=tr,
            vel=pythermalcomfort.utilities.v_relative(vel, met=1.2),
            rh=rh, met=1.2,
            clo=pythermalcomfort.utilities.clo_dynamic(clo, met=1.2),
            wme=0.0,
        )['pmv']
        assert _pmv(ta, tr, vel, rh, 1.2, clo, 0.0) == esperado


if __name__ == "__main__":
    test_pmv_igual_ao_modelo_completo()
    print("ok")
