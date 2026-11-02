# Säkerhet

Pluginet hanterar översiktsplaner som filer på din dator eller i er egen PostGIS-databas, och (vid leverans till NGP)
inloggningsuppgifter. Nyckel och hemlighet till Lantmäteriets API lagras **inte av pluginet** utan i QGIS
autentiseringsdatabas. Databaslösenord hanteras av QGIS egna anslutningar.

En genomgång av vad pluginet gör, vilka data som rör sig vart och kända fynd finns i
[docs/sakerhet.md](docs/sakerhet.md). Där finns också en kort version för IT-säkerhetsfunktionen i en organisation.

Så hanterar pluginet det som kan vara känsligt:

- **Nätverk:** pluginet kontaktar bara tjänster när du själv väljer det: Lantmäteriets API vid *Leverera till NGP*,
  Boverkets karttjänst vid *Hämta riksintressen* och SCB:s karttjänst när en ny plan skapas med kommunens yta. Adresser
  till Lantmäteriets API måste börja med `https://`. Det finns ingen telemetri.
- **Databasen:** värden i SQL skrivs med citering, och schemanamn och planers id får bara innehålla a–z, siffror och
  understreck. Pluginet tar bara bort ett schema som det själv började skapa i samma försök (om det misslyckas), och
  ett annat användares lås bryts bara efter två frågor.
- **Word-dokument:** originalet skrivs aldrig över; bokmärkena läggs i en kopia.
- **Webbversionen (HTML):** all text är kodad, och bara länkar till webbadresser, e-post och avsnitt i samma sida blir
  klickbara (inte till exempel `javascript:` eller filer på datorn).
- **Exporten:** sökvägar till filer på datorn följer inte med, bara webbadresser.

## Rapportera en säkerhetsbrist

Beskriv inte säkerhetsbrister i ett öppet ärende. Använd i stället GitHubs
[privata rapportering](https://github.com/ritaplan/rita-oversiktsplan/security/advisories/new) (fliken *Security* →
*Report a vulnerability*). Då syns rapporten bara för dig och underhållaren. Skriv gärna:

- vilken version det gäller och vad du gjorde,
- vad som hände och vad du hade väntat dig,
- om du har en fil eller ett exempel som visar felet (ta bort uppgifter du inte får dela).

**Vad du kan vänta dig:** pluginet underhålls av en enskild person på fritiden. Målet är att bekräfta rapporten inom
**14 dagar** och att ha en rättning eller en plan inom 60 dagar för det som är allvarligt. Du får veta när rättningen är
utgiven och, om du vill, nämns som den som hittade felet i [CHANGELOG](CHANGELOG.md). Rättade säkerhetsfel anges där med
rubriken *Säkerhet*.

Rapportera gärna också om du hittar något i [docs/sakerhet.md](docs/sakerhet.md) som inte stämmer.

## Vad som räknas

Som säkerhetsbrist räknas till exempel att en fil, ett svar från en server eller en plan kan få pluginet att köra kod,
läsa eller skriva filer det inte ska, skicka inloggningsuppgifter till fel mottagare, frysa QGIS eller visa vilseledande
text i en bekräftelsedialog. Att QGIS själv eller en databas har en sårbarhet räknas inte hit; rapportera det till QGIS
respektive databasens projekt.

## Stödda versioner

Bara den senaste utgivna versionen får rättningar.

## Kontrollera det du laddar ner

Varje release på GitHub har en SHA-256-kontrollsumma (`.zip.sha256`) och en materiallista (`.sbom.cdx.json`, CycloneDX).
Zip-filen byggs reproducerbart ur taggen med `python tools/build_zip.py`. Se
[Så kan du verifiera uppgifterna](docs/sakerhet.md#så-kan-du-verifiera-uppgifterna).
