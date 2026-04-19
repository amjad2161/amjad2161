from brainiac.core.localization import Localization


def test_localization_phrases_and_rtl():
    loc = Localization()
    assert loc.phrase("turn_left", "en") == "Turn left"
    assert "ש" in loc.phrase("turn_left", "he")
    assert "انعطف" in loc.phrase("turn_left", "ar")
    assert loc.is_rtl("he") is True
    assert loc.is_rtl("ar") is True
    assert loc.is_rtl("en") is False
