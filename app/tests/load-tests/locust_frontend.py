# locust_frontend.py
from locust import HttpUser, task, between

class FrontUser(HttpUser):
    """
    Usuario que golpea el FRONT (Next.js en EB).
    OJO: aquí el host será el de www.<tu-dominio>.com
    """
    wait_time = between(1, 3)  # navegación un poco más "rápida"

    @task(3)
    def home(self):
        self.client.get("/", name="FRONT GET /")

    @task(2)
    def levels_page(self):
        # Ajusta la ruta según tu app: /levels, /puzzles, /play, etc.
        self.client.get("/levels", name="FRONT GET /levels")

    @task(1)
    def puzzle_page(self):
        # También puedes simular entrar directo a un puzzle
        self.client.get("/puzzles/1", name="FRONT GET /puzzles/1")

    # Si quieres ser más nasty con los estáticos (JS/CSS):
    # @task(1)
    # def main_js(self):
    #     self.client.get(
    #         "/_next/static/chunks/main.js",
    #         name="FRONT GET main.js",
    #     )
