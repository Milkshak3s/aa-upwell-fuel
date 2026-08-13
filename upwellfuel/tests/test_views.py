"""Smoke tests for the page itself.

These run against the local test project (see runtests.py) and check the parts
that unit tests on the arithmetic cannot: that the hooks register, the URLs
resolve, the permissions bite and the template renders.
"""

from django.test import TestCase
from django.urls import reverse

from allianceauth.tests.auth_utils import AuthUtils


def _make_user(username: str, character_id: int, with_permission: bool):
    """A user Auth will let through: logged in, with a main character.

    Every hook-registered view is wrapped in main_character_required, so a user
    without a main is redirected before the view ever runs.
    """
    user = AuthUtils.create_user(username)
    AuthUtils.add_main_character_2(
        user,
        name=username.title(),
        character_id=character_id,
        corp_id=2001,
        corp_name="Test Corp",
        corp_ticker="TEST",
    )
    if with_permission:
        AuthUtils.add_permission_to_user_by_name("structures.basic_access", user)
    return user


class ViewAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user("planner", 1001, with_permission=True)
        cls.outsider = _make_user("outsider", 1002, with_permission=False)

    def test_page_renders_for_a_permitted_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("upwellfuel:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upwell Fuel")

    def test_page_is_refused_without_the_structures_permission(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("upwellfuel:index"))
        self.assertNotEqual(response.status_code, 200)

    def test_empty_state_is_explained_rather_than_blank(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("upwellfuel:index"))
        self.assertContains(response, "view_all_structures")

    def test_period_comes_from_the_query_string(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("upwellfuel:index"), {"days": 7})
        self.assertEqual(response.context["period_days"], 7)

    def test_a_nonsense_period_falls_back_to_the_default(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("upwellfuel:index"), {"days": "soon"})
        self.assertEqual(response.context["period_days"], 30)

    def test_an_absurd_period_is_clamped(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("upwellfuel:index"), {"days": 99999})
        self.assertEqual(response.context["period_days"], 365)

    def test_csv_export_is_served_as_a_download(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("upwellfuel:export_csv"), {"days": 14})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("upwell-fuel-14d.csv", response["Content-Disposition"])
        self.assertIn("Blocks needed (14d)", response.content.decode())


class MenuHookTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user("planner", 1001, with_permission=True)
        cls.outsider = _make_user("outsider", 1002, with_permission=False)

    def _render_menu_for(self, user):
        from django.test import RequestFactory

        from upwellfuel.auth_hooks import UpwellFuelMenuItem

        request = RequestFactory().get("/")
        request.user = user
        return UpwellFuelMenuItem().render(request)

    def test_menu_item_is_shown_to_a_permitted_user(self):
        self.assertIn("Upwell Fuel", self._render_menu_for(self.user))

    def test_menu_item_is_hidden_from_everyone_else(self):
        self.assertEqual(self._render_menu_for(self.outsider), "")
