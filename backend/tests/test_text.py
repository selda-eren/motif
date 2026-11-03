from motif.text import locate_quote, segment


def test_segmentation_is_stable_and_lossless(cave):
    passages = segment(cave.text)
    assert len(passages) == 9
    for p in passages:
        assert cave.text[p.start:p.end] == p.text
        assert not p.text[0].islower(), "passages should not start mid-sentence"
    assert passages[0].start == 0


def test_short_replies_stay_with_their_question():
    text = ("A long question " * 40).strip() + "?\n\nYes, he said.\n\n" + ("Next argument " * 40).strip()
    first, second = segment(text, target_words=50, min_tail_words=10)
    assert first.text.endswith("Yes, he said.")
    assert second.text.startswith("Next argument")


def test_locate_quote_tolerates_case_whitespace_and_quote_style():
    passage = "which is true of the mind’s eye,\nquite as much as of the bodily eye"
    span = locate_quote(passage, "Which is true of the mind's eye, quite as much")
    assert span is not None
    assert passage[span[0]:span[1]] == "which is true of the mind’s eye,\nquite as much"


def test_locate_quote_rejects_paraphrase():
    assert locate_quote("the truth would be literally nothing but the shadows", "truth is only shadows") is None
    assert locate_quote("anything", "") is None
