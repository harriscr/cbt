""" Unit tests for the Benchmarkrawfio class """

import unittest
import hashlib
import json
import benchmarkfactory
import settings
from cluster.ceph import Ceph


class TestBenchmarkrawfio(unittest.TestCase):
    """ Sanity tests for Benchmarkrawfio """
    archive_dir = "/tmp"
    iteration = {'acceptable': [1,2,3], 'iteration': 0}
    cluster = {}
    cl_name = "tools/invariant.yaml"
    bl_name = "tools/baseline.json"
    bl_json = {}
    bl_md5 = 'aa42ab3c2da0e01ecec18add853f7d79'
    md5_returned = None

    @classmethod
    def setUpClass(cls):
        with open(cls.bl_name, 'rb') as f:
            data = f.read()
            f.close()
        cls.md5_returned = hashlib.md5(data).hexdigest()
        settings.mock_initialize(config_file=cls.cl_name)
        cls.cluster = Ceph.mockinit(settings.cluster)
        with open(cls.bl_name, 'r') as f:
            cls.bl_json = json.load(f)
            f.close()

    @classmethod
    def tearDownClass(cls):
        cls.cluster = None
        cls.bl_json = None

    def test_valid_baseline(self):
        """ Verify the baseline has not been compromised """
        self.assertEqual( self.bl_md5, str(self.md5_returned) )

    def test_valid_archive_dir(self):
        """ Basic sanity attribute identity archive_dir check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['archive_dir'], b.__dict__['archive_dir'])

    def test_valid_block_device_list(self):
        """ Basic sanity attribute identity block_device_list check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['block_device_list'], b.__dict__['block_device_list'])

    def test_valid_block_devices(self):
        """ Basic sanity attribute identity block_devices check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['block_devices'], b.__dict__['block_devices'])

    def test_valid_cmd_path(self):
        """ Basic sanity attribute identity cmd_path check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['cmd_path'], b.__dict__['cmd_path'])

    def test_valid_cmd_path_full(self):
        """ Basic sanity attribute identity cmd_path_full check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['cmd_path_full'], b.__dict__['cmd_path_full'])

    def test_valid_concurrent_procs(self):
        """ Basic sanity attribute identity concurrent_procs check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['concurrent_procs'], b.__dict__['concurrent_procs'])

    def test_valid_config(self):
        """ Basic sanity attribute identity config check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['config'], b.__dict__['config'])

    def test_valid_direct(self):
        """ Basic sanity attribute identity direct check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['direct'], b.__dict__['direct'])

    def test_valid_fio_cmd(self):
        """ Basic sanity attribute identity fio_cmd check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['fio_cmd'], b.__dict__['fio_cmd'])

    def test_valid_fio_out_format(self):
        """ Basic sanity attribute identity fio_out_format check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['fio_out_format'], b.__dict__['fio_out_format'])

    def test_valid_iodepth(self):
        """ Basic sanity attribute identity iodepth check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['iodepth'], b.__dict__['iodepth'])

    def test_valid_ioengine(self):
        """ Basic sanity attribute identity ioengine check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['ioengine'], b.__dict__['ioengine'])

    def test_valid_log_bw(self):
        """ Basic sanity attribute identity log_bw check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['log_bw'], b.__dict__['log_bw'])

    def test_valid_log_iops(self):
        """ Basic sanity attribute identity log_iops check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['log_iops'], b.__dict__['log_iops'])

    def test_valid_log_lat(self):
        """ Basic sanity attribute identity log_lat check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['log_lat'], b.__dict__['log_lat'])

    def test_valid_mode(self):
        """ Basic sanity attribute identity mode check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['mode'], b.__dict__['mode'])

    def test_valid_numjobs(self):
        """ Basic sanity attribute identity numjobs check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['numjobs'], b.__dict__['numjobs'])

    def test_valid_op_size(self):
        """ Basic sanity attribute identity op_size check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['op_size'], b.__dict__['op_size'])

    def test_valid_osd_ra(self):
        """ Basic sanity attribute identity osd_ra check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['osd_ra'], b.__dict__['osd_ra'])

    def test_valid_osd_ra_changed(self):
        """ Basic sanity attribute identity osd_ra_changed check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['osd_ra_changed'], b.__dict__['osd_ra_changed'])

    def test_valid_out_dir(self):
        """ Basic sanity attribute identity out_dir check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['out_dir'], b.__dict__['out_dir'])

    def test_valid_ramp(self):
        """ Basic sanity attribute identity ramp check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['ramp'], b.__dict__['ramp'])

    def test_valid_rate_iops(self):
        """ Basic sanity attribute identity rate_iops check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['rate_iops'], b.__dict__['rate_iops'])

    def test_valid_run_dir(self):
        """ Basic sanity attribute identity run_dir check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['run_dir'], b.__dict__['run_dir'])

    def test_valid_rwmixread(self):
        """ Basic sanity attribute identity rwmixread check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['rwmixread'], b.__dict__['rwmixread'])

    def test_valid_rwmixwrite(self):
        """ Basic sanity attribute identity rwmixwrite check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['rwmixwrite'], b.__dict__['rwmixwrite'])

    def test_valid_startdelay(self):
        """ Basic sanity attribute identity startdelay check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['startdelay'], b.__dict__['startdelay'])

    def test_valid_time(self):
        """ Basic sanity attribute identity time check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['time'], b.__dict__['time'])

    def test_valid_total_procs(self):
        """ Basic sanity attribute identity total_procs check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['total_procs'], b.__dict__['total_procs'])

    def test_valid_valgrind(self):
        """ Basic sanity attribute identity valgrind check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['valgrind'], b.__dict__['valgrind'])

    def test_valid_vol_size(self):
        """ Basic sanity attribute identity vol_size check"""
        b = benchmarkfactory.get_object(self.archive_dir,
                                            self.cluster, 'rawfio', self.iteration)
        self.assertEqual(self.bl_json['rawfio']['vol_size'], b.__dict__['vol_size'])

if __name__ == '__main__':
    unittest.main()
