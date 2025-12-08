# locust_common.py
import os
import csv
import random
from locust import HttpUser, between

# -------------------------
# Config & CSV
# -------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_CSV_PATH = os.path.join(BASE_DIR, "users.csv")

PASSWORD = "123456789"  # misma para todos

def load_emails_from_csv(path: str = USERS_CSV_PATH) -> list[str]:
    emails: list[str] = []
    if not os.path.exists(path):
        print(f"[locust] WARNING: users.csv not found at {path}")
        return emails

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = (row.get("email") or "").strip()
            if email:
                emails.append(email)
    return emails

TEST_EMAILS = load_emails_from_csv()
print(f"[locust] Loaded {len(TEST_EMAILS)} emails from users.csv")

MIN_WAIT = 5
MAX_WAIT = 15


# -------------------------
# Base user para _todo el backend
# -------------------------

class KiwiBaseUser(HttpUser):
    """
    Base común para usuarios que golpean el backend (auth o anon).
    Comparte wait_time y helpers.
    """
    wait_time = between(MIN_WAIT, MAX_WAIT)
    abstract = True

    @staticmethod
    def random_puzzle_id() -> int:
        return random.randint(1, 120)  # ajusta según tu seed

    @staticmethod
    def random_user_id() -> int:
        # si el 1 es Kiwi system, empezamos en 2
        return random.randint(2, 60)


# -------------------------
# Mixin para usuarios autenticados
# -------------------------

class AuthMixin:
    """
    Mezcla reutilizable para hacer login + gestionar CSRF.
    Se usa junto con KiwiBaseUser (múltiple herencia).
    """

    def on_start(self):
        """
        Login una sola vez al "nacer" el usuario virtual.
        """
        if not TEST_EMAILS:
            self.email = None
            self.csrf_token = None
            return

        self.email = random.choice(TEST_EMAILS)
        self.csrf_token = None

        payload = {
            "email": self.email,
            "password": PASSWORD,
        }

        with self.client.post(
            "/auth/login",
            json=payload,
            name="POST /auth/login",
            catch_response=True,
        ) as res:
            if res.status_code != 200:
                res.failure(f"Login failed ({res.status_code}): {res.text}")
                return

        self.csrf_token = self.client.cookies.get("csrf_token")

    def _csrf_headers(self) -> dict:
        if getattr(self, "csrf_token", None):
            return {"X-CSRF-Token": self.csrf_token}
        return {}
