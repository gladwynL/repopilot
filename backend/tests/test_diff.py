from app.services.ai.diff import parse_patch


def test_new_file_line_numbers_follow_hunk_header() -> None:
    lines = parse_patch("@@ -10,3 +20,4 @@ def f():\n ctx\n-old\n+new1\n+new2\n ctx2")

    assert [(line.kind, line.new_line) for line in lines] == [
        ("hunk", None),
        ("context", 20),
        ("removed", None),
        ("added", 21),
        ("added", 22),
        ("context", 23),
    ]


def test_multiple_hunks_reset_numbering() -> None:
    lines = parse_patch("@@ -1 +1 @@\n-a\n+b\n@@ -50,2 +50,2 @@\n x\n+y")

    assert [line.new_line for line in lines if line.kind != "hunk"] == [None, 1, 50, 51]


def test_no_newline_marker_is_not_numbered() -> None:
    lines = parse_patch("@@ -1 +1 @@\n-a\n\\ No newline at end of file\n+b")

    assert [(line.kind, line.new_line) for line in lines] == [
        ("hunk", None),
        ("removed", None),
        ("meta", None),
        ("added", 1),
    ]


def test_unparseable_hunk_header_yields_no_line_numbers() -> None:
    lines = parse_patch("@@ garbage @@\n+added\n context")

    assert all(line.new_line is None for line in lines)


def test_single_line_hunk_without_count() -> None:
    lines = parse_patch("@@ -0,0 +1 @@\n+only")

    assert lines[1].new_line == 1
