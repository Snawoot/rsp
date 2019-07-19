rsp
===

Rapid SSH Proxy. Like `ssh -ND`, but much faster.

`rsp` is a SSH client which implements SOCKS5 proxy feature of SSH protocol. Key feature of this implementation is use of multiple connections to overcome downsides of multiplexing many tunneled TCP connections in single SSH session. Multiple sessions are not limited with TCP window size of single connection and packet loss does not affect all tunneled connections. In order to cut latency of connection establishment `rsp` maintains pool of steady connections, which replenished with configurable rate.

## Features

* High speed as compared to conventional OpenSSH client.
* Cross-platrorm (Windows, Linux, macOS and other Unix-like systems).
* Zero-setup required for server. `rsp` can be used right away with any SSH server.
* Self-sufficient: doesn't require OpenSSH on client side to operate.
* Connection establishment latency hidden from user with asynchronous connection pool.
* Connection establishment rate limit guards user from being threated as SSH flood.

## Performance

Tested with Debian 9 server through 100Mbps connection. Round trip time to server is 125 ms, average packet loss is about 0.5%.

Client is a Linux desktop (Fedora 30, Python 3.7.3, OpenSSH\_8.0p1).

| OpenSSH | rsp |
| ------- | --- |
| ![Speedtest - OpenSSH](https://www.speedtest.net/result/8425714040.png) | ![Speedtest - rsp](https://www.speedtest.net/result/8425718956.png) |

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

Note: host keys must be added to trusted list before proxy operation. See synopsis for `rsp-trust` utility.

Connect to example.com with SSH on port 22, using default pool size, and accept SOCKS5 connections on port 1080. Authentication is using SSH Agent and username `root`.

```
rsp -L root example.com
```

Connect to example.net with SSH on port 2222, using private key in file `proxy_key` and username `user`.

```
rsp -I proxy_key -L user example.net 2222
```

Connect to example.com with SSH on port 22, using password and username of current user:

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

```
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
