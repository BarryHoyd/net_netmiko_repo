"""Program using netmiko for the automation of cisco devices"""
import os
import re
from getpass import getpass
from datetime import datetime
import ipaddress
import sys
import yaml
import netmiko
import jinja2
from tinydb import TinyDB, where

class UserInput:
    """Used to gather and validate user input"""
    def __init__(self) -> None:
        """No attributes to assign"""

    @staticmethod
    def get_device_details(device_ip_address: str) -> dict:
        """Used to get device_details

        Args:
            ip_address (str): ip address of device to conenct to

        Returns:
            dict: contains everything needed for ssh session
        """

        device = {
            'device_type': 'cisco_ios',
            'host': device_ip_address,
            'port': 22,
            'username': input("Please enter the username: "),
            'password': getpass()
        }
        return device

    @staticmethod
    def validate_input_list(list_to_validate: list, message_to_be_displayed: str) -> str:
        """Used to vlaidate user input when selecting from a list
        
        Args:
            list_to_validate (list): list to validate user choice for
            message_to_be_displayed (str): message to be displayed to console
        
        Returns:
            str: valid user choice
        """
        #Used to validate user input
        while True:
            for index, device in enumerate(list_to_validate, start=1):
                print(f"[{index}]. {device}")
            try:
                user_index = int(input(message_to_be_displayed)) - 1
                if user_index >= 0:
                    user_selected_element = list_to_validate[user_index]
                    break
                print("Please select a valid option in the range displayed\n")
            except IndexError:
                print("Please select a valid option in the range displayed\n")
            except ValueError:
                if user_index == "Q":
                    sys.exit()
                else:
                    print("Please select one of the options using numbers\n")
        print()
        return user_selected_element

    @staticmethod
    def validate_input_int(start: int, end: int) -> int:
        """Used to validate user input when an int is used

        Args:
            start (int): lowest amount user can select
            end (int): highest amount user can select

        Returns:
            int: valid user choice
        """
        while True:
            try:
                user_int_input = int(input("Please make a selection: "))
                if user_int_input >= start and user_int_input <= end:
                    break
            except ValueError:
                return -1
        return user_int_input

    @staticmethod
    def get_devices_in_network() -> str:
        """Used to all devices connected in a network

        Returns:
            str: device ip address that will be connected to
        """
        #Used to get all connected devices ip addreS
        stream = os.popen('arp -a')
        connected_devices = stream.read()
        connected_devices = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', connected_devices)
        connected_devices.append("10.0.0.1") #R1
        if len(connected_devices) == 0:
            print("ERROR no devices visable in the network!")
            sys.exit()
        return ["192.168.100.1", "192.168.200.1"]

class Session:
    """Used to handle netmiko session"""
    def __init__(self, session_details: dict, user_input: UserInput) -> None:
        """starts instance of netmiko session to passed device

        Args:
            session_details (dict): Contains everything needed for ssh session
            user_input (UserInput): Used to validate user input
        """
        self.session_details = session_details
        self.net_connect = netmiko.BaseConnection
        self.user_input = user_input

    def make_connection(self) -> None:
        """Used to make ssh connection to cisco ios/nxos/iso telnet"""
        try:
            self.net_connect = netmiko.ConnectHandler(**self.session_details)
            output = self.net_connect.send_command('show ver')
            if "Nexus" in output:
                self.net_connect.disconnect()
                self.session_details['device_type'] = 'cisco_nxos'
                self.net_connect = netmiko.ConnectHandler(**self.session_details)
        except netmiko.NetmikoTimeoutException:
            try:
                self.session_details['device_type'] = 'cisco_iso_telnet'
                self.net_connect = netmiko.ConnectHandler(**self.session_details)
            except netmiko.NetmikoAuthenticationException:
                print(f"Connection could not be establised to {self.session_details['host']}")
        except netmiko.NetmikoAuthenticationException:
            print(f"Connection could not be establised to {self.session_details['host']}. Login incorrect")

    def send_show_command(self, command: str, use_textfsm: bool) -> str:
        """Sends show comamnds to deivce and returns input

        Args:
            command (str): command to run on device
            use_textfsm (bool): decides if textfsm will be used to format output

        Returns:
            str: output of command once run on device
        """
        return self.net_connect.send_command(command_string=command,
                            read_timeout=100, use_textfsm=use_textfsm)

    def get_full_config(self, use_textfsm: bool) -> str:
        """Gets full running config

        Args:
            use_textfsm (bool): decides if textfsm will be used to format output

        Returns:
            str: full running config of device
        """
        return self.send_show_command('show run', use_textfsm=use_textfsm)

    def get_hostname(self) -> str:
        """Gets the host name of the device

        Returns:
            str: name of device
        """
        device_details = self.get_full_config(use_textfsm=True)
        name = device_details[device_details.find("hostname") + 9:]
        name = name[:name.find("\n"):]
        return name

    def send_config_commands(self, commands: list) -> None:
        """Sends config commands to device

        Args:
            commands (list): list containing all commands to execute
        """
        self.net_connect.send_config_set(config_commands=commands, read_timeout=100)

    def send_show_interface_commands(self, interface_choice: str) -> None:
        """Used to determine what view commands to send (send)

        Args:
            interface_choice (str): physical, loopback, Vlan, port channel
        """
        if interface_choice == "Full":
            full = FullConfig(jinja_file_path="", yaml_file_path="", interface_type=interface_choice, user_input=self.user_input, session=self)
            full.show_running_config()
        else:
            interface = Interface(jinja_file_path=JINJA_FILE, yaml_file_path=YAML_FILE, interface_type=interface_choice, user_input=self.user_input, session=self)
            interface.show(is_user_interactable=True, is_for_delete=False)

    def send_create_interface_commands(self, interface_to_create: str) -> None:
        """Used to determine what view commands to send (create)

        Args:
            interface_to_create (str): physical, loopback, Vlan, port channel
        """
        if interface_to_create == "Physical":
            physical_interface = Physical(jinja_file_path=JINJA_FILE, yaml_file_path=YAML_FILE, interface_type=interface_to_create, user_input=self.user_input, session=self)
            physical_interface.assign()
        else:
            interface = Interface(jinja_file_path=JINJA_FILE, yaml_file_path=YAML_FILE, interface_type=interface_to_create, user_input=self.user_input, session=self)
            interface.create()

    def send_delete_interface_commands(self, interface_type_to_delete) -> None:
        """Used to determine what view commands to send (delete)

        Args:
            interface_type_to_delete (str): physical, loopback, Vlan, port channel_
        """
        if interface_type_to_delete != "Physical":
            interface = Interface(jinja_file_path=JINJA_FILE, yaml_file_path=YAML_FILE, interface_type=interface_type_to_delete, user_input=self.user_input, session=self)
            interface.show(is_user_interactable=True, is_for_delete=True)
        else:
            physical_interface = Physical(jinja_file_path=JINJA_FILE, yaml_file_path=YAML_FILE, interface_type=interface_type_to_delete, user_input=self.user_input, session=self)
            physical_interface.delete_physical()

class Interface:
    """Used to handle interfaces"""
    def __init__(self, jinja_file_path: str, yaml_file_path: str, interface_type: str, user_input: UserInput, session: Session) -> None:
        """Used to set up interfaces

        Args:
            Args:
            jinja_file_path (str): file path to jinja folder
            yaml_file_path (str): pathh to yaml input file
            interface_type (str): type of interface
            user_input (UserInput): ref to user input class
            session (Session): ref to session class
        """
        template_loader = jinja2.FileSystemLoader(searchpath=jinja_file_path)
        self.template_env = jinja2.Environment(loader=template_loader)
        try:
            with open(yaml_file_path, "r", encoding="utf-8") as stream:
                try:
                    self.yaml_file = yaml.safe_load(stream)
                except yaml.YAMLError as error:
                    print(error)
        except ValueError:
            pass
        except FileNotFoundError:
            pass
        self.interface_type = interface_type
        self.user_input = user_input
        self.session = session

    @staticmethod
    def check_ip_format(ip_to_check: str) -> bool:
        """Used to check that ip address is in the correct format as is not already used in the network

        Args:
            ip_to_check (str): ip to be checked for usage and format

        Returns:
            bool: valid or not
        """
        try:
            formatted_ip_to_check = ip_to_check[:ip_to_check.find("/")]
            if ipaddress.ip_address(formatted_ip_to_check):
                ipv4_address = ipaddress.IPv4Address(formatted_ip_to_check)
                for item in DB_FILE:
                    net = ipaddress.IPv4Network(item['ip_address'])
                    for host in net.hosts():
                        if ipv4_address in (host, net.broadcast_address):
                            print(f"\nERROR! {ip_to_check} is already reserved in the network!\n")
                            return False
                return True
        except ValueError:
            print("Please input a valid ip address! \n")
        except IndexError:
            print("Please input a valid ip address! \n")
        return False

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
    def get_next_ip_address(network_address: str) -> str:
        """Formats ip by removing subnet mask

        Args:
            network_address (str): ip address including mask

        Returns:
            str: ip address minus mask
        """
        hosts = []
        try:
            network = ipaddress.IPv4Network(network_address)
            for host in network.hosts():
                hosts.append(host)
            return str(hosts[0])
        except ValueError:
            print("ERROR not starting ip at network address!")
            return None

    @staticmethod
    def get_all_ip_addresses(string_of_ip_addresses: str) -> list:
        """_summary_

        Args:
            string_of_ip_addresses (str): string containing 1 or more ip addresses

        Returns:
            list: list of ip addresses
        """
        list_of_ip_addresses = re.findall(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", string_of_ip_addresses)
        return list_of_ip_addresses

    @staticmethod
    def ping(ip_address_to_ping: str, interface_created_name: str) -> None:
        """Used to ping an ip address

        Args:
            ip_address_to_ping (str): ip to ping check against
            interface_created_name (str): for output message
        """
        response = os.system(f"ping -c 1 {ip_address_to_ping} >/dev/null 2>&1")
        if response == 0:
            print(f"Creation of {interface_created_name} successful")
        else:
            print(f"Creation of {interface_created_name} unccessful")

    @staticmethod
    def edit_db(ip_address: str, add_to_db: bool) -> None:
        """Used to update TinyDB

        Args:
            ip_address (str): ip address to be added or removed
            add_or_remove (bool): add or remove
        """
        if add_to_db:
            DB_FILE.insert({'ip_address': ip_address})
            print(f"\n{ip_address} has been added to the data base!")
        else:
            removed_ip_address = ""
            for item in DB_FILE:
                if ipaddress.IPv4Address(ip_address) in ipaddress.IPv4Network(item['ip_address']):
                    removed_ip_address = item['ip_address']
                    DB_FILE.remove(where('ip_address') == item['ip_address'])
                    break
            print(f"{removed_ip_address} has been removed from the data base!")

    def write_output(self, data_to_write: str) -> None:
        """Used to write output config to file

        Args:
            data_to_write (str): config to be written to file
        """
        print("[1]. Write to file")
        print("[2]. Do not write to file")
        write_to_file = self.user_input.validate_input_int(start = 1, end = 2)
        if write_to_file == 1:
            with open(OUTPUT_FILE, "a", encoding="utf-8") as write_file:
                write_file.write("=====================================\n")
                now = datetime.now()
                write_file.write(f"{now.strftime('%m/%d/%Y, %H:%M:%S')}\n")
                write_file.write("-------------------------------------\n\n")
                write_file.writelines(data_to_write)
                write_file.write("\n")
            print("\nWritten to output file!")
        elif write_to_file == 2:
            print("\nNot written to output file!")

    def generate_commands(self, command_data: dict) -> list:
        """Uses jinja templates to generate cisco comamnds

        Args:
            command_data (dict): dict containing all data for comamnds

        Returns:
            list: list of commands
        """
        template = self.template_env.get_template("Base.j2")
        commands = template.render(config=command_data)
        list_of_commands = commands.split("\n")
        return list_of_commands

    def check_name(self, name_to_check: str) -> bool:
        """checks if name is already in use

        Args:
            name_to_check (str): given name

        Returns:
            bool: is valid
        """
        names_of_interfaces = []
        interfaces = self.get_all_interfaces_of_type()
        for interface in interfaces:
            names_of_interfaces.append(interface['interface'])
        for name in names_of_interfaces:
            if name == name_to_check:
                return False
        return True

    def get_all_interfaces_of_type(self) -> list:
        """Get all interfaces of specified type

        Returns:
            list: all interfaces of disered type
        """
        all_interfaces_of_type = []
        all_interfaces = self.session.send_show_command(command='show interfaces',use_textfsm=True)
        if self.interface_type == "Physical":
            list_of_physical_interfaces = ["Ethernet", "Serial", "BRI"]
            for physical_interface in list_of_physical_interfaces:
                for interface in all_interfaces:
                    if physical_interface in interface['interface'] and "." not in interface['interface']:
                        all_interfaces_of_type.append(interface)
        elif self.interface_type == "Vlan":
            for interface in all_interfaces:
                if "." in interface['interface']:
                    all_interfaces_of_type.append(interface)
        else:
            for interface in all_interfaces:
                if self.interface_type in interface['interface']:
                    all_interfaces_of_type.append(interface)
        return all_interfaces_of_type

    def get_user_interface(self, is_user_interactable: bool) -> str:
        """Used to get single interface

        Args:
            is_user_interactable (bool): used to see if user can interact with the console

        Returns:
            str: single interface name
        """
        list_of_interfaces = self.get_all_interfaces_of_type()

        if len(list_of_interfaces) == 0:
            print(f"\nNo {self.interface_type} found!")
            input("Press enter to continue...")
        else:
            while True:
                print(f"\nThese are the {self.interface_type} on the device:")
                for index, formatted_interface in enumerate(list_of_interfaces, start=1):
                    print(f"[{index}]. {formatted_interface['interface']}")
                if is_user_interactable:
                    interface_index = self.user_input.validate_input_int(1, len(list_of_interfaces))
                    if interface_index == -1:
                        break
                    interface_to_view = list_of_interfaces[interface_index-1]['interface']
                    return interface_to_view
                return ""

    def show(self, is_user_interactable: bool, is_for_delete: bool) -> None:
        """Used to show interface info

        Args:
            is_user_interactable (bool): used to see if user can interact with the console
            is_for_delete (bool): used to get delete command
        """

        interface_to_view = self.get_user_interface(is_user_interactable=is_user_interactable)
        if is_user_interactable:
            interface_details = self.session.send_show_command(command=f"show run interface {interface_to_view}",use_textfsm=False)
            interface_details = interface_details[interface_details.find("interface"):]

            print(f"\n{interface_details}")
            if is_for_delete:
                self.delete(interface_details=interface_details)
            print("Would you like to write the config to a file?\n")
            self.write_output(interface_details)

    def create(self) -> None:
        """Used to create basic interfaces"""
        interface_tuple = ()

        self.show(is_user_interactable=False, is_for_delete=False)
        print(f"\nCreating {self.interface_type} started...\n")
        print("Please select one of the following: ")
        print("[1]. Create using command input")
        print("[2]. Create using input file\n")
        interface_user_choice = self.user_input.validate_input_int(start=1, end=2)

        if interface_user_choice == 1:
            interface_tuple = self.create_using_console()
        elif interface_user_choice == 2:
            interface_tuple = self.yaml_creation()
        elif interface_user_choice == -1:
            return

        interface_commands  = self.generate_commands(command_data=interface_tuple[0])
        self.session.send_config_commands(commands=interface_commands)
        print("\nCommands are being executed...")
        self.ping(ip_address_to_ping=interface_tuple[0]['ip'], interface_created_name=interface_tuple[0]['name'])
        self.show(is_user_interactable=False, is_for_delete=False)
        self.edit_db(ip_address=interface_tuple[1], add_to_db=True)           

    def create_using_console(self) -> tuple:
        """Used to created interface from user input

        Returns:
            tuple: [0]dict, [1]str
        """
        while True:
            user_ip = input("\nPlease enter in the ip address with subnet: ")
            if self.check_ip_format(ip_to_check=user_ip):
                interface_data = {
                    'name': input("Please enter in the name: "),
                    'ip': '',
                    'desc': input("Please enter in the description: "),
                    'mask': '',
                    'type': 'basic'
                }

                interface_data['ip'] = self.get_next_ip_address(network_address=user_ip)
                if interface_data['ip'] is not None:
                    interface_data['mask'] = self.calculate_subnet_mask(ip_with_subnet=user_ip)
                    if self.check_name(name_to_check=interface_data['name']):
                        break
                    print("\nError name already in use. Delete before creating!\n")
        return (interface_data, user_ip)

    def yaml_creation(self) -> tuple:
        """Uses yaml input file to create commands

        Returns:
            tuple: [0]dict, [1]str
        """
        interface_data = self.yaml_file[self.interface_type]
        interface_data['type'] = "basic"
        self.check_ip_format(interface_data['ip'])
        user_interface_ip = interface_data['ip']
        interface_data['ip']= self.get_next_ip_address(network_address=user_interface_ip)
        if interface_data['ip'] is not None:
            interface_data['mask'] = self.calculate_subnet_mask(ip_with_subnet=user_interface_ip)
            if self.check_name(name_to_check=interface_data['name']):
                pass
            else:
                print("\nError name already in use. Delete before creating!\n")
        else:
            print("Please adjust input file!")
            return None
        return (interface_data, user_interface_ip)

    def delete(self, interface_details: str) -> None:
        """Used to delete interface

        Args:
            interface_details (str): full config to remove
        """
        list_of_ip_addresses = self.get_all_ip_addresses(string_of_ip_addresses=interface_details)
        ip_address_to_remove = list_of_ip_addresses[0]

        interface_to_delete = interface_details[:interface_details.find("\n")]
        self.session.send_config_commands(commands=f"no {interface_to_delete}")
        self.edit_db(ip_address=ip_address_to_remove, add_to_db=False)
        print(f"The {self.interface_type} has been deleted!")

class FullConfig(Interface):
    """Used to handle everything full config"""
    def show_running_config(self) -> None:
        """Deals with running config aspect"""
        full_config = self.session.get_full_config(use_textfsm=False)
        print(f"\n{full_config}")
        self.write_output(data_to_write=full_config)

class Physical(Interface):
    """"Used to handle physical interfaces"""
    def check_in_use(self, interface_name: str) -> bool:
        """Used to check if a physical interface is already assigned

        Returns:
            bool: True(not in use) or False(in use)
        """
        details = self.session.send_show_command(command=f"show run interface {interface_name}",use_textfsm=False)
        list_of_ip_addresses = re.findall(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", details)
        if len(list_of_ip_addresses) == 0:
            return True
        input(f"\nERROR! {interface_name} already in use please delete then reassign...")
        return False

    def assign_using_console(self, interface_name: str) -> tuple:
        """Overload of basic method used to created interface from user input

        Returns:
            tuple: [0]dict, [1]str
        """
        while True:
            user_ip = input("Please enter in the ip address with subnet: ")
            if self.check_ip_format(ip_to_check=user_ip):
                interface_data = {
                    'name': interface_name,
                    'ip': '',
                    'desc': input("Please enter in the description: "),
                    'mask': '',
                    'type': 'basic'
                }

                interface_data['ip'] = self.get_next_ip_address(network_address=user_ip)
                if interface_data['ip'] is not None:
                    interface_data['mask'] = self.calculate_subnet_mask(ip_with_subnet=user_ip)
                    break
        return (interface_data, user_ip)

    def assign(self) -> None:
        """Overload of basic function used to assign physical interfaces"""
        list_of_interfaces = self.get_all_interfaces_of_type()

        if len(list_of_interfaces) == 0:
            print("\nNo physical interfaces found!")
            input("Press enter to continue...")
        else:
            print("\nThese are the physical interfaces on the device:")
            for index, formatted_interface in enumerate(list_of_interfaces, start=1):
                print(f"[{index}]. {formatted_interface['interface']}")

            interface_index = self.user_input.validate_input_int(1, len(list_of_interfaces))
            interface_to_assign = list_of_interfaces[interface_index-1]['interface']

            if self.check_in_use(interface_name=interface_to_assign):
                interface_tuple = self.assign_using_console(interface_name=interface_to_assign)
                interface_commands  = self.generate_commands(command_data=interface_tuple[0])
                self.session.send_config_commands(commands=interface_commands)
                print("\nCommands are being executed...")
                self.ping(ip_address_to_ping=interface_tuple[0]['ip'], interface_created_name=interface_tuple[0]['name'])
                self.edit_db(ip_address=interface_tuple[1], add_to_db=True)

    def delete_physical(self) -> None:
        """Used to delet physical interface"""
        interface_to_delete = self.get_user_interface(is_user_interactable=True)
        interface_details = self.session.send_show_command(command=f"show run interface {interface_to_delete}",use_textfsm=False)
        interface_details = interface_details[interface_details.find("interface"):]
        print(f"\n{interface_details}")

        if "Serial" in interface_to_delete:
            commands = [f"interface {interface_to_delete}", "no desc", "no ip address", "shutdown"]
            old_interface_details = interface_details

            interface_details = interface_details[interface_details.find("ip address"):]
            list_of_ip_addresses = self.get_all_ip_addresses(string_of_ip_addresses=interface_details)
            ip_address_to_remove = list_of_ip_addresses[0]

            self.session.send_config_commands(commands=commands)
            self.edit_db(ip_address=ip_address_to_remove, add_to_db=False)
            print(f"The {self.interface_type} has been deleted!")
            print("\nWould you like to write the old config to a file?")
            self.write_output(old_interface_details)
        else:
            self.delete(interface_details=interface_to_delete)

class Vlan(Interface):
    """"Used to handle vlan interfaces"""
    def create_vlan(self) -> None:
        """_summary_

        Returns:
            _type_: _description_
        """
        print()
    
class Main:
    """Main program body"""
    def __init__(self) -> None:
        """Used to assign class wide attributes"""
        self.user_input = UserInput
        self.ssh_session = netmiko.BaseConnection

    @staticmethod
    def display_intro() -> None:
        """Displays intro message"""
        os.system("clear")
        print("""///////////////////////////
//                       //
//        Welcome        //
//                       //
///////////////////////////""")
        input("Please press any key to start...")

    @staticmethod
    def display_main_menu() -> None:
        """Displays main menu"""
        os.system("clear")
        print("""///////////////////////////
//                       //
//       Main Menu       //
//                       //
///////////////////////////\n""")
        print("[1]. Scan for devices")
        print("[2]. Adjust template location")
        print("***Note: Pressing 'q' at any input point will return to the main menu!***\n")

    def device_scan(self) -> dict:
        """Gets user selected device details in the network

        Returns:
            dict: Contains everything needed for ssh session
        """
        os.system("clear")
        print("""///////////////////////////
//                       //
//    Devices Scanned    //
//                       //
///////////////////////////\n""")
        list_of_connected_devices = self.user_input.get_devices_in_network()
        device_to_connect_to = self.user_input.validate_input_list(
                                                            list_to_validate=list_of_connected_devices,
                                                            message_to_be_displayed=
                                                            "Please select the device you want to conenct to: ")
        return self.user_input.get_device_details(device_to_connect_to)

    def display_device_menu(self) -> int:
        """Used to display options to user that can be done on a device

        Returns:
            int: user selection of option
        """
        name = self.ssh_session.get_hostname()
        os.system("clear")
        print("""///////////////////////////
//                       //
//         Device        //
//                       //
///////////////////////////\n""")
        print(f"Connected to: {name}\n")
        print("[1]. Show running config")
        print("[2]. View/Create/Delete loopback config")
        print("[3]. View/Create/Delete physical interface config")
        print("[4]. View/Create/Delete vlan interface config\n")
        return self.user_input.validate_input_int(start=1, end=4)

    def display_device_options(self, interface_type: str) -> None:
        """Displays options that can be slected

        Args:
            interface_type (str): physical, loopback, Vlan, port channel
        """
        if interface_type != "Full":
            print(f"What would you like to do with the {interface_type}(s)?")
            print("\n[1]. View")
            print("[2]. Create")
            print("[3]. Delete\n")
            device_option_choice = self.user_input.validate_input_int(1, 3)
            if device_option_choice == 1:
                self.ssh_session.send_show_interface_commands(interface_choice=interface_type)
            elif device_option_choice == 2:
                self.ssh_session.send_create_interface_commands(interface_to_create=interface_type)
            elif device_option_choice == 3:
                self.ssh_session.send_delete_interface_commands(interface_type_to_delete=interface_type)
        else:
            self.ssh_session.send_show_interface_commands(interface_choice=interface_type)

    def run(self) -> None:
        """Runs main body"""
        self.display_intro()

        self.display_main_menu()
        main_menu_choice = self.user_input.validate_input_int(1, 2)
        if main_menu_choice == 1:
            ssh_details = self.device_scan()
            self.ssh_session = Session(session_details=ssh_details, user_input=self.user_input)
            self.ssh_session.make_connection()
            while True:
                device_choice = self.display_device_menu()
                if device_choice == 1:
                    self.display_device_options("Full")
                elif device_choice == 2:
                    self.display_device_options("Loopback")
                elif device_choice == 3:
                    self.display_device_options("Physical")
                elif device_choice == 4:
                    self.display_device_options("Vlan")
                else:
                    break
        elif main_menu_choice == 2:
            print("Main menu choice: Template Options")


if __name__ == '__main__':
    YAML_FILE = "/home/harry/Documents/input.yaml"
    JINJA_FILE = '/home/harry/Documents/Jinja Templates'
    OUTPUT_FILE = "/home/harry/Documents/output.txt"
    DB_FILE = TinyDB('/home/harry/Documents/db.json')

    main = Main()
    main.run()
