#!/usr/bin/env python3

import sys
import argparse
import asyncio
import os
import os.path

import asyncssh

KEY_TYPES = [
    "ssh-ed25519",
    "ssh-rsa",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "ssh-dss",
]


def check_keysize(value):
    def fail():
        raise argparse.ArgumentTypeError(
            "%s is not a valid RSA key size" % value)
    try:
        ivalue = int(value)
    except ValueError:
        fail()
    if not (2048 <= ivalue <= 8192):
        fail()
    return ivalue


def parse_args():
    parser = argparse.ArgumentParser(
        description="Rapid SSH Proxy: key generation utility",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-f", "--file",
                        default="proxy_key",
                        help="output file name")
    parser.add_argument("-t", "--type",
                        default=KEY_TYPES[0],
                        choices=KEY_TYPES,
                        help="key type")
    parser.add_argument("-b", "--bits",
                        default=2048,
                        type=check_keysize,
                        help="key type")

    return parser.parse_args()


def main():  # pragma: no cover
    args = parse_args()
    opts = {}
    if args.type == "ssh-rsa":
        opts['key_size'] = args.bits

    privkey = asyncssh.generate_private_key(args.type, **opts)
    try:
        with open(args.file, 'xb') as sk_file:
            sk_export = privkey.export_private_key(format_name='openssh')
            sk_file.write(sk_export)
        print('Your identification has been saved in %s.' % (args.file,))
        pub_filename = args.file + '.pub'
        with open(pub_filename, 'xb') as pk_file:
            pk_export = privkey.export_public_key(format_name='openssh')
            pk_file.write(pk_export)
        print('Your public key has been saved in %s.' % (pub_filename,))
    except FileExistsError as exc:
        print("Error: file '%s' already exists." % (str(exc.filename),), file=sys.stderr)


if __name__ == '__main__':
    main()
