# Kartan

Boverket styr inte hur en översiktsplan ska visas. Symbolerna i pluginet är därför **pluginets eget förslag**, gjort
för att fungera i webbkartor lika väl som i QGIS. Du kan ändra dem fritt under lagrets egenskaper.

> **Pågående arbete.** Symbologin och presentationen i kartan kommer att ändras. Synpunkter tas gärna emot under
> [Issues](https://github.com/ritaplan/rita-oversiktsplan/issues).

<!-- BILD: karta-oversikt.png | En översiktsplan i QGIS med markanvändning, utvecklingsinriktning och riksintressen -->

## Så läser du kartan

- **Mark- och vattenanvändningen** är grunden. Färgerna är lånade från detaljplanens användningsområden, till exempel
  gul för bostäder och blå för vatten, och täcker till 80 procent så att bakgrundskartan anas.
- **Utvecklingsinriktningen** är ett schema för hela kommunen:
  - färgen visar temat (bebyggelse, grön- och blåstruktur, kommunikation),
  - storleken visar **sambandsnivån**,
  - linjer har en **pilspets** där man slutade rita. Rita därför stråk och utbyggnadsriktningar från orten och utåt.
    Samband i grön- och blåstrukturen får pilar i båda ändar.
  - Inzoomat, från 1:50 000, blir schemat mindre.
- **Övrigt innehåll** ligger ovanpå som genomskinliga överlägg: gruppens kantlinje i värdets färg, en bred bård på
  insidan och namnet längs kanten.
- **Riksintressen enligt miljöbalken** ritas med tunn streckad kant och ihålig punkt, eftersom de är statens anspråk
  och inte kommunens.
- **Gruppen avgör symbolen och värdet avgör färgen.** Varje grupp har en egen kantlinje och punktform, och värdena inom
  gruppen skiljs åt med färgen.

Vill du ändra pilspetsarna på en linje kryssar du i **Pilspets där linjen slutar** och/eller **där linjen börjar** i
*Tilldela innehåll*.

## Texter i kartan

**Namnet** du ger innehållet i *Tilldela innehåll* visas i kartan. Knappen **Dölj texter** släcker namnen i alla öppna
planer så länge den är intryckt.

Punkter och linjer syns i alla skalor och blir mindre i steg när du zoomar ut.

## Planens lager

I gruppen **Översiktsplan – *titeln*** finns:

- **Översiktsplan** – tabellen med planens uppgifter (en rad).
- **Att tilldela** – det du ritat men ännu inte gett innehåll: en yta, en linje och en punkt.
- **Plangeometri** och **Område** – ytor.
- **En undergrupp per innehållstyp** med lagren *punkt*, *linje* och *yta*, i den ordningen, så att ytor inte täcker
  linjer och punkter. Mark- och vattenanvändning ligger sist, under de genomskinliga överläggen.
- **Beslut, dokument och underlag** – beslut och tabeller för planhandlingen och underlagen.

Teckenförklaringen syns i lagerpanelen.

> Ett projekt som sparats med en äldre version av pluginet behåller sina gamla symboler och sin lagerordning. Ta bort
> planen ur projektet och öppna den igen för att få de nya.

## Stilar för webbkartor (GeoServer)

En digital översiktsplan ska kunna visas på webben. Symbolerna byggs därför bara av enkla symboler som finns i SLD,
det stilformat GeoServer läser: enfärgade ytor, genomskinlighet, streckade linjer och enkla punktformer. Det finns inga
mönsterfyllningar eller bilder.

1. Välj **Insticksprogram → Rita Översiktsplan → Spara stilar för GeoServer (SLD)…**.
2. Välj en mapp. En stilfil sparas per innehållslager.
3. Lägg upp lagren i GeoServer med samma namn som tabellerna. Geometrikolumnen heter `geom`.

Pluginet gör om pilspetsarna till GeoServers sätt att rita dem. Stilfilerna är **inte provade i en riktig GeoServer**.

Läs mer om färger, symboler och avvägningar i [Symbologi](../symbologi.md).

## Nästa steg

Fortsätt med [Planhandlingen](planhandlingen.md).
