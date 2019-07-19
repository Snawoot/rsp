rsp
===

Rapid SSH Proxy

## Synopsis

### Proxy

```
$ rsp --help
usage: rsp [-h] [-v {debug,info,warn,error,fatal}] [-l FILE]
           [--disable-uvloop] [-a BIND_ADDRESS] [-p BIND_PORT] [-n POOL_SIZE]
           [-B BACKOFF] [-w TIMEOUT] [-r CONNECT_RATE] [-L LOGIN]
           [-I KEY_FILE] [-P PASSWORD] [-H FILE]
           dst_address [dst_port]

Rapid SSH Proxy

positional arguments:
  dst_address           target hostname
  dst_port              target port (default: 22)

optional arguments:
  -h, --help            show this help message and exit
  -v {debug,info,warn,error,fatal}, --verbosity {debug,info,warn,error,fatal}
                        logging verbosity (default: info)
  -l FILE, --logfile FILE
                        log file location (default: None)
  --disable-uvloop      do not use uvloop even if it is available (default:
                        False)

listen options:
  -a BIND_ADDRESS, --bind-address BIND_ADDRESS
                        bind address (default: 127.0.0.1)
  -p BIND_PORT, --bind-port BIND_PORT
                        bind port (default: 1080)

pool options:
  -n POOL_SIZE, --pool-size POOL_SIZE
                        target number of steady connections (default: 30)
  -B BACKOFF, --backoff BACKOFF
                        delay after connection attempt failure in seconds
                        (default: 5)
  -w TIMEOUT, --timeout TIMEOUT
                        server connect timeout (default: 4)
  -r CONNECT_RATE, --connect-rate CONNECT_RATE
                        limit for new pool connections per second (default:
                        0.5)

SSH options:
  -L LOGIN, --login LOGIN
                        SSH login. Default is name of current user (default:
                        None)
  -I KEY_FILE, --identity KEY_FILE
                        SSH private key file. By default program looks for SSH
                        keys in usual locations, including SSH agent socket.
                        This option may be specified multiple times (default:
                        None)
  -P PASSWORD, --password PASSWORD
                        SSH password. If not specified, password auth will be
                        disabled (default: None)
  -H FILE, --hosts-file FILE
                        overrides known_hosts file location (default:
                        /home/user/.rsp/known_hosts)
```

#### Usage examples

Note: host keys must be added to trusted before proxy operation. See also synopsis for `rsp-trust` utility.

Connect to example.com with SSH on port 22, using default pool size, and accept SOCKS5 connections on port 1080. Authentication using SSH Agent.

```
rsp example.com
```

Connect to example.net with SSH on port 2222, using private key in file `proxy_key`.

```
rsp -I proxy_key example.net 2222
```

Connect to example.com with SSH on port 22, using password:

```
rsp -P MyGoodPassword example.com
```

### Trust management utility

```
$ rsp-trust --help
usage: rsp-trust [-h] [-H FILE] dst_address [dst_port]

Rapid SSH Proxy: TOFU key trust utility

positional arguments:
  dst_address           target hostname
  dst_port              target port (default: 22)

optional arguments:
  -h, --help            show this help message and exit

SSH options:
  -H FILE, --hosts-file FILE
                        overrides known_hosts file location (default:
                        /home/user/.rsp/known_hosts)
```

#### Usage examples

Get host key from example.com, port 22

```
rsp-trust example.com
```

Get host key from example.net, port 2222 and use non-default location of trusted keys file:

```
rsp-trust -H myhostkeysfile example.net 2222
```

### Key generation utility

$ rsp-keygen --help
usage: rsp-keygen [-h] [-f FILE]
                  [-t {ssh-ed25519,ssh-rsa,ecdsa-sha2-nistp256,ecdsa-sha2-nistp384,ecdsa-sha2-nistp521,ssh-dss}]
                  [-b BITS]

Rapid SSH Proxy: key generation utility

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  output file name (default: proxy_key)
  -t {ssh-ed25519,ssh-rsa,ecdsa-sha2-nistp256,ecdsa-sha2-nistp384,ecdsa-sha2-nistp521,ssh-dss}, --type {ssh-ed25519,ssh-rsa,ecdsa-sha2-nistp256,ecdsa-sha2-nistp384,ecdsa-sha2-nistp521,ssh-dss}
                        key type (default: ssh-ed25519)
  -b BITS, --bits BITS  key type (default: 2048)
```

#### Usage examples

Generate SSH key with good default parameters:

```
rsp-keygen
```

Private and public key will be saved to `proxy_key` and `proxy_key.pub` respectively.
