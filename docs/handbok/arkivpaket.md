# Arkivpaket

**Skapa arkivpaket** samlar planen och handlingarna i en mapp med bevarandemetadata enligt Boverkets specifikation
*Långtidsbevarande och arkivering av översiktsplan och detaljplan* (PREMIS 3.0), med kontrollsummor för alla filer.

<!-- FILM: arkivpaket | Skapa och kontrollera ett arkivpaket, ca 2 min -->

## Skapa ett arkivpaket

1. **Avsluta redigeringen**, så att det du ritat är sparat.
2. Välj **Insticksprogram → Rita Översiktsplan → Skapa arkivpaket…**, eller *Skapa arkivpaket* i dialogen *Leverans
   och export*.
3. Välj vad som ska med:
   - planens **GeoPackage** (bara för en plan i en fil),
   - **exportfilen** i Lantmäteriets format,
   - **planhandlingen** med bokmärken och dess webbversion,
   - **underlagens filer**, de som finns på datorn,
   - **egna dokument** som du lägger till, till exempel planhandlingen som PDF/A.
4. Skapa paketet.

<!-- BILD: arkivpaket-dialog.png | Dialogen Skapa arkivpaket med valen -->

> **Pluginet gör inga filer till PDF/A.** Spara själv plankarta och planhandling som PDF/A och kontrollera dem, till
> exempel med det kostnadsfria programmet [veraPDF](https://verapdf.org/). Pluginet påpekar bara när en PDF inte uppger
> sig vara PDF/A.

En plan i en databas har ingen GeoPackage att kopiera. Checka ut den först, eller nöj dig med exportfilen.

## Så ser paketet ut

```
<paketmapp>/
    metadata/
        PREMIS.xml      all bevarandemetadata i en fil
    schemas/            scheman för att kunna validera utan internet
    content/            filerna
```

### metadata/PREMIS.xml

En fil som är giltig mot Library of Congress schema för PREMIS 3.0. Den beskriver

- **planen** som helhet, med titel, kommun, planhändelse, diarienummer och datum,
- **varje fil**, med id, kontrollsumma (SHA-256), storlek, format och program,
- **vad som hänt**: att paketet skapades och av vem.

Alla kopplingar går åt båda hållen: planen har filerna som delar och varje fil hör till planen.

### schemas/

- PREMIS-schemat (`premis-v3-0.xsd`),
- schemat för planens uppgifter (`oversiktsplan-1.xsd`), som är pluginets eget,
- Lantmäteriets JSON-scheman för Översiktsplan 2.0, när exportfilen finns med.

> Paketet är inget E-ARK- eller FGS-paket. Har kommunen ett e-arkiv lägger du PREMIS-filen i e-arkivets eget
> paketeringsflöde. Läs mer i [Kända begränsningar](../kanda-begransningar.md).

## Kontrollera ett arkivpaket

Välj **Insticksprogram → Rita Översiktsplan → Kontrollera arkivpaket…** och peka ut paketmappen. Kontrollen räknar om
kontrollsummorna och visar om en fil har

- **ändrats**,
- **försvunnit**, eller
- **tillkommit**

sedan paketet skapades. Den kontrollerar också att metadatans kopplingar hänger ihop, och säger till om paketet är
skapat med en äldre version (0.1.1–0.1.7) vars metadata inte är giltig mot PREMIS-schemat.

Kontrollen ändrar ingenting.
