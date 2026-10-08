import json
from datetime import date

from django.test import TestCase
from django.test import Client
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Journal, JournalSticker, Quest, QuestCompletion, Reward, UserReward


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


class JournalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="writer", password="pw-12345!")
        self.other = User.objects.create_user(username="other", password="pw-12345!")
        Journal.objects.create(user=self.other, content="Someone else's secret")

        self.quest = Quest.objects.create(title="Walk", category="general")
        self.sticker = Reward.objects.create(
            name="Star", item_type="sticker", asset="rewards/stickers/stay-hydrated.svg")
        self.background = Reward.objects.create(
            name="Meadow", item_type="background", asset="rewards/backgrounds/nature.svg")
        self.frame = Reward.objects.create(
            name="Smiles", item_type="frame", asset="rewards/frames/smiley.svg")
        self.font = Reward.objects.create(
            name="Hand", item_type="font", asset="rewards/fonts/caveat.woff2")
        for reward in [self.sticker, self.background, self.frame, self.font]:
            reward.quests.add(self.quest)

    def earn(self, user, times=1):
        for day in range(times):
            QuestCompletion.objects.create(
                user=user, quest=self.quest, quest_date=date(2026, 9, 1 + day),
                completed_status=True, completed_date=date(2026, 9, 1 + day),
            ).award_rewards()

    def save_page(self, content="A good day", **layout):
        layout.setdefault("stickers", [])
        return self.client.post(
            "/journals/new/",
            {"content": content, "layout": json.dumps(layout)},
        )

    def test_journal_requires_login(self):
        for url in ["/journals/", "/journals/new/"]:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"/login/?next={url}")

    def test_editor_lists_owned_rewards_with_unused_counts(self):
        self.earn(self.user, times=2)
        self.client.login(username="writer", password="pw-12345!")

        response = self.client.get("/journals/new/")

        rewards = response.context["editor_rewards"]
        self.assertEqual([(r["name"], r["count"]) for r in rewards["sticker"]], [("Star", 2)])
        self.assertEqual([r["name"] for r in rewards["background"]], ["Meadow"])
        self.assertContains(response, "reward-font-")

    def test_saves_decorated_page_and_uses_up_sticker_copies(self):
        self.earn(self.user, times=2)
        self.client.login(username="writer", password="pw-12345!")

        response = self.save_page(
            background=self.background.pk, frame=self.frame.pk, font=self.font.pk,
            stickers=[{"reward": self.sticker.pk, "x": 80, "y": 30, "rotation": 8, "scale": 1.3}],
        )

        self.assertRedirects(response, "/journals/")
        journal = Journal.objects.get(user=self.user)
        self.assertEqual(
            (journal.background, journal.frame, journal.font),
            (self.background, self.frame, self.font),
        )
        placed = journal.stickers.get()
        self.assertEqual((placed.x, placed.y, placed.rotation, placed.scale), (80, 30, 8, 1.3))
        self.assertEqual(placed.user_reward.user, self.user)

        editor = self.client.get("/journals/new/")
        self.assertEqual(editor.context["editor_rewards"]["sticker"][0]["count"], 1)

    def test_cannot_place_more_stickers_than_unused_copies(self):
        self.earn(self.user, times=1)
        self.client.login(username="writer", password="pw-12345!")
        two = [{"reward": self.sticker.pk, "x": 10, "y": 10}] * 2

        response = self.save_page(stickers=two)

        self.assertContains(response, "enough copies")
        self.assertFalse(Journal.objects.filter(user=self.user).exists())

    def test_cannot_use_rewards_you_have_not_earned(self):
        self.earn(self.other)
        self.client.login(username="writer", password="pw-12345!")

        for layout in [
            {"background": self.background.pk},
            {"stickers": [{"reward": self.sticker.pk, "x": 1, "y": 1}]},
        ]:
            with self.subTest(layout=layout):
                self.save_page(**layout)
                self.assertFalse(Journal.objects.filter(user=self.user).exists())

    def test_wrong_reward_type_and_bad_layout_are_rejected(self):
        self.earn(self.user)
        self.client.login(username="writer", password="pw-12345!")

        self.save_page(background=self.frame.pk)
        self.client.post("/journals/new/", {"content": "Hi", "layout": "not json"})
        self.save_page(stickers=[{"reward": self.sticker.pk, "x": "NaN", "y": 1}])

        self.assertFalse(Journal.objects.filter(user=self.user).exists())

    def test_positions_are_kept_inside_the_page(self):
        self.earn(self.user)
        self.client.login(username="writer", password="pw-12345!")

        self.save_page(stickers=[{"reward": self.sticker.pk, "x": 500, "y": -20, "scale": 9}])

        placed = JournalSticker.objects.get()
        self.assertEqual((placed.x, placed.y, placed.scale), (100, 0, 2.5))

    def test_empty_entry_is_not_saved(self):
        self.client.login(username="writer", password="pw-12345!")

        response = self.save_page(content="")

        self.assertContains(response, "Write something")
        self.assertFalse(Journal.objects.filter(user=self.user).exists())

    def test_list_shows_only_own_decorated_entries(self):
        self.earn(self.user)
        self.client.login(username="writer", password="pw-12345!")
        self.save_page(
            content="Saw a nice sunset", background=self.background.pk,
            stickers=[{"reward": self.sticker.pk, "x": 50, "y": 50}],
        )

        response = self.client.get("/journals/")

        self.assertContains(response, "Saw a nice sunset")
        self.assertContains(response, "rewards/backgrounds/nature.svg")
        self.assertContains(response, 'class="journal-sticker"')
        self.assertNotContains(response, "Someone else&#x27;s secret")

    def test_rewards_page_shows_used_copies(self):
        self.earn(self.user, times=2)
        self.client.login(username="writer", password="pw-12345!")
        self.save_page(stickers=[{"reward": self.sticker.pk, "x": 50, "y": 50}])

        self.assertContains(self.client.get("/rewards/"), "1 used on journal pages")


class CompleteQuestTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="quester", password="pw-12345!")
        self.quest = Quest.objects.create(title="Read a book", category="learning")
        self.reward = Reward.objects.create(name="Bookmark", item_type="sticker")
        self.reward.quests.add(self.quest)
        self.today = timezone.localdate()
        self.url = f"/quests/{self.quest.pk}/complete/"

    def test_requires_login(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(QuestCompletion.objects.exists())

    def test_get_is_not_allowed(self):
        self.client.login(username="quester", password="pw-12345!")

        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_marks_completed_today_and_awards_reward(self):
        self.client.login(username="quester", password="pw-12345!")

        self.client.post(self.url)

        completion = QuestCompletion.objects.get(user=self.user, quest=self.quest)
        self.assertTrue(completion.completed_status)
        self.assertEqual(completion.quest_date, self.today)
        self.assertEqual(completion.completed_date, self.today)
        self.assertTrue(UserReward.objects.filter(user=self.user, reward=self.reward).exists())

    def test_already_completed_today_is_not_changed(self):
        original = QuestCompletion.objects.create(
            user=self.user, quest=self.quest, quest_date=self.today,
            completed_status=True, completed_date=self.today,
        )
        self.client.login(username="quester", password="pw-12345!")

        response = self.client.post(self.url, follow=True)

        self.assertContains(response, "already completed")
        self.assertEqual(QuestCompletion.objects.count(), 1)
        original.refresh_from_db()
        self.assertEqual(original.completed_date, self.today)

    def test_past_completions_are_not_changed(self):
        past_day = date(2026, 9, 26)
        past = QuestCompletion.objects.create(
            user=self.user, quest=self.quest, quest_date=past_day,
            completed_status=True, completed_date=past_day,
        )
        self.client.login(username="quester", password="pw-12345!")

        self.client.post(self.url)

        past.refresh_from_db()
        self.assertEqual(past.completed_date, past_day)
        self.assertEqual(QuestCompletion.objects.filter(user=self.user).count(), 2)

    def test_started_but_unfinished_quest_gets_completed(self):
        QuestCompletion.objects.create(
            user=self.user, quest=self.quest, quest_date=self.today,
            completed_status=False,
        )
        self.client.login(username="quester", password="pw-12345!")

        self.client.post(self.url)

        completion = QuestCompletion.objects.get(user=self.user, quest=self.quest)
        self.assertTrue(completion.completed_status)
        self.assertEqual(completion.completed_date, self.today)

    def test_quest_pages_show_done_today(self):
        self.client.login(username="quester", password="pw-12345!")
        self.client.post(self.url)

        self.assertContains(self.client.get("/quests/"), "done today")
        self.assertContains(self.client.get(f"/quests/{self.quest.pk}/"), "Completed today")

    def test_each_completion_earns_another_copy_of_the_reward(self):
        QuestCompletion.objects.create(
            user=self.user, quest=self.quest, quest_date=date(2026, 9, 26),
            completed_status=True, completed_date=date(2026, 9, 26),
        ).award_rewards()
        self.client.login(username="quester", password="pw-12345!")

        response = self.client.post(self.url, follow=True)

        self.assertContains(response, "You earned: Bookmark")
        self.assertEqual(UserReward.objects.filter(user=self.user, reward=self.reward).count(), 2)
        self.assertContains(self.client.get("/rewards/"), "you have 2")


class AccessProtectionTests(TestCase):
    PRIVATE_PAGES = [
        "/journals/", "/users/", "/forums/nearby/", "/reports/",
        "/export/csv/", "/export/json/", "/vega-lite/",
        "/vega-lite/bar.png", "/vega-lite/completion-timeline.png",
        "/vega-lite/bar.json", "/vega-lite/completion-timeline.json",
        "/quests/", "/rewards/",
    ]
    APIS = [
        "/api/quest-summary/", "/api/completion-timeline/",
        "/api/location/?q=Chicago", "/api/forum-nearby/?q=Chicago",
    ]
    PUBLIC_PAGES = ["/", "/login/", "/register/"]

    def setUp(self):
        self.user = User.objects.create_user(username="member", password="pw-12345!")

    def test_private_pages_redirect_to_login(self):
        for url in self.PRIVATE_PAGES:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith("/login/?next="))

    def test_detail_pages_require_login(self):
        quest = Quest.objects.create(title="Walk", category="general")

        for url in [f"/users/{self.user.pk}/", f"/quests/{quest.pk}/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_apis_return_json_401_when_logged_out(self):
        for url in self.APIS:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"error": "Login required."})

    def test_chart_apis_are_admin_only(self):
        self.client.login(username="member", password="pw-12345!")

        for url in ["/api/quest-summary/", "/api/completion-timeline/"]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json(), {"error": "Admins only."})

    def test_public_pages_stay_open(self):
        for url in self.PUBLIC_PAGES:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_nav_hides_protected_links_before_login(self):
        response = self.client.get("/")

        self.assertContains(response, 'href="/login/"')
        for url in ["/journals/", "/users/", "/reports/", "/vega-lite/", "/forums/nearby/"]:
            self.assertNotContains(response, f'href="{url}"')

    def test_nav_shows_protected_links_after_login(self):
        self.client.login(username="member", password="pw-12345!")

        response = self.client.get("/")

        self.assertContains(response, "Log out (member)")
        self.assertNotContains(response, 'href="/login/"')
        for url in ["/journals/", "/forums/nearby/"]:
            self.assertContains(response, f'href="{url}"')
        for url in ["/users/", "/vega-lite/", "/reports/"]:
            self.assertNotContains(response, f'href="{url}"')

    ADMIN_PAGES = [
        "/reports/", "/export/csv/", "/export/json/", "/users/",
        "/vega-lite/", "/vega-lite/bar.png", "/vega-lite/completion-timeline.png",
        "/vega-lite/bar.json", "/vega-lite/completion-timeline.json",
        "/quests/quest-completion-chart.png",
    ]

    def test_reports_are_admin_only(self):
        self.client.login(username="member", password="pw-12345!")

        for url in self.ADMIN_PAGES + [f"/users/{self.user.pk}/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertNotContains(self.client.get("/"), 'href="/reports/"')

    def test_admin_sees_reports(self):
        User.objects.create_user(username="admin", password="pw-12345!", is_staff=True)
        self.client.login(username="admin", password="pw-12345!")

        for url in self.ADMIN_PAGES + ["/api/quest-summary/", "/api/completion-timeline/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        home = self.client.get("/")
        for url in ["/users/", "/vega-lite/", "/reports/"]:
            self.assertContains(home, f'href="{url}"')
        self.assertNotContains(home, 'href="/journals/"')
        self.assertEqual(self.client.get("/journals/").status_code, 403)
        self.assertContains(self.client.get("/quests/"), "Users Who Completed Each Quest")

    def test_admin_cannot_complete_quests_and_sees_system_rewards(self):
        admin = User.objects.create_user(username="admin", password="pw-12345!", is_staff=True)
        quest = Quest.objects.create(title="Walk", category="general")
        reward = Reward.objects.create(name="Leaf", item_type="sticker")
        reward.quests.add(quest)
        QuestCompletion.objects.create(
            user=self.user, quest=quest, quest_date=date(2026, 9, 26),
            completed_status=True, completed_date=date(2026, 9, 26),
        ).award_rewards()
        self.client.login(username="admin", password="pw-12345!")

        self.assertEqual(self.client.post(f"/quests/{quest.pk}/complete/").status_code, 403)
        self.assertFalse(QuestCompletion.objects.filter(user=admin).exists())
        self.assertNotContains(self.client.get(f"/quests/{quest.pk}/"), "Mark completed today")

        rewards_page = self.client.get("/rewards/")
        self.assertContains(rewards_page, "unlocked by:")
        self.assertContains(rewards_page, "earned 1 time")
        self.assertNotContains(rewards_page, "you have")

    def test_quest_page_hides_completion_stats_from_users(self):
        self.client.login(username="member", password="pw-12345!")

        response = self.client.get("/quests/")

        self.assertNotContains(response, "Users Who Completed Each Quest")
        self.assertNotContains(response, "quest-completion-chart.png")

    def test_logged_out_header_only_has_login_and_signup(self):
        response = self.client.get("/")

        self.assertContains(response, 'href="/login/"')
        self.assertContains(response, 'href="/register/"')
        self.assertNotContains(response, "nav-toggle")
        for url in ["/quests/", "/rewards/", "/journals/", "/forums/nearby/"]:
            self.assertNotContains(response, f'href="{url}"')

    def test_menu_is_hidden_until_button_pressed(self):
        self.client.login(username="member", password="pw-12345!")

        response = self.client.get("/")

        self.assertContains(response, 'class="nav-toggle" aria-expanded="false"')
        self.assertContains(response, 'id="site-nav" hidden')

    def test_logout_logs_user_out(self):
        self.client.login(username="member", password="pw-12345!")

        response = self.client.post("/logout/")

        self.assertRedirects(response, "/")
        self.assertEqual(self.client.get("/journals/").status_code, 302)
