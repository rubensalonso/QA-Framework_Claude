"""Fixtures específicas de la suite de UI."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from framework.data import User
from framework.ui.pages import HomePage
from framework.ui.session import login_via_http


@pytest.fixture
def logged_in_user(page: Page, registered_user: User, base_url: str) -> User:
    """Usuario registrado (vía API) con sesión iniciada en el navegador (vía HTTP).

    Ni el registro ni el login pasan por los formularios de la UI: los tests que usan esta fixture
    (checkout, logout...) no dependen de que esos formularios funcionen, que tienen sus propios
    tests en ``test_authentication.py``. La sesión vive en las cookies del contexto del test, que es
    exclusivo: no hay estado compartido entre tests aunque corran en paralelo.
    """
    login_via_http(page.context, base_url, registered_user.email, registered_user.password)
    home = HomePage(page).open()
    expect(home.header.logged_in_as).to_contain_text(registered_user.name)
    return registered_user
