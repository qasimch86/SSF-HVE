"""Text normalisation. Without it the scorer measures typography."""
import pytest

from ssf_hve.scoring.normalise import normalise, words_to_numbers


@pytest.mark.parametrize("raw,expected", [
    ("a thirty-four percent higher rate", "a 34% higher rate"),
    ("one thousand eight hundred and seventy-three people", "1873 people"),
    ("One hundred eighty-seven of six hundred two", "187 of 602"),
    ("sixty milligrams on alternate days", "60 milligrams on alternate days"),
    ("walked about fourteen metres further", "walked about 14 metres further"),
])
def test_number_words_become_digits(raw, expected):
    assert normalise(raw) == expected


def test_percentage_points_not_mangled():
    assert "percentage points" in normalise("a difference of 1.0 percentage points")


@pytest.mark.parametrize("raw,needle", [
    ("On daytime functioning, it didn't.", "did not"),
    ("Immune memory isn't indexed", "is not"),
    ("that won't happen", "will not"),
    ("it can't show causation", "cannot"),
    ("it can not show causation", "cannot"),
])
def test_contractions_expand(raw, needle):
    assert needle in normalise(raw)


def test_ordinary_words_untouched():
    assert normalise("an important point") == "an important point"


def test_normalisation_is_idempotent():
    once = normalise("it didn't cut risk by forty-two percent")
    assert normalise(once) == once
