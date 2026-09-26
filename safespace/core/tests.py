from datetime import date

from django.test import TestCase
from django.test import Client
from django.contrib.auth.models import User

from .models import Quest, QuestCompletion


class AccountRegistrationTests(TestCase):
    def test_get_displays_csrf_protected_registration_form(self):
        response = self.client.get("/register/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'name="username"')

    def test_post_creates_account_with_hashed_password(self):
        csrf_client = Client(enforce_csrf_checks=True)
        form_response = csrf_client.get("/register/")
        csrf_token = form_response.cookies["csrftoken"].value

        response = csrf_client.post(
            "/register/",
            {
                "username": "new-member",
                "password1": "SafePassword123!",
                "password2": "SafePassword123!",
                "csrfmiddlewaretoken": csrf_token,
            },
        )

        self.assertRedirects(response, "/")
        user = User.objects.get(username="new-member")
        self.assertTrue(user.check_password("SafePassword123!"))

    def test_invalid_post_does_not_create_account(self):
        response = self.client.post(
            "/register/",
            {
                "username": "new-member",
                "password1": "SafePassword123!",
                "password2": "DifferentPassword123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The two password fields")
        self.assertFalse(User.objects.filter(username="new-member").exists())

    def test_post_without_csrf_token_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            "/register/",
            {
                "username": "new-member",
                "password1": "SafePassword123!",
                "password2": "SafePassword123!",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="new-member").exists())


class QuestListViewTests(TestCase):
    def setUp(self):
        self.completed_quest = Quest.objects.create(
            title="Completed quest",
            category="general",
        )
        self.incomplete_quest = Quest.objects.create(
            title="Incomplete quest",
            category="general",
        )
        user = User.objects.create_user(username="quest-member")
        QuestCompletion.objects.create(
            user=user,
            quest=self.completed_quest,
            completed_status=True,
            quest_date=date(2026, 9, 26),
        )
        QuestCompletion.objects.create(
            user=user,
            quest=self.incomplete_quest,
            completed_status=False,
            quest_date=date(2026, 9, 26),
        )

    def test_base_view_shows_completed_quest_statistics_and_search(self):
        response = self.client.get("/quests/cbv-base/?q=Completed")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_quests"], 2)
        self.assertEqual(
            list(response.context["quests"]),
            [self.completed_quest],
        )
        summary = {
            quest.pk: quest.user_count
            for quest in response.context["quest_summary"]
        }
        self.assertEqual(summary[self.completed_quest.pk], 1)
        self.assertEqual(summary[self.incomplete_quest.pk], 0)

    def test_generic_view_shows_completed_quest_statistics_and_search(self):
        response = self.client.get("/quests/cbv-generic/?q=Completed")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_quests"], 2)
        self.assertEqual(
            list(response.context["quests"]),
            [self.completed_quest],
        )
        summary = {
            quest.pk: quest.user_count
            for quest in response.context["quest_summary"]
        }
        self.assertEqual(summary[self.completed_quest.pk], 1)
        self.assertEqual(summary[self.incomplete_quest.pk], 0)


class ResponseExampleTests(TestCase):
    def test_http_response_returns_plain_text(self):
        response = self.client.get("/responses/http/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertContains(response, "message: Hello from SafeSpace")

    def test_json_response_returns_equivalent_data_as_json(self):
        response = self.client.get("/responses/json/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {
                "message": "Hello from SafeSpace",
                "quest_count": 3,
            },
        )
