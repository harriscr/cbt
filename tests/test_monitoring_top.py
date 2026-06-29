"""Tests for the top monitoring backend."""

# pylint: disable=protected-access

from typing import Any, Optional
from unittest.mock import MagicMock, mock_open, patch

from monitoring.top_monitoring import TopMonitoring


def _make_monitor(
    pid_dir: str = "/var/run/ceph",
    user: str = "ceph",
    mconfig: Optional[dict[str, Any]] = None,
) -> TopMonitoring:
    """Construct a TopMonitoring instance with mocked settings."""
    if mconfig is None:
        mconfig = {}
    with (
        patch("monitoring.base.settings") as mock_base_settings,
        patch("monitoring.top_monitoring.settings") as mock_settings,
        patch("monitoring.top_monitoring.common.pdsh"),
    ):
        mock_base_settings.getnodes.return_value = "resolved-nodes"
        mock_settings.cluster.get.side_effect = lambda key, default=None: {
            "pid_dir": pid_dir,
            "user": user,
        }.get(key, default)
        return TopMonitoring(mconfig)


def test_default_nodes_is_osds() -> None:
    """DEFAULT_NODES must be ['osds']."""
    assert TopMonitoring.DEFAULT_NODES == ["osds"]


def test_init_stores_cluster_settings() -> None:
    """__init__ reads pid_dir and user from settings.cluster."""
    monitor = _make_monitor(pid_dir="/run/ceph", user="admin")
    assert monitor._pid_dir == "/run/ceph"
    assert monitor._user == "admin"


def test_init_stores_default_args() -> None:
    """__init__ uses the default top argument string when mconfig has no 'args'."""
    monitor = _make_monitor()
    assert monitor._top_cmd == "top"
    assert monitor._pid_glob == "osd.*.pid"
    assert "{pid}" in monitor._args
    assert "{top_dir}" in monitor._args


def test_init_accepts_custom_args() -> None:
    """__init__ accepts custom top_cmd, args, and pid_glob from mconfig."""
    monitor = _make_monitor(mconfig={"top_cmd": "htop", "args": "-d 1", "pid_glob": "*.pid"})
    assert monitor._top_cmd == "htop"
    assert monitor._args == "-d 1"
    assert monitor._pid_glob == "*.pid"


def test_start_local_node_runs_top_for_each_pid() -> None:
    """start() runs top locally for each matching pid file."""
    mkdir_runner = MagicMock()
    local_runner = MagicMock()
    with (
        patch("monitoring.base.settings") as mock_base_settings,
        patch("monitoring.top_monitoring.settings") as mock_settings,
        patch("monitoring.top_monitoring.common.pdsh", return_value=mkdir_runner) as mock_pdsh,
        patch("monitoring.top_monitoring.common.get_localnode", return_value="node1"),
        patch("monitoring.top_monitoring.common.sh", return_value=local_runner) as mock_sh,
        patch("monitoring.top_monitoring.glob.glob", return_value=["/var/run/ceph/osd.1.pid"]),
        patch("builtins.open", mock_open(read_data="42\n")),
    ):
        mock_base_settings.getnodes.return_value = "resolved-nodes"
        mock_settings.cluster.get.side_effect = lambda key, default=None: {
            "pid_dir": "/var/run/ceph",
            "user": "ceph",
        }.get(key, default)
        monitor = TopMonitoring({})

        monitor.start("/tmp/output")

    mock_pdsh.assert_called_once_with("resolved-nodes", "mkdir -p -m0755 -- /tmp/output/top")
    mkdir_runner.communicate.assert_called_once_with()
    expected_cmd = "top -b -H -1 -p 42 -n 30 > /tmp/output/top/42_osd_top.out"
    mock_sh.assert_called_once_with("node1", expected_cmd)
    assert monitor._top_runners == [local_runner]


def test_start_remote_node_uses_pdsh_loop() -> None:
    """start() dispatches via pdsh for-loop when no local node is available."""
    mkdir_runner = MagicMock()
    remote_runner = MagicMock()
    with (
        patch("monitoring.base.settings") as mock_base_settings,
        patch("monitoring.top_monitoring.settings") as mock_settings,
        patch("monitoring.top_monitoring.common.pdsh") as mock_pdsh,
        patch("monitoring.top_monitoring.common.get_localnode", return_value=None),
    ):
        mock_base_settings.getnodes.return_value = "resolved-nodes"
        mock_settings.cluster.get.side_effect = lambda key, default=None: {
            "pid_dir": "/var/run/ceph",
            "user": "ceph",
        }.get(key, default)
        mock_pdsh.side_effect = [mkdir_runner, remote_runner]
        monitor = TopMonitoring({})

        monitor.start("/tmp/output")

    mock_pdsh.assert_any_call("resolved-nodes", "mkdir -p -m0755 -- /tmp/output/top")
    mock_pdsh.assert_any_call(
        "resolved-nodes",
        [
            "for pid in `cat /var/run/ceph/osd.*.pid`;",
            "do",
            "top -b -H -1 -p ${pid} -n 30 > /tmp/output/top/${pid}_osd_top.out",
            ";",
            "done",
        ],
    )


def test_stop_kills_local_top_runners() -> None:
    """stop() kills locally started runners when present."""
    runner = MagicMock()
    monitor = _make_monitor()
    monitor._top_runners = [runner]

    with patch("monitoring.top_monitoring.common.pdsh") as mock_pdsh:
        monitor.stop(None)

    runner.kill.assert_called_once_with()
    mock_pdsh.assert_not_called()


def test_stop_uses_pdsh_when_no_local_runners_exist() -> None:
    """stop() issues pkill via pdsh when no local runners are tracked."""
    stop_runner = MagicMock()
    monitor = _make_monitor()

    with patch("monitoring.top_monitoring.common.pdsh", return_value=stop_runner) as mock_pdsh:
        monitor.stop(None)

    mock_pdsh.assert_called_once_with("resolved-nodes", r"sudo pkill -SIGINT -f top\ ")
    stop_runner.communicate.assert_called_once_with()


def test_stop_chowns_output_files_when_directory_is_provided() -> None:
    """stop() adjusts ownership of top output files when a directory is given."""
    stop_runner = MagicMock()
    chown_runner = MagicMock()
    monitor = _make_monitor(user="ceph")

    with patch("monitoring.top_monitoring.common.pdsh") as mock_pdsh:
        mock_pdsh.side_effect = [stop_runner, chown_runner]
        monitor.stop("/tmp/output")

    mock_pdsh.assert_any_call("resolved-nodes", r"sudo pkill -SIGINT -f top\ ")
    mock_pdsh.assert_any_call("resolved-nodes", "sudo chown ceph.ceph /tmp/output/top/*top.out")
