"""Python program using netmiko for the automation of cisco devices"""
import ipaddress
import yaml
from getpass import getpass
from netmiko import ConnectHandler
import jinja2

class Session:
    """Used to handle netmiko session"""
    def __init__(self, session_details: dict) -> None:
        """starts instance of netmiko session to passed device

        Args:
            session_details (dict): Contains everything needed for ssh session
        """
        self.session_details = session_details

    def make_connection(self) -> None:
        """Used to make ssh connection to cisco ios/nxos/iso telnet"""
        try:
            self.net_connect = ConnectHandler(**self.session_details)
            output = self.net_connect.send_command('show ver')
            if "Nexus" in output:
                self.net_connect.disconnect()
                self.session_details['device_type'] = 'cisco_nxos'
                self.net_connect = ConnectHandler(**self.session_details)
        except:
            try:
                self.session_details['device_type'] = 'cisco_iso_telnet'
                self.net_connect = ConnectHandler(**self.session_details)
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
        return self.net_connect.send_command(command_string=command, read_timeout=100, use_textfsm=use_textfsm)

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
        with open(yaml_file_path, "r") as stream:
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
        templateLoader = jinja2.FileSystemLoader(searchpath=jinja_file_path)
        self.templateEnv = jinja2.Environment(loader=templateLoader)
    
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
        template = self.templateEnv.get_template("loopback.j2")
        commands = template.render(config=command_data)
        list_of_commands = self.convert_to_list(commands)
        return list_of_commands
        

def get_device_details():
    """Used to get device_details

    Returns:
        dict: contains everything needed for ssh session
    """
    
    ip_address = input("Please enter in the ip address of the device: ")
    port = int(input("Please enter in the port: "))

    device = {
        'device_type': 'cisco_ios',
        'host': ip_address,
        'port': port,
        'username': input("Please enter the username: "),
        'password': getpass()
    }
    return device

if __name__ == '__main__':
    
    yaml_file = "/home/harry/Documents/input.yaml"
    yaml_reader = YamlReader(yaml_file_path=yaml_file)
    details = yaml_reader.read_loopback()

    jinja_file = '/home/harry/Documents/Jinja Templates'
    command_generator = CommandGenerator(jinja_file_path=jinja_file)
    loopback_commands = command_generator.generate_commands(details)

    ssh_details = get_device_details()
    session_one = Session(session_details=ssh_details)
    session_one.make_connection()
    print()

    output = session_one.send_show_command(command='show ip int brief', use_textfsm=False)
    print(output)
    print()

    session_one.send_config_commands(commands=loopback_commands)

    output = session_one.send_show_command(command='show ip interface brief', use_textfsm=False)
    print(output)
