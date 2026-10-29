"""prepare-pfs mode (PFS-only refresh, exFAT intact)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pfs_batchkit.workflows import run_prepare_pfs_device


def test_run_prepare_pfs_device_delegates_with_pfs_only() -> None:
    with patch("pfs_batchkit.workflows.run_prepare_device") as mock_run:
        mock_run.return_value.exit_code = 0
        mock_run.return_value.messages = ()
        mock_run.return_value.layout = None
        mock_run.return_value.opl_mount = None
        run_prepare_pfs_device(Path("/dev/sdb"), force=True, cfg_dev=True)
        mock_run.assert_called_once()
        kwargs = mock_run.call_args.kwargs
        assert kwargs["pfs_only"] is True
        assert kwargs["init_pfs"] is True
        assert kwargs["format_exfat"] is False
        assert kwargs["scaffold_opl"] is False
        assert kwargs["cfg_dev"] is True
