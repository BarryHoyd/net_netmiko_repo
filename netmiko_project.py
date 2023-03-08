"""Program using netmiko for the automation of cisco devices"""
import os
import re
from getpass import getpass
import ipaddress
import yaml
import netmiko
import jinja2

class Session:
    """Used to handle netmiko session"""
    def __init__(self, session_details: dict) -> None:
        """starts instance of netmiko session to passed device

        Args:
            session_details (dict): Contains everything needed for ssh session
        """
        self.session_details = session_details
        self.net_connect = netmiko.BaseConnection

    def make_connection(self) -> None:
        """Used to make ssh connection to cisco ios/nxos/iso telnet"""
        try:
            self.net_connect = netmiko.ConnectHandler(**self.session_details)
            output = self.net_connect.send_command('show ver')
            if "Nexus" in output:
                self.net_connect.disconnect()
                self.session_details['device_type'] = 'cisco_nxos'
                self.net_connect = netmiko.ConnectHandler(**self.session_details)
        except:
            try:
                self.session_details['device_type'] = 'cisco_iso_telnet'
                self.net_connect = netmiko.ConnectHandler(**self.session_details)
            except:
                print(f"Connection could not be establised to {self.session_details['host']}")

    def send_show_command(self, command: str, use_textfsm: bool) -> str:
        """Sends show comamnds to deivce and returns input

        Args:
            ccommand (str): command to run on device
            use_textfsm (bool): decides if textfsm will be used to format output

        Returns:
            str: output of command once run on device
        """
        return self.net_connect.send_command(command_string=command, 
                            read_timeout=100, use_textfsm=use_textfsm)

    def send_config_commands(self, commands: list) -> None:
        """Sends config commands to device

        Args:
            commands (list): list containing all commands to execute
        """
        self.net_connect.send_config_set(config_commands=commands, read_timeout=100)

class YamlReader:
    """Used to get data from yaml data"""
    def __init__(self, yaml_file_path: str) -> None:
        """Used to read in yaml file

        Args:
            yaml_file_path (str): path to yaml file
        """
        with open(yaml_file_path, "r", encoding="utf-8") as stream:
            try:
                self.yaml_file = yaml.safe_load(stream)
            except yaml.YAMLError as error:
                print(error)

    @staticmethod
    def calculate_subnet_mask(ip_with_subnet: str) -> str:
        """Used to calculate subnet mask based on x.x.x.x/x address format

        Args:
            ip_with_subnet (str): ip in x.x.x.x/x format

        Returns:
            str: subnet mask
        """
        subnet_mask = ipaddress.ip_interface(ip_with_subnet)
        return subnet_mask.netmask.compressed

    @staticmethod
    def format_ip_address(unformatted_ip: str) -> str:
        """Formats ip by removing subnet mask

        Args:
            unformatted_ip (str): ip address including mask

        Returns:
            str: ip address minus mask
        """
        return unformatted_ip[:unformatted_ip.find("/")]

    def read_loopback(self) -> dict:
        """Used to get loopback details from yaml file

        Returns:
            dict: dictonary of info needed to make loopbacks
        """
        loopback_commands = self.yaml_file['Loopback']
        loopback_commands['mask'] = self.calculate_subnet_mask(loopback_commands['ip'])
        loopback_commands['ip'] = self.format_ip_address(loopback_commands['ip'])
        return loopback_commands

class CommandGenerator:
    """Used to generate commands using jinja files"""
    def __init__(self, jinja_file_path: str) -> None:
        """Used to set jinja enviroment up

        Args:
            jinja_file_path (str): file path to jinja folder
        """
        template_loader = jinja2.FileSystemLoader(searchpath=jinja_file_path)
        self.template_env = jinja2.Environment(loader=template_loader)

    @staticmethod
    def convert_to_list(to_convert: str) -> list:
        """convert from str to list

        Args:
            to_convert (str): str of commands including \n characters

        Returns:
            list: list of commands
        """
        return to_convert.split("\n")

    def generate_commands(self, command_data: dict) -> list:
        """Uses jinja templates to generate cisco comamnds

        Args:
            command_data (dict): dict containing all data for comamnds

        Returns:
            list: list of commands
        """
        template = self.template_env.get_template("loopback.j2")
        commands = template.render(config=command_data)
        list_of_commands = self.convert_to_list(commands)
        return list_of_commands
  

def get_device_details(ip_address: str) -> dict:
    """Used to get device_details

    Args:
            ip_address (str): ip address of device to conenct to

    Returns:
        dict: contains everything needed for ssh session
    """

    ip_address = ip_address
    port = int(input("Please enter in the port: "))

    device = {
        'device_type': 'cisco_ios',
        'host': ip_address,
        'port': port,
        'username': input("Please enter the username: "),
        'password': getpass()
    }
    return device

def get_devices_in_network() -> str:
    """Used to all devices connected in a network

    Returns:
        str: device ip address that will be connected to
    """
    ip_address = ""

    #Used to get all connected devices ip addresses
    stream = os.popen('arp -a')
    connected_devices = stream.read()
    connected_devices = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', connected_devices)

    #Used to validate user input
    while True:
        for index, device in enumerate(connected_devices, start=1):
            print(f"[{index}]. {device}")
        try:
            user_index = int(input("Please select the device you would like to conect to: ")) - 1
            if user_index >= 0:
                ip_address = connected_devices[user_index]
                break
            print("Please select a valid device in the range displayed\n")
        except IndexError:
            print("Please select a valid device in the range displayed\n")
        except ValueError:
            print("Please select one of the devices using numbers\n")
  
    print()
    return ip_address

if __name__ == '__main__':

    #Loads YAML input file
    YAML_FILE = "/home/harry/Documents/input.yaml"
    yaml_reader = YamlReader(yaml_file_path=YAML_FILE)
    #Loads Jinja templates
    JINJA_FILE = '/home/harry/Documents/Jinja Templates'
    command_generator = CommandGenerator(jinja_file_path=JINJA_FILE)

    #Establishes ssh session to a device on the network
    ip_address = get_devices_in_network()
    ssh_details = get_device_details(ip_address=ip_address)
    session_one = Session(session_details=ssh_details)
    session_one.make_connection()
    print("Connection successfully made...\n")

    #Loads commands
    details = yaml_reader.read_loopback()
    loopback_commands = command_generator.generate_commands(command_details=details)

    output = session_one.send_show_command(command='show ip int brief', use_textfsm=False)
    print(f"{output}\n")

    session_one.send_config_commands(commands=loopback_commands)

    output = session_one.send_show_command(command='show ip interface brief', use_textfsm=False)
    print(f"{output}\n")

    response = os.system("ping -c 1 10.1.1.1 >/dev/null 2>&1")
    if response == 0:
        print("Creation of Loopback1 successful")
    else:
        print("Creation of Loopback1 unccessful")
