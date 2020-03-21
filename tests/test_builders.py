import os
import shutil

import pytest
from nebula import builder


@pytest.fixture(autouse=True)
def run_around_tests():
    # Before test
    if os.path.isdir("libiio"):
        shutil.rmtree("libiio")
    if os.path.isdir("hdl"):
        shutil.rmtree("hdl")
    if os.path.isdir("u-boot-xlnx"):
        shutil.rmtree("u-boot-xlnx")
    if os.path.isdir("linux"):
        shutil.rmtree("linux")
    yield
    # After test
    if os.path.isdir("libiio"):
        shutil.rmtree("libiio")
    if os.path.isdir("hdl"):
        shutil.rmtree("hdl")
    if os.path.isdir("u-boot-xlnx"):
        shutil.rmtree("u-boot-xlnx")
    if os.path.isdir("linux"):
        shutil.rmtree("linux")


def test_libiio_build():
    b = builder()
    b.analog_clone_build("libiio")
    assert os.path.isfile("libiio/build/libiio.so")


def test_hdl_build():
    b = builder()
    b.analog_clone_build("hdl", "hdl_2018_r2", "fmcomms2", "zed")
    filename = "hdl/projects/fmcomms2/zed/fmcomms2_zed.sdk/system_top.hdf"
    assert os.path.isfile(filename)


def test_uboot_build():
    b = builder()
    b.analog_clone_build(
        "u-boot-xlnx", "xilinx-v2018.2", def_config="zynq_zed_defconfig"
    )
    assert os.path.isfile("u-boot-xlnx/u-boot")


def test_linux_build():
    b = builder()
    b.analog_clone_build("linux", "2018_R2")
    path = "linux/arch/arm/boot/uImage"
    assert os.path.isfile(path)


if __name__ == "__main__":
    test_uboot_build()
