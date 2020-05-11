import logging
import os
import time

import yaml
from nebula.driver import driver
from nebula.netconsole import netconsole
from nebula.network import network
from nebula.pdu import pdu
from nebula.tftpboot import tftpboot
from nebula.uart import uart
import nebula.errors as ne

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class manager:
    """ Board Manager """

    def __init__(self, monitor_type="uart", configfilename=None, extras=None):
        # Check if config info exists in yaml
        self.configfilename = configfilename
        self.monitor_type = monitor_type
        if configfilename:
            stream = open(configfilename, "r")
            configs = yaml.safe_load(stream)
            stream.close()
        else:
            configs = None

        if "netconsole" in monitor_type.lower():
            monitor_uboot = netconsole(port=6666, logfilename="uboot.log")
            monitor_kernel = netconsole(port=6669, logfilename="kernel.log")
            self.monitor = [monitor_uboot, monitor_kernel]
        elif "uart" in monitor_type.lower():
            if "uart-config" not in configs:
                configfilename = None
            else:
                configfilename = self.configfilename
            u = uart(yamlfilename=configfilename)
            self.monitor = [u]

            self.driver = driver(yamlfilename=configfilename)

        if "network-config" not in configs:
            configfilename = None
        else:
            configfilename = self.configfilename
        self.net = network(yamlfilename=configfilename)

        if "pdu-config" not in configs:
            configfilename = None
        else:
            configfilename = self.configfilename
        self.power = pdu(yamlfilename=configfilename)

        self.boot_src = tftpboot()

        self.tftp = False

    def get_status(self):
        pass

    def load_boot_bin(self):
        pass

    def _check_files_exist(self, *args):
        for filename in args:
            if not os.path.exists(filename):
                raise Exception(filename + " not found or does not exist")

    def board_reboot_uart_net_pdu(
        self, system_top_bit_path, bootbinpath, uimagepath, devtreepath
    ):
        """ Manager when UART, PDU, and Network are available """
        self._check_files_exist(
            system_top_bit_path, bootbinpath, uimagepath, devtreepath
        )
        try:
            # Flush UART
            self.monitor[0]._read_until_stop()  # Flush
            # Check if Linux is accessible
            log.info("Checking if Linux is accessible")
            out = self.monitor[0].get_uart_command_for_linux("uname -a", "Linux")
            if not out:
                raise ne.LinuxNotReached

            # Get IP over UART
            ip = self.monitor[0].get_ip_address()
            if not ip:
                self.monitor[0].request_ip_dhcp()
                ip = self.monitor[0].get_ip_address()
                if not ip:
                    raise ne.NetworkNotFunctional
            if ip != self.net.dutip:
                log.info("DUT IP changed to: " + str(ip))
                self.net.dutip = ip
                self.driver.uri = "ip:" + ip

            # Update board over SSH and reboot
            self.net.update_boot_partition(
                bootbinpath=uimagepath, uimagepath=uimagepath, devtreepath=devtreepath
            )
            log.info("Waiting for reboot to complete")
            time.sleep(30)

        except ne.LinuxNotReached:
            # Power cycle
            log.info("SSH reboot failed again after power cycling")
            log.info("Forcing UART override on power cycle")
            log.info("Power cycling")
            self.power.power_cycle_board()

            # Enter u-boot menu
            self.monitor[0]._enter_uboot_menu_from_power_cycle()

            if self.tftp:
                # Move files to correct position for TFTP
                # self.monitor[0].load_system_uart_from_tftp()

                # Load boot files over tftp
                self.monitor[0].load_system_uart_from_tftp()

            else:
                # Load boot files
                self.monitor[0].load_system_uart(
                    system_top_bit_filename=system_top_bit_path,
                    kernel_filename=uimagepath,
                    devtree_filename=devtreepath,
                )
            # NEED A CHECK HERE OR SOMETHING
            log.info("Waiting for boot to complete")
            time.sleep(30)

        # Check is networking is working
        if self.net.ping_board():
            ip = self.monitor[0].get_ip_address()
            if not ip:
                self.monitor[0].request_ip_dhcp()
                ip = self.monitor[0].get_ip_address()
                if not ip:
                    raise ne.NetworkNotFunctionalAfterBootFileUpdate

        # Check SSH
        if self.net.check_ssh():
            raise ne.SSHNotFunctionalAfterBootFileUpdate

        print("Home sweet home")

    def board_reboot(self):
        # Try to reboot over SSH first
        try:
            self.net.reboot_board()
        except Exception as ex:
            # Try power cycling
            log.info("SSH reboot failed, power cycling " + str(ex))
            self.power.power_cycle_board()
            time.sleep(60)
            try:
                ip = self.monitor[0].get_ip_address()
                if not ip:
                    self.monitor[0].request_ip_dhcp()
                    ip = self.monitor[0].get_ip_address()
                log.info("IP Address Found: " + str(ip))
                if ip != self.net.dutip:
                    log.info("DUT IP changed to: " + str(ip))
                    self.net.dutip = ip
                    self.driver.uri = "ip:" + ip
                self.net.check_board_booted()
            except Exception as ex:
                log.info("Still cannot get to board after power cycling")
                log.info("Exception: " + str(ex))
                try:
                    log.info("SSH reboot failed again after power cycling")
                    log.info("Forcing UART override on power cycle")
                    log.info("Power cycling")
                    self.power.power_cycle_board()
                    log.info("Spamming ENTER to get UART console")
                    for k in range(60):
                        self.monitor[0]._write_data("\r\n")
                        time.sleep(0.1)

                    self.monitor[0].load_system_uart()
                    time.sleep(20)
                    log.info("IP Address: " + str(self.monitor[0].get_ip_address()))
                    self.net.check_board_booted()
                except Exception as ex:
                    raise Exception("Getting board back failed", str(ex))

    def run_test(self):
        # Move BOOT.BIN, kernel and devtree to target location
        # self.boot_src.update_boot_files()

        # Start loggers
        for mon in self.monitor:
            mon.start_log()
        # Power cycle board
        self.board_reboot()

        # Check IIO context and devices
        self.driver.run_all_checks()

        # Run tests

        # Stop and collect logs
        for mon in self.monitor:
            mon.stop_log()

    def board_reboot_auto(
        self, system_top_bit_path, bootbinpath, uimagepath, devtreepath
    ):
        """ Automatically select loading mechanism
            based on current class setup """
        self.board_reboot_uart_net_pdu(
            system_top_bit_path=system_top_bit_path,
            bootbinpath=bootbinpath,
            uimagepath=uimagepath,
            devtreepath=devtreepath,
        )


if __name__ == "__main__":
    # import pathlib

    # p = pathlib.Path(__file__).parent.absolute()
    # p = os.path.split(p)
    # p = os.path.join(p[0], "resources", "nebula-zed-fmcomms2.yaml")

    # m = manager(configfilename=p)
    # m.run_test()
    pass
