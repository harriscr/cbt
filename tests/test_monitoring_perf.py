"""Tests for the perf monitoring backend."""

# pylint: disable=protected-access

from unittest.mock import MagicMock, mock_open, patch

from monitoring.perf_monitoring import PerfMonitoring


def test_start_local_node_runs_perf_for_each_pid() -> None:
    """Start perf locally for each matching pid file."""
    mkdir_runner = MagicMock()
    local_runner = MagicMock()
    with (
        patch("monitoring.base.settings") as mock_base_settings,
        patch("monitoring.perf_monitoring.settings") as mock_settings,
        patch("monitoring.perf_monitoring.common.pdsh", return_value=mkdir_runner) as mock_pdsh,
        patch("monitoring.perf_monitoring.common.get_localnode", return_value="node1"),
        patch("monitoring.perf_monitoring.common.sh", return_value=local_runner) as mock_sh,
        patch("monitoring.perf_monitoring.glob.glob", return_value=["/var/run/ceph/osd.1.pid"]),
        patch("builtins.open", mock_open(read_data="123\n")),
    ):
        mock_base_settings.getnodes.return_value = "resolved-nodes"
        mock_settings.cluster.get.side_effect = lambda key, default=None: {
            "pid_dir": "/var/run/ceph",
            "user": "ceph",
        }.get(key, default)
        monitor = PerfMonitoring({"args": "stat -p {pid} -o {perf_dir}/perf_stat.{pid}"})

        monitor.start("/tmp/output")

    mock_pdsh.assert_called_once_with("resolved-nodes", "mkdir -p -m0755 -- /tmp/output/perf")
    mkdir_runner.communicate.assert_called_once_with()
    mock_sh.assert_called_once_with("node1", "sudo perf stat -p 123 -o /tmp/output/perf/perf_stat.123 &")
    assert monitor._perf_runners == [local_runner]
    assert monitor._perf_dir == "/tmp/output/perf"


def test_start_remote_node_uses_pdsh_loop() -> None:
    """Start perf remotely through pdsh when no local node is available."""
    mkdir_runner = MagicMock()
    remote_runner = MagicMock()
    with (
        patch("monitoring.base.settings") as mock_base_settings,
        patch("monitoring.perf_monitoring.settings") as mock_settings,
        patch("monitoring.perf_monitoring.common.pdsh") as mock_pdsh,
        patch("monitoring.perf_monitoring.common.get_localnode", return_value=None),
    ):
        mock_base_settings.getnodes.return_value = "resolved-nodes"
        mock_settings.cluster.get.side_effect = lambda key, default=None: {
            "pid_dir": "/var/run/ceph",
            "user": "ceph",
        }.get(key, default)
        mock_pdsh.side_effect = [mkdir_runner, remote_runner]
        monitor = PerfMonitoring({"args": "stat -p {pid} -o {perf_dir}/perf_stat.{pid}"})

        monitor.start("/tmp/output")

    mock_pdsh.assert_any_call("resolved-nodes", "mkdir -p -m0755 -- /tmp/output/perf")
    mock_pdsh.assert_any_call(
        "resolved-nodes",
        [
            "for pid in `cat /var/run/ceph/osd.*.pid`;",
            "do",
            "sudo perf stat -p ${pid} -o /tmp/output/perf/perf_stat.${pid} &",
            ";",
            "done",
        ],
    )


def test_stop_kills_local_perf_runners() -> None:
    """Kill locally started perf runners when present."""
    runner = MagicMock()
    with (
        patch("monitoring.base.settings") as mock_base_settings,
        patch("monitoring.perf_monitoring.settings") as mock_settings,
    ):
        mock_base_settings.getnodes.return_value = "resolved-nodes"
        mock_settings.cluster.get.side_effect = lambda key, default=None: {
            "pid_dir": "/var/run/ceph",
            "user": "ceph",
        }.get(key, default)
        monitor = PerfMonitoring({"args": "stat -p {pid} -o {perf_dir}/perf_stat.{pid}"})
        monitor._perf_runners = [runner]

        monitor.stop(None)

    runner.kill.assert_called_once_with()


def test_stop_uses_pdsh_when_no_local_runners_exist() -> None:
    """Stop perf remotely through pdsh when no local runners are tracked."""
    stop_runner = MagicMock()
    with (
        patch("monitoring.base.settings") as mock_base_settings,
        patch("monitoring.perf_monitoring.settings") as mock_settings,
        patch("monitoring.perf_monitoring.common.pdsh", return_value=stop_runner) as mock_pdsh,
    ):
        mock_base_settings.getnodes.return_value = "resolved-nodes"
        mock_settings.cluster.get.side_effect = lambda key, default=None: {
            "pid_dir": "/var/run/ceph",
            "user": "ceph",
        }.get(key, default)
        monitor = PerfMonitoring({"args": "stat -p {pid} -o {perf_dir}/perf_stat.{pid}"})

        monitor.stop(None)

    mock_pdsh.assert_called_once_with("resolved-nodes", r"sudo pkill -SIGINT -f perf\ ")
    stop_runner.communicate.assert_called_once_with()


def test_stop_chowns_output_files_when_directory_is_provided() -> None:
    """Adjust ownership of generated perf files when an output directory is given."""
    stop_runner = MagicMock()
    chown_data_runner = MagicMock()
    chown_stat_runner = MagicMock()
    with (
        patch("monitoring.base.settings") as mock_base_settings,
        patch("monitoring.perf_monitoring.settings") as mock_settings,
        patch("monitoring.perf_monitoring.common.pdsh") as mock_pdsh,
    ):
        mock_base_settings.getnodes.return_value = "resolved-nodes"
        mock_settings.cluster.get.side_effect = lambda key, default=None: {
            "pid_dir": "/var/run/ceph",
            "user": "ceph",
        }.get(key, default)
        mock_pdsh.side_effect = [stop_runner, chown_data_runner, chown_stat_runner]
        monitor = PerfMonitoring({"args": "stat -p {pid} -o {perf_dir}/perf_stat.{pid}"})

        monitor.stop("/tmp/output")

    mock_pdsh.assert_any_call("resolved-nodes", r"sudo pkill -SIGINT -f perf\ ")
    mock_pdsh.assert_any_call("resolved-nodes", "sudo chown ceph.ceph /tmp/output/perf/perf.data")
    mock_pdsh.assert_any_call("resolved-nodes", "sudo chown ceph.ceph /tmp/output/perf/perf_stat.*")


def test_get_cpu_cycles_returns_total_cycles() -> None:
    """Sum cycle counts from all perf stat output files."""
    with (
        patch("monitoring.base.settings") as mock_base_settings,
        patch("monitoring.perf_monitoring.settings") as mock_settings,
        patch("monitoring.perf_monitoring.glob.glob", return_value=["/tmp/output/perf"]),
        patch("monitoring.perf_monitoring.os.listdir", return_value=["perf_stat.1", "perf_stat.2"]),
        patch(
            "builtins.open",
            side_effect=[
                mock_open(read_data="1,000 cycles user\n").return_value,
                mock_open(read_data="2,500 cycles user\n").return_value,
            ],
        ),
    ):
        mock_base_settings.getnodes.return_value = "resolved-nodes"
        mock_settings.cluster.get.side_effect = lambda key, default=None: {
            "pid_dir": "/var/run/ceph",
            "user": "ceph",
        }.get(key, default)
        monitor = PerfMonitoring({"args": "stat -p {pid} -o {perf_dir}/perf_stat.{pid}"})

        assert monitor.get_cpu_cycles("/tmp/output") == 3500


def test_get_cpu_cycles_returns_none_when_cycles_are_missing() -> None:
    """Return None when perf output does not contain a cycles line."""
    with (
        patch("monitoring.base.settings") as mock_base_settings,
        patch("monitoring.perf_monitoring.settings") as mock_settings,
        patch("monitoring.perf_monitoring.glob.glob", return_value=["/tmp/output/perf"]),
        patch("monitoring.perf_monitoring.os.listdir", return_value=["perf_stat.1"]),
        patch("builtins.open", mock_open(read_data="nothing to match\n")),
    ):
        mock_base_settings.getnodes.return_value = "resolved-nodes"
        mock_settings.cluster.get.side_effect = lambda key, default=None: {
            "pid_dir": "/var/run/ceph",
            "user": "ceph",
        }.get(key, default)
        monitor = PerfMonitoring({"args": "stat -p {pid} -o {perf_dir}/perf_stat.{pid}"})

        assert monitor.get_cpu_cycles("/tmp/output") is None
