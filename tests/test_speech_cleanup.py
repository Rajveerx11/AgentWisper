from agent_whisper.speech_cleanup import clean_spoken_text


def test_removes_hesitations_and_boundary_fillers() -> None:
    result = clean_spoken_text(
        "Um, create the route, you know, then run the tests. Uh, ship it."
    )
    assert result.text == "Create the route, then run the tests. Ship it."
    assert result.removed_count == 3


def test_keeps_words_that_can_carry_meaning() -> None:
    text = "Use a map like this kind of structure."
    assert clean_spoken_text(text).text == text


def test_keeps_you_know_when_it_is_sentence_content() -> None:
    for text in (
        "Make sure you know which provider is selected.",
        "You know which provider is selected.",
        "Send this to the ER team.",
    ):
        assert clean_spoken_text(text).text == text


def test_cleanup_is_safe_for_empty_text() -> None:
    assert clean_spoken_text("  ").text == ""
