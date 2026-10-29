''' heclib message level comes from DSS_MESSAGE_LEVEL, 1 when not set or invalid '''
import pytest

from pyheclib import message_level_from_env


@pytest.mark.parametrize("value, level", [
	(None, 1), ("", 1), ("abc", 1), ("-1", 1), ("16", 1), ("2.5", 1),
	("0", 0), ("4", 4), (" 3 ", 3), ("15", 15),
])
def test_message_level_from_env(monkeypatch, value, level):
	if value is None:
		monkeypatch.delenv("DSS_MESSAGE_LEVEL", raising=False)
	else:
		monkeypatch.setenv("DSS_MESSAGE_LEVEL", value)
	assert message_level_from_env() == level
