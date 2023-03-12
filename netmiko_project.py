"""Program using netmiko for the automation of cisco devices"""
import os
import re
from getpass import getpass
import ipaddress
import sys
import yaml
import netmiko
import jinja2

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
            'port': int(input("Please enter in the port: ")),
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
                if start >= user_int_input <= end:
                    break
            except ValueError:
                print("Please select one of the options using numbers\n")
        return user_int_input

    @staticmethod
    def get_devices_in_network() -> str:
        """Used to all devices connected in a network

        Returns:
            str: device ip address that will be connected to
        """
        #Used to get all connected devices ip addresses
        stream = os.popen('arp -a')
        connected_devices = stream.read()
        connected_devices = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', connected_devices)
        if len(connected_devices) == 0:
            print("ERROR no devices visable in the network!")
            sys.exit()
        return connected_devices

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
                write_file.writelines(data_to_write)
        print("\nWritten to output file!")

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

    def send_config_commands(self, commands: list) -> None:
        """Sends config commands to device

        Args:
            commands (list): list containing all commands to execute
        """
        self.net_connect.send_config_set(config_commands=commands, read_timeout=100)

    def show_running_config(self) -> None:
        """Deals with running config aspect"""
        full_config = self.send_show_command('show run', False)
        print(full_config)
        self.write_output(data_to_write=full_config)

    def send_show_interface_commands(self, interface_choice: str) -> None:
        """Used to determine what view commands to send (send)

        Args:
            interface_choice (str): physical, loopback, Vlan, port channel
        """
        if interface_choice == "loopback":
            loopback = Loopback(jinja_file_path=JINJA_FILE,
            yaml_file_path="/home/harry/Documents/input.yaml",
            loopback_session=self, loopback_user_input=self.user_input)
            loopback.show_loopbacks(user_interactable=True, is_for_delete=False)

    def send_create_interface_commands(self, interface_to_create: str) -> None:
        """Used to determine what view commands to send (create)

        Args:
            interface_to_create (str): physical, loopback, Vlan, port channel
        """
        if interface_to_create == "loopback":
            loopback = Loopback(jinja_file_path=JINJA_FILE,
            yaml_file_path="/home/harry/Documents/input.yaml",
            loopback_session=self, loopback_user_input=self.user_input)
            loopback.create_loopback()

    def send_delete_interface_commands(self, interface_type_to_delete) -> None:
        """_summary_

        Args:
            interface_type_to_delete (str): physical, loopback, Vlan, port channel_
        """
        if interface_type_to_delete == "loopback":
            loopback = Loopback(jinja_file_path=JINJA_FILE,
            yaml_file_path="/home/harry/Documents/input.yaml",
            loopback_session=self, loopback_user_input=self.user_input)
            loopback.delte_loopback()

class CommandGenerator:
    """Used to generate commands using jinja files"""
    def __init__(self, jinja_file_path: str, yaml_file_path: str) -> None:
        """Used to set jinja enviroment up

        Args:
            jinja_file_path (str): file path to jinja folder
            yaml_file_path (str): file path to yaml file
        """
        template_loader = jinja2.FileSystemLoader(searchpath=jinja_file_path)
        self.template_env = jinja2.Environment(loader=template_loader)
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

    @staticmethod
    def convert_to_list(to_convert: str) -> list:
        """convert from str to list

        Args:
            to_convert (str): str of commands including \n characters

        Returns:
            list: list of commands
        """
        return to_convert.split("\n")

    @staticmethod
    def ping_result(ip_address_to_ping: str, interface_created_name: str) -> None:
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

    def generate_commands(self, command_data: dict, template_to_use: str) -> list:
        """Uses jinja templates to generate cisco comamnds

        Args:
            command_data (dict): dict containing all data for comamnds
            template_to_use (str): what template should be used for commands

        Returns:
            list: list of commands
        """
        template = self.template_env.get_template(f"{template_to_use}.j2")
        commands = template.render(config=command_data)
        list_of_commands = self.convert_to_list(commands)
        return list_of_commands

    def read_loopback(self) -> dict:
        """Used to get loopback details from yaml file

        Returns:
            dict: dictonary of info needed to make loopbacks
        """
        return self.yaml_file['Loopback']

class Loopback(CommandGenerator):
    """Used to handle everything loopback"""
    def __init__(self, jinja_file_path: str, yaml_file_path: str, loopback_session: Session,
    loopback_user_input: UserInput) -> None:
        """Used to assign attributes to child class

        Args:
            jinja_file_path (str): file path to jinja folder
            yaml_file_path (str): pathh to yaml input file
            loopback_session (Session): ref to session class
            loopback_user_input (UserInput): ref to user input class
        """
        super().__init__(jinja_file_path, yaml_file_path)
        self.loopback_session = loopback_session
        self.loopback_user_input = loopback_user_input

    def show_loopbacks(self, user_interactable: bool, is_for_delete: bool) -> None:
        """Used to show all loopbaks on the device

        Args:
            user_interactable (bool): used to see if user can interact with the console
            is_for_delete (bool): used to get delete command
        """

        formatted_loopbacks = []
        loopbacks = self.loopback_session.send_show_command(command='show interfaces',
                                                        use_textfsm=True)
        for loopback in loopbacks:
            if "Loopback" in loopback['interface']:
                formatted_loopbacks.append(loopback)
        print("\nThese are the loopbacks on the device:")

        for index, formatted_loopback in enumerate(formatted_loopbacks, start=1):
            print(f"[{index}]. {formatted_loopback['interface']}")

        if user_interactable:
            if is_for_delete:
                print("\nPlease select one that you wold like to delete")
            else:
                print("\nPlease select one that you wold like to view indepth")
            loopback_to_view = formatted_loopbacks[self.loopback_user_input.validate_input_int(
                                                                                        1, len(formatted_loopbacks)) - 1]['interface']
            loopback_details = self.loopback_session.send_show_command(
                                                                    command=f"show run interface {loopback_to_view}",
                                                                    use_textfsm=False)
            loopback_details = loopback_details[loopback_details.find("interface"):]
            if is_for_delete:
                loopback_to_delete = loopback_details[:loopback_details.find("\n")]
                self.loopback_session.send_config_commands(commands=f"no {loopback_to_delete}")
                print("\nThe loopback has been deleted\n")
                print("Would you like to write the old config to a file?")
            else:
                print(f"\n{loopback_details}")
            print()
            self.loopback_session.write_output(loopback_details)

    def create_loopback(self) -> None:
        """Used to create loopback"""
        loopback_data = dict
        self.show_loopbacks(user_interactable=False, is_for_delete=False)
        print("\nCreating loopback started...")
        print("Please select one of the following: ")
        print("[1]. Create using command input")
        print("[2]. Create using input file\n")
        loopback_user_choice = self.loopback_user_input.validate_input_int(start=1, end=2)

        if loopback_user_choice == 1:
            user_loopback_ip = input("Please enter in the ip address with subnet: ")
            loopback_data = {
                'name': input("Please enter in the name: "),
                'ip': '',
                'desc': input("Please enter in the description: "),
                'mask': self.calculate_subnet_mask(ip_with_subnet=user_loopback_ip)
            }
            loopback_data["ip"] = self.format_ip_address(unformatted_ip=user_loopback_ip)
        else:
            loopback_data = self.use_yaml()
        loopback_commands  = self.generate_commands(command_data=loopback_data,
                                                template_to_use="loopback")
        self.loopback_session.send_config_commands(commands=loopback_commands)
        print("\nCommands are being executed...")
        self.ping_result(ip_address_to_ping=loopback_data['ip'],
                    interface_created_name=loopback_data['name'])
        self.show_loopbacks(user_interactable=False, is_for_delete=False)

    def delte_loopback(self) -> None:
        """Used to delete loopbacks"""
        self.show_loopbacks(user_interactable=True, is_for_delete=True)
        self.show_loopbacks(user_interactable=False, is_for_delete=False)

    def use_yaml(self) -> dict:
        """Uses yaml input file to create commands

        Returns:
            dict: everything needed to make a loopback
        """
        loopback_data = self.read_loopback()

        loopback_data['mask'] = self.calculate_subnet_mask(loopback_data['ip'])
        loopback_data['ip'] = self.format_ip_address(loopback_data['ip'])
        return loopback_data

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
        print("[2]. Adjust template location\n")

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
                                                            message_to_be_displayed="Please select the device you want to conenct to: ")
        return self.user_input.get_device_details(device_to_connect_to)

    def display_device_menu(self, device_connected_to_ip: str) -> int:
        """Used to display options to user that can be done on a device

        Args:
            device_connected_to_ip (str): connected device ip

        Returns:
            int: user selection of option
        """
        os.system("clear")
        print("""///////////////////////////
//                       //
//         Device        //
//                       //
///////////////////////////\n""")
        print(f"Connected to: {device_connected_to_ip}\n")
        print("[1]. Show running config")
        print("[2]. View/Create/Delete loopback config\n")
        return self.user_input.validate_input_int(start=1, end=2)

    def display_device_options(self, interface_type):
        """Displays options that can be slected

        Args:
            interface_type (str): physical, loopback, Vlan, port channel
        """
        print(f"What would you like to do with the {interface_type}(s)?")
        print("\n[1]. View")
        print("[2]. Create")
        print("[3]. Delete\n")
        device_option_choice = self.user_input.validate_input_int(1, 3)
        if device_option_choice == 1:
            self.ssh_session.send_show_interface_commands(interface_choice=interface_type)
        elif device_option_choice == 2:
            self.ssh_session.send_create_interface_commands(interface_to_create=interface_type)
        else:
            self.ssh_session.send_delete_interface_commands(interface_type_to_delete=interface_type)

    def run(self) -> None:
        """Runs main body"""
        self.display_intro()

        self.display_main_menu()
        main_menu_choice = self.user_input.validate_input_int(1, 2)
        if main_menu_choice == 1:
            ssh_details = self.device_scan()
            self.ssh_session = Session(session_details=ssh_details, user_input=self.user_input)
            self.ssh_session.make_connection()
            device_choice = self.display_device_menu(device_connected_to_ip=ssh_details['host'])
            if device_choice == 1:
                self.ssh_session.show_running_config()
            elif device_choice == 2:
                self.display_device_options("loopback")
        else:
            print("Main menu choice: Template Options")
        print()

if __name__ == '__main__':
    YAML_FILE = "/home/harry/Documents/input.yaml"
    JINJA_FILE = '/home/harry/Documents/Jinja Templates'
    command_generator = CommandGenerator(jinja_file_path=JINJA_FILE, yaml_file_path=YAML_FILE)
    #Loads output file
    OUTPUT_FILE = "/home/harry/Documents/output.txt"

    main = Main()
    main.run()
