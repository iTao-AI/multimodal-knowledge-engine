from typing import Any, cast

import pytest

from mke.domain.source_discovery import SourceLocatorRange


def test_source_ranges_are_strict() -> None:
    range_type = SourceLocatorRange
    for args in [
        ("page", 0, 1),
        ("page", 3, 2),
        ("timestamp_ms", 2, 2),
        ("mixed", 1, 2),
        ("page", True, 2),
        ("timestamp_ms", -1, 2),
    ]:
        with pytest.raises(ValueError):
            range_type(*cast(Any, args))
    assert range_type("page", 1, 3).end == 3
    assert range_type("timestamp_ms", 0, 3).start == 0
