"""
Load test for the coming-soon page and waitlist signup.

Simulates launch-day traffic: mostly visitors reading the page, some real
people signing up, and spam bots attacking the signup form in every way the
form defends against. Run via loadtests/run_local.sh, or directly:

    locust -f loadtests/locustfile.py --host http://127.0.0.1:8001

Without nginx in front (local runs), each simulated user sends its own
X-Real-IP header, just as nginx would set it in production.
"""

import random
import re
import time
import uuid

from locust import HttpUser, between, task

CSRF_RE = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')
TIMESTAMP_RE = re.compile(r'name="timestamp" value="([^"]+)"')

# Spam comes from a small pool of IPs, so per-IP limits are exercised
BOT_IPS = [f"203.0.113.{i}" for i in range(1, 6)]

SIGNUP_PATH = "/waitlist/subscribe/"


def random_ip():
    return (
        f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
    )


class _FormUser(HttpUser):
    abstract = True

    def on_start(self):
        self.ip = random_ip()

    def headers(self):
        return {"X-Real-IP": self.ip}

    def load_form(self):
        """GET the page and return (csrf_token, signed_timestamp)."""
        with self.client.get(
            "/", headers=self.headers(), name="GET /", catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"status {response.status_code}")
                return None, None
            csrf = CSRF_RE.search(response.text)
            timestamp = TIMESTAMP_RE.search(response.text)
            if not csrf or not timestamp:
                response.failure("waitlist form not found on page")
                return None, None
            return csrf.group(1), timestamp.group(1)


class Visitor(_FormUser):
    """Reads the page and leaves."""

    weight = 70
    wait_time = between(1, 3)

    @task
    def view_home(self):
        self.client.get("/", headers=self.headers(), name="GET /")


class RealSignup(_FormUser):
    """A human: loads the page, types an email for a few seconds, submits."""

    weight = 20
    wait_time = between(5, 15)

    @task
    def sign_up(self):
        csrf, timestamp = self.load_form()
        if not csrf:
            return
        time.sleep(random.uniform(4, 10))
        data = {
            "csrfmiddlewaretoken": csrf,
            "timestamp": timestamp,
            "website": "",
            "email": f"loadtest+{uuid.uuid4().hex[:12]}@gmail.com",
        }
        with self.client.post(
            SIGNUP_PATH,
            data=data,
            headers=self.headers(),
            name="POST signup (real)",
            allow_redirects=False,
            catch_response=True,
        ) as response:
            if response.status_code != 302:
                response.failure(f"real signup got {response.status_code}")


class SpamBot(_FormUser):
    """
    Cycles through spam techniques. Every one must be rejected (302 redirect
    with nothing saved, 403 for missing CSRF, or 429 from nginx).
    """

    weight = 10
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.ip = random.choice(BOT_IPS)

    def _spam_email(self, domain="gmail.com"):
        return f"spam+{uuid.uuid4().hex[:12]}@{domain}"

    def _post(self, name, data, headers=None):
        with self.client.post(
            SIGNUP_PATH,
            data=data,
            headers=headers or self.headers(),
            name=f"POST spam: {name}",
            allow_redirects=False,
            catch_response=True,
        ) as response:
            if response.status_code in (302, 403, 429):
                response.success()
            else:
                response.failure(f"unexpected {response.status_code}")

    def _form(self, email, wait=0):
        csrf, timestamp = self.load_form()
        if not csrf:
            return None
        if wait:
            time.sleep(wait)
        return {
            "csrfmiddlewaretoken": csrf,
            "timestamp": timestamp,
            "website": "",
            "email": email,
        }

    @task
    def instant_submit(self):
        data = self._form(self._spam_email())
        if data:
            self._post("instant", data)

    @task
    def honeypot(self):
        data = self._form(self._spam_email(), wait=3.5)
        if data:
            data["website"] = "http://cheap-pills.example"
            self._post("honeypot", data)

    @task
    def disposable_domain(self):
        domain = random.choice(
            ["mailinator.com", "10minutemail.com", "guerrillamail.com"]
        )
        data = self._form(self._spam_email(domain), wait=3.5)
        if data:
            self._post("disposable", data)

    @task
    def made_up_domain(self):
        domain = f"no-such-{uuid.uuid4().hex[:8]}.com"
        data = self._form(self._spam_email(domain), wait=3.5)
        if data:
            self._post("made-up domain", data)

    @task
    def typo_domain(self):
        data = self._form(self._spam_email("gmial.com"), wait=3.5)
        if data:
            self._post("typo domain", data)

    @task
    def forged_timestamp(self):
        data = self._form(self._spam_email())
        if data:
            data["timestamp"] = "forged"
            self._post("forged timestamp", data)

    @task
    def no_csrf(self):
        self._post(
            "no csrf",
            {"email": self._spam_email(), "website": "", "timestamp": ""},
        )

    @task
    def spoofed_forwarded_for(self):
        """Human-like, plus a fake X-Forwarded-For to dodge the per-IP limit.
        Must still be counted against the bot's real IP."""
        data = self._form(f"smartbot+{uuid.uuid4().hex[:12]}@gmail.com", wait=3.5)
        if data:
            headers = dict(self.headers(), **{"X-Forwarded-For": random_ip()})
            self._post("spoofed X-Forwarded-For", data, headers)

    @task
    def smart_bot(self):
        """Behaves like a human with a real-looking address; only IP limits and
        the confirmation link stop it, so a few unconfirmed rows can appear."""
        data = self._form(f"smartbot+{uuid.uuid4().hex[:12]}@gmail.com", wait=3.5)
        if data:
            self._post("smart bot", data)
