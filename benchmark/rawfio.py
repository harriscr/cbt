import re
import common
import settings
import monitoring
import time
import logging
from pathlib import Path
from typing import Union

from post_processing.report import Report, ReportOptions

from .benchmark import Benchmark

logger = logging.getLogger("cbt")


class RawFio(Benchmark):

    def __init__(self, archive_dir, cluster, config):
        super(RawFio, self).__init__(archive_dir, cluster, config)
        # comma-separated list of block devices to use inside the client host/VM/container
        self.block_device_list = config.get('block_devices', '/dev/vdb')
        self.block_devices = [d.strip() for d in self.block_device_list.split(',')]
        self.concurrent_procs = config.get('concurrent_procs', len(self.block_devices))
        self.total_procs = self.concurrent_procs * len(settings.getnodes('clients').split(','))
        self.fio_out_format = "json"
        self.time = str(config.get('time', '300'))
        self.ramp = str(config.get('ramp', '0'))
        self.startdelay = config.get('startdelay', None)
        self.rate_iops = config.get('rate_iops', None)
        self.iodepth = config.get('iodepth', 16)
        self.direct = config.get('direct', 1)
        self.numjobs = config.get('numjobs', 1)
        self.mode = config.get('mode', 'write')
        self.rwmixread = config.get('rwmixread', 50)
        self.rwmixwrite = 100 - self.rwmixread
        self.ioengine = config.get('ioengine', 'libaio')
        self.op_size = config.get('op_size', 4194304)
        self.vol_size = config.get('vol_size', 65536)
        self.cmd_path = config.get('cmd_path', '/usr/bin/fio')
        # FIXME there are too many permutations, need to put results in SQLITE3
        if not self._workloads.exist():
            self.run_dir = (
                f"{self.run_dir}raw_ra-{int(self.osd_ra):08d}/op_size-{int(self.op_size):08d}/"
                f"concurrent_procs-{int(self.total_procs):03d}/iodepth-{int(self.iodepth):03d}/{self.mode}"
            )
        self.out_dir = self.archive_dir

    # def exists(self):
    #     if os.path.exists(self.out_dir):
    #         logger.info('Skipping existing test in %s.', self.out_dir)
    #         return True
    #     return False

    def initialize(self):
        super(RawFio, self).initialize()
        if self._workloads.exist():
            logger.info("Workloads:\n    %s", self._workloads.get_names().replace(" ", "\n"))
        common.pdsh(settings.getnodes('clients'),
                    'sudo rm -rf %s' % self.run_dir,
                    continue_if_error=False).communicate()
        common.make_remote_dir(self.run_dir)
        clnts = settings.getnodes('clients')
        logger.info('creating mountpoints...')

        logger.info('Attempting to initialize fio files...')
        initializer_list = []
        for i in range(self.concurrent_procs):
            b = self.block_devices[i % len(self.block_devices)]
            fiopath = b
            pre_cmd = 'sudo %s --rw=write -ioengine=%s --bs=%s ' % (self.cmd_path, self.ioengine, self.op_size)
            pre_cmd = '%s --size %dM --name=%s --output-format=%s> /dev/null' % (
                pre_cmd, self.vol_size, fiopath, self.fio_out_format)
            initializer_list.append(common.pdsh(clnts, pre_cmd,
                                                continue_if_error=False))
        for p in initializer_list:
            p.communicate()

        # Create the run directory
        common.pdsh(clnts, 'rm -rf %s' % self.run_dir,
                    continue_if_error=False).communicate()
        common.make_remote_dir(self.run_dir)

    def run(self):
        super(RawFio, self).run()
        clnts = settings.getnodes('clients')

        # We'll always drop caches for raw fio
        self.dropcaches()

        if self._workloads.exist():
            self._workloads.set_benchmark_type("rawfio")
            self._workloads.set_executable(self.cmd_path)
            self._workloads.run()
        else:
            monitoring.start(self.run_dir)

            time.sleep(5)

            logger.info('Starting raw fio %s test.', self.mode)

            fio_process_list = []
            for i in range(self.concurrent_procs):
                b = self.block_devices[i % len(self.block_devices)]
                fiopath = b
                out_file = '%s/output.%d' % (self.run_dir, i)
                fio_cmd = 'sudo %s' % self.cmd_path
                fio_cmd += ' --rw=%s' % self.mode
                if self.mode == 'readwrite' or self.mode == 'randrw':
                    fio_cmd += ' --rwmixread=%s --rwmixwrite=%s' % (self.rwmixread, self.rwmixwrite)
                fio_cmd += ' --ioengine=%s' % self.ioengine
                fio_cmd += ' --runtime=%s' % self.time
                fio_cmd += ' --ramp_time=%s' % self.ramp
                if self.startdelay:
                    fio_cmd += ' --startdelay=%s' % self.startdelay
                if self.rate_iops:
                    fio_cmd += ' --rate_iops=%s' % self.rate_iops
                fio_cmd += ' --numjobs=%s' % self.numjobs
                fio_cmd += ' --direct=%s' % self.direct
                fio_cmd += ' --bs=%dB' % self.op_size
                fio_cmd += ' --iodepth=%d' % self.iodepth
                fio_cmd += ' --size=%dM' % self.vol_size
                if self.log_iops:
                    fio_cmd += ' --write_iops_log=%s' % out_file
                if self.log_bw:
                    fio_cmd += ' --write_bw_log=%s' % out_file
                if self.log_lat:
                    fio_cmd += ' --write_lat_log=%s' % out_file
                fio_cmd += ' --output-format=%s' % self.fio_out_format
                if 'recovery_test' in self.cluster.config:
                    fio_cmd += ' --time_based'
                fio_cmd += ' --name=%s > %s' % (fiopath, out_file)
                logger.debug("FIO CMD: %s" % fio_cmd)
                fio_process_list.append(common.pdsh(clnts, fio_cmd, continue_if_error=False))
            for p in fio_process_list:
                p.communicate()
            monitoring.stop(self.run_dir)
            logger.info('Finished raw fio test')

        source_directory: str = f'{self.run_dir}/*'
        if self._workloads.exist():
            source_directory = f'{self._workloads.get_base_run_directory()}/*'
        common.sync_files(source_directory, self.out_dir)
        self.analyze(self.out_dir)

        if self._create_report:
            report_config: dict[str, Union[str, bool]] = settings.report
            output_directory: str = report_config.get('output_directory', f"{self.out_dir}/report")
            report_options: ReportOptions = ReportOptions(
                archives=[f"{self.archive_dir}"],
                output_directory=output_directory,
                results_file_root="json_output",
                create_pdf=report_config.get("create_pdf", False),
                force_refresh=report_config.get("force_refresh", False),
                no_error_bars=report_config.get("no_error_bars", False),
                comparison=False,
                plot_resources=report_config.get("plot_resource", False),
            )
            report: Report = Report(report_options)
            report.generate()

    def parse(self, out_dir):
        """
        Filters the JSON output from the fio output file and writes it to a
        separate file. Works with both --output-format=json and json,normal.

        Unlike librbdfio, this uses the out_dir argument as the search root
        because self.out_dir and self.archive_dir are different paths in rawfio.
        """
        archive_path: Path = Path(out_dir)
        files_to_process: list[Path] = [
            file for file in archive_path.glob("**/output.*") if re.search(r"output\.\d+$", str(file))
        ]
        for file in files_to_process:
            with file.open("r", encoding="utf-8") as input_file:
                output_file_name: str = f"{file.parent}/json_output{file.name[file.name.find('.'):]}"
                output_path = Path(output_file_name)
                found: bool = False
                with output_path.open("w", encoding="utf-8") as output_file:
                    for line in input_file.readlines():
                        if re.search("^{$", line):
                            found = True
                        if re.search("^}$", line):
                            output_file.write(line)
                            found = False
                            break
                        if found:
                            output_file.write(line)

    def analyze(self, out_dir):
        logger.info('Convert results to json format.')
        self.parse(out_dir)

    def cleanup(self):
        super(RawFio, self).cleanup()
        clnts = settings.getnodes('clients')

        logger.debug("Kill fio: %s" % clnts)
        common.pdsh(clnts, 'killall fio').communicate()
        time.sleep(3)
        common.pdsh(clnts, 'killall -9 fio').communicate()

    def set_client_param(self, param, value):
        cmd = 'find /sys/block/vd* ! -iname vda -exec sudo sh -c "echo %s > {}/queue/%s" \;' % (value, param)
        common.pdsh(settings.getnodes('clients'), cmd).communicate()

    def __str__(self):
        return "%s\n%s\n%s" % (self.run_dir, self.out_dir, super(RawFio, self).__str__())

    def recovery_callback(self):
        common.pdsh(settings.getnodes('clients'), 'sudo killall fio').communicate()
