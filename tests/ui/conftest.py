"""Fixtures específicas de la suite de UI."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from framework.data import User
from framework.ui.pages import HomePage, LoginPage


@pytest.fixture
def logged_in_user(page: Page, registered_user: User) -> User:
    """Usuario registrado (vía API) con sesión iniciada en el navegador (vía UI).

    La sesión vive en las cookies del contexto del test, que es exclusivo: no hay
    estado compartido entre tests aunque corran en paralelo.
    """
    LoginPage(page).open().login(registered_user.email, registered_user.password)
    home = HomePage(page).should_be_loaded()
    expect(home.header.logged_in_as).to_contain_text(registered_user.name)
    return registered_user
