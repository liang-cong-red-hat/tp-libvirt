import re

from virttest import libvirt_version
from virttest import virsh
from virttest.libvirt_xml import vm_xml
from virttest.utils_test import libvirt
from virttest.utils_libvirt import libvirt_disk

from provider.backingchain import blockcommand_base
from provider.backingchain import check_functions
from provider.virtual_disk import disk_base


def run(test, params, env):
    """
    Do blockcopy with different qcow2 properties

    1) Prepare image with properties and snap chain
    2) Do blockcopy.
    3) Check result.
    """

    def setup_test():
        """
        Prepare image with properties and snap chain
        """
        test.log.info("SETUP:Prepare image with properties and snap chain")
        if property_item == "with_datastore":
            libvirt.create_local_disk("file", path=datastore_path, size=image_size,
                                      disk_format=image_format)
        libvirt.create_local_disk("file", path=image_path, size=image_size,
                                  disk_format=image_format, extra=image_extras)
        check_property(image_path, property_item)

        prepare_disk()
        test_obj.backingchain_common_setup(
            create_snap=True, snap_num=1, snap_path=snap_path, extra=snap_extra)

        if property_item == "extended_l2_and_cluster_size":
            check_property(test_obj.snap_path_list[0], property_item)
        check_obj.check_backingchain_from_vmxml(disk_type, target_disk, expected_chain_after_snap)

    def run_test():
        """
        Do blockcopy.
        """
        test.log.info("TEST_STEP1:Do blockcopy.")
        virsh.blockcopy(vm_name, target_disk, copy_image,
                        options=blockcopy_option,
                        ignore_status=False,
                        debug=True)

        test.log.info("TEST_STEP2:Check guest xml and image properties "
                      "after blockcopy.")
        check_obj.check_backingchain_from_vmxml(disk_type, target_disk,
                                                [copy_image])

        if property_item == "extended_l2_and_cluster_size":
            check_property(copy_image, property_item)

        test.log.info("TEST_STEP3: Write file in guest")
        libvirt_disk.check_virtual_disk_io(vm, target_disk)

    def teardown_test():
        """
        Clean data.
        """
        test.log.info("TEST_TEARDOWN: Clean up env.")
        test_obj.backingchain_common_teardown()
        test_obj.clean_file(copy_image)
        test_obj.clean_file(image_path)
        if datastore_path:
            test_obj.clean_file(datastore_path)

        bkxml.sync()

    def check_property(path, property_item):
        """
        Check the property value

        :param path: The image path.
        :param property_item: The property you want to check.
        """
        if property_item == "extended_l2_and_cluster_size":
            check_obj.check_image_info(path, 'extended l2',
                                       expected_extended_l2)

            cluster_size_value = int(re.findall(r"\d+", cluster_size)[0])*1024*1024
            check_obj.check_image_info(path, 'csize',
                                       cluster_size_value)
        elif property_item == "with_datastore":
            check_obj.check_image_info(path, 'data file', datastore_path)

    def prepare_disk():
        """
        Prepare encryption or normal disk.
        """
        if encryption_disk:
            test_obj.prepare_secret_disk(image_path, secret_disk_dict)
        else:
            test_obj.new_image_path = disk_obj.add_vm_disk(
                disk_type, disk_dict, new_image_path=image_path)

    libvirt_version.is_libvirt_feature_supported(params)
    # Process cartesian parameters
    vm_name = params.get("main_vm")
    target_disk = params.get('target_disk')
    disk_type = params.get('disk_type')
    disk_dict = eval(params.get('disk_dict', '{}'))
    blockcopy_option = params.get('blockcopy_option')
    secret_disk_dict = eval(params.get("secret_disk_dict", '{}'))
    snap_extra = params.get('snap_extra')
    image_extras = params.get('image_extras')
    image_format = params.get('image_format')
    image_path = params.get('image_path')
    image_size = params.get('image_size')
    copy_image = params.get('copy_image')
    property_item = params.get('property')
    cluster_size = params.get('cluster_size')
    expected_extended_l2 = params.get('expected_extended_l2')
    datastore_path = params.get("datastore_path")
    snap_path = params.get("snap_path")
    expected_chain_after_snap = eval(params.get("expected_chain_after_snap", '{}'))
    encryption_disk = params.get('enable_encrypt_disk', 'no') == "yes"

    vm = env.get_vm(vm_name)
    vmxml = vm_xml.VMXML.new_from_inactive_dumpxml(vm_name)
    bkxml = vmxml.copy()

    # Create object
    test_obj = blockcommand_base.BlockCommand(test, vm, params)
    check_obj = check_functions.Checkfunction(test, vm, params)
    disk_obj = disk_base.DiskBase(test, vm, params)

    try:
        setup_test()
        run_test()

    finally:
        teardown_test()
