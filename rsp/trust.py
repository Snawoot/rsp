#!/usr/bin/env python3

import sys
import argparse
import asyncio
import os
import os.path

import asyncssh

from . import utils


def parse_args():
    parser = argparse.ArgumentParser(
        description="Rapid SSH Proxy: TOFU key trust utility",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("dst_address",
                        help="target hostname")
    parser.add_argument("dst_port",
                        nargs="?",
                        default=22,
                        type=utils.check_port,
                        help="target port")

    ssh_group = parser.add_argument_group('SSH options')
    ssh_group.add_argument("-H", "--hosts-file",
                           default=os.path.join(os.path.expanduser("~"),
                                                '.rsp',
                                                'known_hosts'),
                           help="overrides known_hosts file location",
                           metavar="FILE")

    return parser.parse_args()


def main():  # pragma: no cover
    args = parse_args()
    loop = asyncio.get_event_loop()
    hostkey = loop.run_until_complete(
        asyncssh.get_server_host_key(args.dst_address, args.dst_port))
    loop.close()
    if hostkey is None:
        print("Unable to retrieve hostkey", file=sys.stderr)
        exit(3)
    print("%s key fingerprint is %s." % (hostkey.get_algorithm(),
                                         hostkey.get_fingerprint()))
    inp = input("Do you want to trust this key (yes/no)? ").lower()
    while True:
        if inp == 'yes':
            os.makedirs(os.path.dirname(args.hosts_file), mode=0o700, exist_ok=True)
            with open(args.hosts_file, 'a') as f:
                print("%s %s" % (args.dst_address,
                                 hostkey.export_public_key('openssh').decode('ascii')),
                      file=f)
                exit(0)
        elif inp == 'no':
            exit(0)
        else:
            inp = input("Please type 'yes' or 'no': ").lower()
        

if __name__ == '__main__':
    main()
