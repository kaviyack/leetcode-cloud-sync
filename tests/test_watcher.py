"""
Tests for the local background watcher module (src/watcher.py).
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from unittest.mock import MagicMock, patch

import pytest

from src.watcher import watch


def test_watcher_runs_and_sleeps(tmp_path):
    with patch("src.watcher.Config.from_env") as mock_config_env, \
         patch("src.watcher.run") as mock_run, \
         patch("time.sleep", side_effect=InterruptedError("stop")), \
         patch("src.watcher.load_dotenv") as mock_load_dotenv, \
         patch("pathlib.Path") as mock_path_cls:

        mock_path_instance = MagicMock()
        mock_path_cls.return_value = mock_path_instance
        mock_path_instance.__truediv__.return_value = tmp_path / "watcher.log"

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.github_repo = "owner/repo"
        mock_config.github_branch = "main"
        mock_config.git_author_name = "Author"
        mock_config.git_author_email = "author@example.com"
        mock_config_env.return_value = mock_config

        mock_run.return_value = 1

        with pytest.raises(InterruptedError, match="stop"):
            watch(interval=10)

        assert mock_run.call_count >= 1
        mock_load_dotenv.assert_called_once()


def test_watcher_adds_rotating_file_handler(tmp_path):
    with patch("src.watcher.Config.from_env") as mock_config_env, \
         patch("src.watcher.run") as mock_run, \
         patch("time.sleep", side_effect=InterruptedError("stop")), \
         patch("src.watcher.load_dotenv"), \
         patch("pathlib.Path") as mock_path_cls:

        mock_path_instance = MagicMock()
        mock_path_cls.return_value = mock_path_instance
        mock_path_instance.__truediv__.return_value = tmp_path / "watcher.log"

        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.github_repo = "owner/repo"
        mock_config.github_branch = "main"
        mock_config.git_author_name = "Author"
        mock_config.git_author_email = "author@example.com"
        mock_config_env.return_value = mock_config

        mock_run.return_value = 0

        root_logger = logging.getLogger()
        root_logger.handlers = [h for h in root_logger.handlers if not isinstance(h, RotatingFileHandler)]

        with pytest.raises(InterruptedError, match="stop"):
            watch(interval=1)

        assert any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers)
