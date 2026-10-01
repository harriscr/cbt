"""Unit tests for the Benchmarkcephtestrados class"""

import hashlib
import json
import unittest
from typing import Any, ClassVar

import benchmarkfactory
import settings
from cluster.ceph import Ceph


class TestBenchmarkcephtestrados(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """Sanity tests for Benchmarkcephtestrados"""

    archive_dir = "/tmp"
    iteration: ClassVar[dict[str, Any]] = {"acceptable": [1, 2, 3], "iteration": 0}
    cluster: Any = None
    cl_name = "tools/invariant.yaml"
    bl_name = "tools/baseline.json"
    bl_json: ClassVar[dict[str, Any]] = {}
    bl_md5 = "d632746a671fcdeb9850f242aaec375e"
    md5_returned = None

    @classmethod
    def setUpClass(cls) -> None:
        with open(cls.bl_name, "rb") as f:
            data = f.read()
            f.close()
        cls.md5_returned = hashlib.md5(data).hexdigest()
        settings.mock_initialize(config_file=cls.cl_name)  # type: ignore[no-untyped-call]
        cls.cluster = Ceph.mockinit(settings.cluster)  # type: ignore[no-untyped-call]
        with open(cls.bl_name, encoding="utf-8") as f:
            cls.bl_json = json.load(f)
            f.close()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.cluster = None
        cls.bl_json = {}

    def test_valid_baseline(self) -> None:
        """Verify the baseline has not been compromised"""
        self.assertEqual(self.bl_md5, str(self.md5_returned))

    def test_valid__base_archive_directory(self) -> None:
        """Basic sanity attribute identity _base_archive_directory check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(
            self.bl_json["cephtestrados"]["_base_archive_directory"], b.__dict__["_base_archive_directory"]
        )

    def test_valid__create_report(self) -> None:
        """Basic sanity attribute identity _create_report check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["_create_report"], b.__dict__["_create_report"])

    def test_valid_archive_dir(self) -> None:
        """Basic sanity attribute identity archive_dir check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["archive_dir"], b.__dict__["archive_dir"])

    def test_valid_bools(self) -> None:
        """Basic sanity attribute identity bools check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["bools"], b.__dict__["bools"])

    def test_valid_cmd_path(self) -> None:
        """Basic sanity attribute identity cmd_path check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["cmd_path"], b.__dict__["cmd_path"])

    def test_valid_cmd_path_full(self) -> None:
        """Basic sanity attribute identity cmd_path_full check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["cmd_path_full"], b.__dict__["cmd_path_full"])

    def test_valid_config(self) -> None:
        """Basic sanity attribute identity config check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["config"], b.__dict__["config"])

    def test_valid_log_bw(self) -> None:
        """Basic sanity attribute identity log_bw check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["log_bw"], b.__dict__["log_bw"])

    def test_valid_log_iops(self) -> None:
        """Basic sanity attribute identity log_iops check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["log_iops"], b.__dict__["log_iops"])

    def test_valid_log_lat(self) -> None:
        """Basic sanity attribute identity log_lat check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["log_lat"], b.__dict__["log_lat"])

    def test_valid_osd_ra(self) -> None:
        """Basic sanity attribute identity osd_ra check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["osd_ra"], b.__dict__["osd_ra"])

    def test_valid_osd_ra_changed(self) -> None:
        """Basic sanity attribute identity osd_ra_changed check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["osd_ra_changed"], b.__dict__["osd_ra_changed"])

    def test_valid_out_dir(self) -> None:
        """Basic sanity attribute identity out_dir check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["out_dir"], b.__dict__["out_dir"])

    def test_valid_pool_profile(self) -> None:
        """Basic sanity attribute identity pool_profile check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["pool_profile"], b.__dict__["pool_profile"])

    def test_valid_run_dir(self) -> None:
        """Basic sanity attribute identity run_dir check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["run_dir"], b.__dict__["run_dir"])

    def test_valid_tmp_conf(self) -> None:
        """Basic sanity attribute identity tmp_conf check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["tmp_conf"], b.__dict__["tmp_conf"])

    def test_valid_valgrind(self) -> None:
        """Basic sanity attribute identity valgrind check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["valgrind"], b.__dict__["valgrind"])

    def test_valid_variables(self) -> None:
        """Basic sanity attribute identity variables check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["variables"], b.__dict__["variables"])

    def test_valid_weights(self) -> None:
        """Basic sanity attribute identity weights check"""
        b = benchmarkfactory.get_object(self.archive_dir, self.cluster, "cephtestrados", self.iteration)
        self.assertEqual(self.bl_json["cephtestrados"]["weights"], b.__dict__["weights"])


if __name__ == "__main__":
    unittest.main()
