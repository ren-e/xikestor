# Name
swctl - XikeStor SKS3200-8E2X switch controller

## Requirements
  - Python3
  - requests
  - PyYAML

## Synopsis
```
swctl.py [-hdask] [-u username] [-c configfile] -p password destination 
```

## Description
`swctl` is a small command-line utility to manage VLAN configuration on the XikeStor SKS3200-8E2X series switch.
 It is intended to provide a more user-friendly method to configure VLANs on these devices, enabling scripted application of per-port VLAN assignments,
 creation of bridge entries required for ports with multiple VLANs, and saving the switch configuration to persistent memory.

`swctl` connects and logs into the specified destination, which may be specified as an IP-address or hostname.

The options are as follows:
```
	-h		Show program help
	-d		Enable debug output
	-a		Apply VLAN configuration
	-s		Save VLAN configuration
	-k		Ignore invalid certificate

	-u username
		Specifies the username to log in as on the switch.

	-p password
		Specifies the password to log in as on the switch.

	-c configfile	
		Specifies the YAML configuration file. When specified the default configuration `vlan.yaml` will be ignored.
```

## Configuration
The program will use PyYAML and safe load the configuration file. Here is a working example configuration file:

```
---

trunk: &trunk
  - 10
  - 20
  - 80

vlan:
  2:
    vlan: [10]
  3:
    vlan: [10]
  4:
    vlan: [10]
  5:
    vlan: [10]
  6:
    vlan: [10]
  7:
    vlan:
      - 10
      - 80
    native: 80
  8:
    vlan:
      - 10
      - 20
    native: 20
  9:
    vlan: *trunk
  10:
    vlan: *trunk

```
