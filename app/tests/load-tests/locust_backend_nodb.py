# locust_backend_nodb.py
from locust import task, between
from locust_common import KiwiBaseUser

class BackendCpuSolverUser(KiwiBaseUser):
    """
    Genera carga en las EC2 del backend llamando al solver CPU-heavy,
    sin pegarle a la base de datos.
    """
    # Por ejemplo, usuarios agresivos:
    wait_time = between(0.1, 0.3)

    @task(10)
    def stress_solver(self):
        params = {
            "iterations": 5,   # cuántas veces corre el solver por request
            "max_depth": 7,    # qué tan profundo busca (más = más CPU)
        }
        self.client.get(
            "/debug/cpu-solver",
            params=params,
            name="GET /debug/cpu-solver",
        )