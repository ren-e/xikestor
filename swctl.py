#!/usr/bin/env python3
#
# Manage the VLAN configuration for XikeStor SKS3200-8E2X
# Because the web interface sucks and the VLAN settings are counterintuitive.
#

import argparse
import hashlib
import json
import requests
import yaml

def parse_args():
    parser = argparse.ArgumentParser(description="Manage the XikeStor SKS3200-8E2X switch")

    parser.add_argument("hostname", nargs="?", help="Target hostname (Required)" )
    parser.add_argument("-d", dest="debug", action="store_true", help="Enable debug output" )
    parser.add_argument("-a", dest="apply", action="store_true", help="Apply VLAN configuration" )
    parser.add_argument("-s", dest="save", action="store_true", help="Save configuration" )
    parser.add_argument("-k", dest="insecure", action="store_true", help="Ignore invalid certificate" )
    parser.add_argument("-u", dest="user", default="admin", help="Username")
    parser.add_argument("-p", dest="password", required=True, help="Username")
    parser.add_argument("-c", dest="conf", default="vlan.yml", help="The VLAN configuration file")

    a = parser.parse_args()
    if not a.hostname:
        parser.error("hostname required")

    return a


class XikeStor:
    def __init__(self, args: argparse.Namespace):

        # Initialize class variables
        self.base_url = f'https://{args.hostname}'
        self.debug    = args.debug
        self.session  = requests.Session()
        self.user     = hashlib.md5(args.user.encode()).hexdigest()
        self.bridge   = {}

        # Initialize VLAN config from yaml configuration file
        if args.apply:
            if not self.load_config(args.conf):
                raise ValueError("Failed to load config!")

        # Initialize session cookie, and then login
        __password    = hashlib.md5(args.password.encode()).hexdigest()
        __login_paths = [
            'login.html',
            f'authorize?loginusr={self.user}&loginpwd={__password}'
        ]

        if args.insecure:
            import warnings
            from urllib3.exceptions import InsecureRequestWarning
            warnings.filterwarnings("ignore", category=InsecureRequestWarning)

        for path in __login_paths:
            url = f'{self.base_url}/{path}'
            r = self.session.get(url, verify=not(args.insecure))

        if r.status_code != 200:
            raise ValueError('Invalid password!')

        return

    def __lookup_port(self, port: int) -> int:
        if port == 9:
            return 10
        if port == 10:
            return 9
        return port

    def __get_next_bridge(self) -> int:
        bridges = [
            0,
            1,
        ]
        bridges += self.bridge.values()
        return max(bridges) + 1

    def __is_native_vlan(self, vlancfg: dict, vlan: int, vlan_native: int) -> list:
        native = [ cfg.get('vlan')[0] for cfg in vlancfg.values() if len(cfg.get('vlan')) == 1 ]
        native.append(vlan_native)
        return vlan in native

    def __get_bridge_key(self, vlan: list) -> str:
        return ','.join([ str(v) for v in vlan ])

    def apply_ports(self, vlan: dict) -> bool:
        jcfg = {}
        for port, cfg in vlan.items():
            vport = self.__lookup_port(port)
            key = self.__get_bridge_key(cfg.get('vlan'))
            if cfg.get('vlan'):
                localcfg = {
                     f"checkbox_{vport}": "on",
                     f"fidName_{vport}": f"{self.bridge[key]}",
                }
                if len(cfg.get('vlan')) == 1:
                    localcfg[f"checkboxTag_{vport}"] = "on"
                jcfg |= localcfg

        url = f"{self.base_url}/port_vlan_cfg.json"
        if self.debug:
            print(json.dumps(jcfg, indent=4))
        r = self.session.post(url, json=jcfg, verify=False)
        if r.status_code != 200:
            print("WARNING: Failed to update port config!")
            return False
        print("INFO: Succesfully updated port config!")
        return True

    def apply_vlan(self, vlancfg: dict) -> bool:
        jcfg = {}
        c = 0
        for port, cfg in vlancfg.items():
            vport = self.__lookup_port(port)
            if len(cfg.get('vlan')) > 1:
                for vlan in cfg.get('vlan'):
                    for _, dcfg in vlancfg.items():
                        if cfg.get('vlan') == dcfg.get('vlan'):
                            continue
                        if self.__is_native_vlan(vlancfg, vlan, cfg.get('native')) and dcfg.get('vlan') != [vlan]:
                            continue
                        if vlan in dcfg.get('vlan'):
                            key = self.__get_bridge_key(dcfg.get('vlan'))
                            localcfg = {
                                f"bpCboxName_{c}": "on",
                                f"vtypeName_{c}": "0",
                                f"ppName_{c}": f"{vport}",
                                f"brName_{c}": f"{self.bridge[key]}",
                                f"oVidName_{c}": f"{vlan}",
                            }
                            if vlan != dcfg.get('native') and dcfg.get('vlan') != [vlan]:
                                key = f"vlan{vlan}"
                                if vlan not in self.bridge:
                                    self.bridge[vlan] = self.__get_next_bridge()
                                localcfg[f"brName_{c}"] = f"{self.bridge[vlan]}"
                            c += 1
                            jcfg |= localcfg
                            break

        url = f"{self.base_url}/tag_vlan_cfg.json"
        if self.debug:
            print(json.dumps(jcfg, indent=4))

        r = self.session.post(url, json=jcfg, verify=False)
        if r.status_code != 200:
            print("WARNING: Couldn't update VLAN configuration!")
            return False

        print("INFO: Applied VLAN configuration!")
        return True

    def status(self) -> None:
        r = self.session.get(f"{self.base_url}/status.json", verify=False)
        print(json.dumps(r.json(), indent=4))
        return

    def apply(self) -> bool:
        print("INFO: Apply VLAN configuration to switch:")
        if self.debug:
            print(json.dumps(self.vlancfg, indent=4))

        for _, cfg in self.vlancfg.items():
            vlan = cfg.get('vlan')
            if not vlan:
                continue

            key = self.__get_bridge_key(cfg.get('vlan'))
            if key not in self.bridge:
                self.bridge[key] = self.__get_next_bridge()

        if not self.apply_ports(self.vlancfg):
            return False

        if not self.apply_vlan(self.vlancfg):
            return False

        return True

    def save(self) -> bool:
        for action in [ "port", "tag" ]:
            url = f"{self.base_url}/save_{action}_vlan_map.json"
            jcfg = {}
            r = self.session.post(url, json=jcfg, verify=False)
            if r.status_code != 200:
                print(f"WARNING: Failed to save {action} cfg!")
                return False

            print(f"INFO: Saved {action} cfg")

        return True

    def load_config(self, path: str) -> bool:
        with open(path, "r", encoding='utf-8') as fp:
            ycfg = yaml.safe_load(fp)
            self.vlancfg = ycfg.get('vlan')
            for port in self.vlancfg:
                if port not in range(1, 11):
                    print(f"ERROR: Port {port} out of range!")
                    return False
        return True


if __name__ == '__main__':
    args = parse_args()
    swctl = XikeStor(args)
    swctl.status()

    if args.apply:
        if not swctl.apply():
            raise ValueError("Failed to apply configuration!")

    if args.save:
        swctl.save()
