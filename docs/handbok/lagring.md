# Lagring och databaser

En översiktsplan kan lagras som en **lokal GeoPackage-fil** eller i en **PostGIS-databas**, där flera kan arbeta mot
samma planer.

## GeoPackage eller PostGIS?

| | GeoPackage | PostGIS |
|---|---|---|
| Passar för | En person, eller planer som delas som filer. | Flera som arbetar mot samma databas. |
| Kräver | Ingenting. | En PostgreSQL-databas med PostGIS och en sparad anslutning i QGIS. |
| Redigering | Direkt i filen. | Checka ut, redigera lokalt, checka in. |

> **PostGIS-stödet** är bara testat mot en låtsasdatabas. Prova först på en testplan i ett testschema.

## Skapa en plan i PostGIS

1. Lägg upp en anslutning till databasen i QGIS som vanligt (*Datakällshanteraren → PostgreSQL*). Inloggningen sköts
   av QGIS.
2. Välj **Ny översiktsplan** och **PostGIS-databas** under *Lagras i*.
3. Välj **Anslutning**, ange ett **Schema** och ett **Plan-id**.
   - Schemat delas av flera planer: finns det redan läggs planen till där, annars skapas det.
   - Plan-id:t föreslås utifrån titeln och får bara innehålla gemener a–z, siffror och understreck.

Alla planer i samma schema ligger i samma tabeller och delar koordinatsystem. En dold kolumn `plan` skiljer dem åt.
QGIS-projektet sparas i mappen du väljer.

## Öppna en plan

Klicka på **Öppna översiktsplan** (mappen). Finns det databasanslutningar visas en liten meny:

- **Lokal fil (GeoPackage)…** – peka ut filen.
- **PostGIS-databas…** – välj anslutning, schema och plan.

Sparar du QGIS-projektet följer planens lager med, och då behöver du inte öppna planen på nytt. En plan som skapats med
en äldre version av pluginet uppgraderas när den öppnas.

## Checka ut och checka in

En plan som öppnas från databasen är **skrivskyddad**. Att rita direkt mot en databas över nätet blir långsamt, och två
som ritar samtidigt skulle skriva över varandra.

<!-- FILM: checka-ut-in | Checka ut en plan från PostGIS, redigera och checka in, ca 2 min -->

### Checka ut

Klicka på **Checka ut** (databasen med grön pil nedåt). Börjar du rita, importera eller tilldela innehåll i en
skrivskyddad plan frågar pluginet om den ska checkas ut. Pluginet

1. låser planen i databasen,
2. kopierar den till en lokal GeoPackage som du redigerar i full fart.

### Checka in

Avsluta redigeringen först. Klicka sedan på **Checka in** (samma knapp, nu med orange pil uppåt). Pluginet

1. skriver tillbaka hela planen i en enda transaktion,
2. släpper låset,
3. pekar lagren mot databasen igen,
4. tar bort den lokala kopian.

Här kan du också **kasta utcheckningen**. Låset släpps då utan att något sparas.

### Om någon annan har planen utcheckad

Bara en person åt gången kan ha planen utcheckad. Försöker du checka ut en låst plan ser du vem som har den och sedan
när. Är utcheckningen övergiven kan du **bryta låset**. Den andras ändringar som inte checkats in går då inte längre
att checka in.

### Om QGIS kraschar

Den lokala kopian finns kvar i QGIS profilmapp under `rita_oversiktsplan/checkouts`. Den erbjuds nästa gång du checkar
ut planen.

> Spara gärna QGIS-projektet. Det kommer ihåg var planen ligger och om den är utcheckad.

## Mer

Hur lagringen och utcheckningen fungerar tekniskt beskrivs i [Under huven](teknik.md).
