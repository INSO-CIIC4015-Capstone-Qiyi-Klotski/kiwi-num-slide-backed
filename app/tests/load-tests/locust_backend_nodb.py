# locust_backend_nodb.py
from locust import task, between
from locust_common import KiwiBaseUser

# -------------------------
# Parámetros de carga CPU
# -------------------------
# Cada request ejecuta el "solver" una sola vez (iterations=1),
# pero con un max_depth configurado para que sea pesado.
SOLVER_ITERATIONS = 1       # una sola llamada a brute_force_solver por request
SOLVER_MAX_DEPTH = 12        # ajusta este valor para subir/bajar peso (1–12 por el router)


class BackendCpuSolverUser(KiwiBaseUser):
    """
    Usuario que genera carga SOLO en CPU del backend llamando al endpoint
    /debug/cpu-solver sin tocar la base de datos.

    Cada tarea:
      - hace UNA llamada HTTP al solver
      - con iterations=1 (una corrida interna)
      - con max_depth relativamente alto (CPU-heavy)
    """

    # Menos agresivo que antes para no tumbar el EB:
    # cada usuario virtual espera entre 2 y 5 segundos entre requests.
    wait_time = between(2, 5)

    @task(10)
    def stress_single_solver_call(self):
        params = {
            "iterations": SOLVER_ITERATIONS,
            "max_depth": SOLVER_MAX_DEPTH,
        }
        self.client.get(
            "/debug/cpu-solver",
            params=params,
            name=f"GET /debug/cpu-solver?it={SOLVER_ITERATIONS}&depth={SOLVER_MAX_DEPTH}",
        )
