# Användarhandbok – Rita Översiktsplan

Rita Översiktsplan är ett QGIS-plugin för att rita översiktsplaner enligt Boverkets ÖP-modell, kontrollera dem mot
Lantmäteriets specifikation, leverera dem till Nationella geodataplattformen (NGP) och förbereda dem för arkivering.

Handboken går igenom arbetet steg för steg, i den ordning du normalt gör det. Är du ny börjar du med
[Kom igång](handbok/kom-igang.md).

> **Tidig utvecklingsversion.** Läs [Kända begränsningar](kanda-begransningar.md) innan du använder pluginet i ett
> skarpt planarbete.

<!-- FILM: oversikt | Rita Översiktsplan på två minuter: en plan från början till slut -->

## Innehåll

1. [Kom igång](handbok/kom-igang.md) – installera, skapa en plan och lär känna verktygsfältet
2. [Planens uppgifter](handbok/planens-uppgifter.md) – planhändelse, beslut, underlag och utbyggnadsordning
3. [Rita och tilldela innehåll](handbok/rita-och-tilldela.md) – rita, ge innehåll ur ÖP-katalogen, importera och koppla
4. [Hämta underlag](handbok/hamta-underlag.md) – markanvändning från Topografi 10 och riksintressen
5. [Kartan](handbok/kartan.md) – symbolerna, planens lager och stilar för GeoServer
6. [Planhandlingen](handbok/planhandlingen.md) – bokmärken i Word och kopplingar till innehållet
7. [Ändring av planen](handbok/andring.md) – ett eget planärende för en del av planen
8. [Leverera planen](handbok/leverera.md) – kontrollen, JSON-filen och leveransen till NGP
9. [Arkivpaket](handbok/arkivpaket.md) – förbered planen för långtidsbevarande
10. [Lagring och databaser](handbok/lagring.md) – GeoPackage, PostGIS och utcheckning
11. [Under huven](handbok/teknik.md) – datamodellen, databasen, exporten och leveransen tekniskt

## Arbetsgången i korthet

1. **Ny översiktsplan** – välj kommun, titel och var planen ska lagras. Kommunens yta blir plangeometri.
2. **Planens uppgifter** – fyll i planhändelse, underlag och eventuella etapper.
3. **Hämta underlag** – befintlig markanvändning ur Topografi 10 och riksintressen från Boverket.
4. **Rita och tilldela** – rita ytor, linjer och punkter och ge dem innehåll ur ÖP-katalogen.
5. **Koppla** innehåll som berör annat innehåll, och ta ställning till riksintressena.
6. **Planhandlingen** – skapa bokmärken i Word och koppla avsnitten till innehållet.
7. **Kontrollera** planen och **leverera** den till NGP, eller spara den som JSON-fil.
8. **Skapa ett arkivpaket** för arkivering.

Arbetsgången är densamma som i [Rita Detaljplan](https://github.com/ritaplan/rita-detaljplan): **rita först, tilldela
sedan**.

## Mer information

- [Kända begränsningar](kanda-begransningar.md) – vad som saknas och vad som inte är provat
- [Datamodell](datamodell.md) – tabellerna och var de avviker från Boverkets mall
- [Symbologi](symbologi.md) – symbolerna per innehållstyp och varför de ser ut som de gör
- [Utveckling](utveckling.md) – köra koden och testerna
- [Ändringslogg](../CHANGELOG.md)
- [Rapportera fel eller önskemål](https://github.com/ritaplan/rita-oversiktsplan/issues)

Under **Insticksprogram → Rita Översiktsplan → Om Rita Översiktsplan…** ser du vilken version du har, och där finns
länkar hit och till [ritaplan.xyz](https://ritaplan.xyz).
