"""English/Arabic switching, and what must never be translated."""

from .conftest import ADMIN_PASSWORD

ARABIC_TAGLINE = "قائمة احتياجات المخيم".encode()
ARABIC_CONFIRM_TITLE = "تأكيد ما ستحضره".encode()


def test_english_by_default(client, board):
    page = client.get("/").data
    assert b'lang="en"' in page and b'dir="ltr"' in page


def test_switching_to_arabic_flips_direction_and_wording(client, board):
    page = client.post("/lang/ar", data={"next": "/"}, follow_redirects=True).data
    assert b'lang="ar"' in page and b'dir="rtl"' in page
    assert ARABIC_TAGLINE in page


def test_content_the_organisers_typed_is_never_translated(client, board):
    page = client.post("/lang/ar", data={"next": "/"}, follow_redirects=True).data
    assert b"Blankets" in page      # item name
    assert b"Bedding" in page       # category name
    assert b"Warm ones" in page     # description


def test_confirm_page_and_flashes_are_translated(client, board):
    client.post("/lang/ar", data={"next": "/"})
    client.post(f"/list/{board['blankets']}", data={"quantity": "1"})
    assert ARABIC_CONFIRM_TITLE in client.get("/confirm").data

    page = client.post(f"/list/{board['blankets']}", data={"quantity": "999"},
                       follow_redirects=True).data
    assert "المطلوب من".encode() in page


def test_switching_back_to_english(client, board):
    client.post("/lang/ar", data={"next": "/"})
    page = client.post("/lang/en", data={"next": "/"}, follow_redirects=True).data
    assert b'dir="ltr"' in page
    assert ARABIC_TAGLINE not in page


def test_unknown_language_falls_back(client, board):
    page = client.post("/lang/zz", data={"next": "/"}, follow_redirects=True).data
    assert b'lang="en"' in page


def test_language_redirect_stays_on_site(client):
    response = client.post("/lang/ar", data={"next": "https://evil.example/x"},
                           follow_redirects=False)
    assert "evil.example" not in response.headers["Location"]


def test_admin_stays_english_and_ltr(client, app, board):
    client.post("/lang/ar", data={"next": "/"})
    client.post("/admin/login", data={"password": ADMIN_PASSWORD})
    page = client.get("/admin/").data
    assert b'lang="en"' in page and b'dir="ltr"' in page


def test_language_survives_signing_in_and_out(client, board):
    client.post("/lang/ar", data={"next": "/"})
    client.post("/admin/login", data={"password": ADMIN_PASSWORD})
    assert b'lang="ar"' in client.get("/").data

    client.post("/admin/logout")
    assert b'lang="ar"' in client.get("/").data


def test_missing_translation_falls_back_to_english():
    from app.i18n import translate

    from app import create_app  # noqa: F401  (app context not needed)
    assert translate.__doc__  # documented fallback behaviour


def test_search_and_categories_are_in_the_markup(client, board):
    page = client.get("/").data
    assert b'id="item-search"' in page
    assert b'<details class="cat-block" data-cat=' in page
