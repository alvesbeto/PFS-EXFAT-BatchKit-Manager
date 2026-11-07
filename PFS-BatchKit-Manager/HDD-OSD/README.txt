HDD-OSD (Browser 2.0) is NOT included in this repository (copyright).
You must obtain the official HDD-OSD package yourself.

Reference archive (verify MD5 after download):
  HDDOSD-1.10U.7z  MD5: 403202A03B910FB6FBD522D6AB5007E7

After extracting the archive, merge/copy into this folder so the layout matches:
  HDD-OSD\__system\osd100\hosdsys.elf
  HDD-OSD\__sysconf\   (browser / XMB assets)
  HDD-OSD\__system\    (osd100, etc.)

Install check in BatchKit:
  OSD/XMB Management > Install HDD-OSD
  Looks for: __system\osd100\hosdsys.elf
  Version 1.10U ELF MD5: ca9ab553e8b51259ccf1ca4ea2d1bc00

This repo already ships APA-Jail helpers (OSDMENU.CNF templates, conf_hdd_apajail_exfat.cfg).
They do NOT replace hosdsys.elf and the full __sysconf / __system tree.

For APA-Jail + exFAT: after HDD-OSD 1.10U install, use menu [6] HOSDMenu (hosdmenu.elf: BAT\OSDMenu\ or __Fetch_HOSDMenu_Elf.ps1).

--- PT-BR (resumo) ---
1) Baixe/obtenha HDDOSD-1.10U.7z (MD5 do 7z acima). O GitHub do BatchKit NAO traz esse arquivo.
2) Extraia TODO o conteudo DENTRO da pasta HDD-OSD deste projeto (nao so os CNF que ja vem no repo).
3) Confirme: HDD-OSD\__system\osd100\hosdsys.elf
4) No BatchKit: OSD/XMB > Install HDD-OSD — deve aparecer "HDD-OSD 1.10U - Detected".
5) Verificacao: powershell -File BAT\__Verify_HDD-OSD_Files.ps1 -RootPath .
