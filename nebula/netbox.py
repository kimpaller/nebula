import pynetbox
from nebula.common import utils


class netbox(utils):
    """NetBox interface"""

    def __init__(
        self,
        ip=None,
        port=None,
        token=None,
        yamlfilename=None,
        board_name=None,
    ):
        self.netbox_server = None
        self.netbox_server_port = None
        self.netbox_api_token = None
        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
        )

        if ip:
            self.netbox_server = ip
        if port:
            self.netbox_server_port = port
        if token:
            self.netbox_api_token = token

        self.nb = pynetbox.api(\
         f"http://{self.netbox_server}:{self.netbox_server_port}",
            token=self.netbox_api_token)

    def get_mac_from_asset_tag(self, asset_tag):
        dev = self.nb.dcim.devices.get(asset_tag=asset_tag)
        if not dev:
            raise Exception(f"No devices for with asset tage: {asset_tag}")
        intf = self.nb.dcim.interfaces.get(device_id=dev.id)
        return intf.mac_address

    def get_uart_address_from_asset_tag(self, asset_tag):
        dev = self.nb.dcim.devices.get(asset_tag=asset_tag)
        if not dev:
            raise Exception(f"No devices for with asset tage: {asset_tag}")
        ports = self.nb.dcim.console_ports.filter(device_id=dev.id)
        for ps in ports:
            if ps.name == 'uart':
                port = ps
        return port.label

    def set_ip_address_with_asset_tag(self, asset_tag, address):
        dev = self.nb.dcim.devices.get(asset_tag=asset_tag)
        if not dev:
            raise Exception(f"No devices for with asset tage: {asset_tag}assigned")
        intf = self.nb.dcim.interfaces.get(device_id=dev.id)
        if not intf:
            raise Exception(f"{dev.id} has no assigned interfaces")
        ipas = self.nb.ipam.ip_addresses.all()
        for ipa in ipas:
            if ipa.assigned_object.id == intf.id:
                ipa.address = address + '/24'
                ipa.save()
