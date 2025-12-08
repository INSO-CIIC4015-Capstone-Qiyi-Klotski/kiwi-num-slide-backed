# locust_backend_db.py
from locust import task
from locust_common import KiwiBaseUser, AuthMixin
import random

class KiwiAnonUser(KiwiBaseUser):
    """
    Usuario NO autenticado que navega endpoints que sí tocan DB.
    """
    weight = 2  # ajusta como quieras

    @task(3)
    def health(self):
        self.client.get("/health", name="GET /health")

    @task(4)
    def browse_puzzles(self):
        params = {"limit": 20, "sort": "created_at_desc"}
        self.client.get("/puzzles", params=params, name="GET /puzzles[browse]")

    @task(3)
    def view_puzzle(self):
        pid = self.random_puzzle_id()
        self.client.get(f"/puzzles/{pid}", name="GET /puzzles/{id}")

    @task(2)
    def daily_puzzle(self):
        self.client.get("/puzzles/daily-puzzle", name="GET /puzzles/daily-puzzle")

    @task(2)
    def browse_users(self):
        params = {"limit": 20, "sort": "created_at_desc"}
        self.client.get("/users", params=params, name="GET /users[browse]")

    @task(2)
    def view_user_profile(self):
        uid = self.random_user_id()
        self.client.get(f"/users/{uid}", name="GET /users/{id}")

    @task(1)
    def view_user_liked_puzzles(self):
        uid = self.random_user_id()
        params = {"limit": 20}
        self.client.get(
            f"/users/{uid}/puzzles/likes",
            params=params,
            name="GET /users/{id}/puzzles/likes",
        )


class KiwiAuthUser(AuthMixin, KiwiBaseUser):
    """
    Usuario autenticado que hace likes, solves, follows, etc.
    """
    weight = 3  # más peso si quieres más tráfico autenticado

    # ----- tareas públicas (igual que anon, pero con [auth] en el name) -----

    @task(2)
    def health(self):
        self.client.get("/health", name="[auth] GET /health")

    @task(3)
    def browse_puzzles(self):
        params = {"limit": 20, "sort": "created_at_desc"}
        self.client.get("/puzzles", params=params, name="[auth] GET /puzzles[browse]")

    @task(2)
    def view_puzzle(self):
        pid = self.random_puzzle_id()
        self.client.get(f"/puzzles/{pid}", name="[auth] GET /puzzles/{id}")

    @task(2)
    def daily_puzzle(self):
        self.client.get("/puzzles/daily-puzzle", name="[auth] GET /puzzles/daily-puzzle")

    @task(2)
    def browse_users(self):
        params = {"limit": 20, "sort": "created_at_desc"}
        self.client.get("/users", params=params, name="[auth] GET /users[browse]")

    @task(1)
    def view_user_profile(self):
        uid = self.random_user_id()
        self.client.get(f"/users/{uid}", name="[auth] GET /users/{id}")

    # ----- tareas que sí escriben en DB -----

    @task(3)
    def like_random_puzzle(self):
        if not self.csrf_token:
            return
        pid = self.random_puzzle_id()
        self.client.post(
            f"/puzzles/{pid}/like",
            headers=self._csrf_headers(),
            name="POST /puzzles/{id}/like",
        )

    @task(2)
    def unlike_random_puzzle(self):
        if not self.csrf_token:
            return
        pid = self.random_puzzle_id()
        self.client.delete(
            f"/puzzles/{pid}/like",
            headers=self._csrf_headers(),
            name="DELETE /puzzles/{id}/like",
        )

    @task(2)
    def submit_solve(self):
        if not self.csrf_token:
            return

        pid = self.random_puzzle_id()
        payload = {
            "movements": 42,
            "duration_ms": 60_000,
            "solution": {"solution": [1, 2, 3, 4]},
        }
        self.client.post(
            f"/puzzles/{pid}/solves",
            json=payload,
            headers=self._csrf_headers(),
            name="POST /puzzles/{id}/solves",
        )

    @task(1)
    def get_my_solves_for_puzzle(self):
        if not self.csrf_token:
            return

        pid = self.random_puzzle_id()
        params = {"limit": 20}
        self.client.get(
            f"/puzzles/{pid}/solves/me",
            params=params,
            headers=self._csrf_headers(),
            name="GET /puzzles/{id}/solves/me",
        )

    @task(2)
    def follow_unfollow_user(self):
        if not self.csrf_token:
            return

        uid = self.random_user_id()
        self.client.post(
            f"/users/{uid}/follow",
            headers=self._csrf_headers(),
            name="POST /users/{id}/follow",
        )

        if random.random() < 0.5:
            self.client.delete(
                f"/users/{uid}/follow",
                headers=self._csrf_headers(),
                name="DELETE /users/{id}/follow",
            )
