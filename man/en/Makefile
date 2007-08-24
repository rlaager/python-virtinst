CENTER="Virtual Machine Install Tools"


all: virt-install.1 virt-image.1 virt-clone.1 virt-image.5

clean:
	rm *.1 *.5

%.1: %.pod
	pod2man --center=$(CENTER) $< $@

virt-image.5: virt-image-xml.pod
	pod2man --center=$(CENTER) $< $@
