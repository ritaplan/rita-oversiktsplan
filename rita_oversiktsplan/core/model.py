"""Datamodell (GeoPackage-schema) för en översiktsplan enligt Boverkets GIS-databasmodell för ÖP-modellen. Ren Python.

Tabell- och kolumnnamnen följer Boverkets GeoPackage ``databasmodell_op_0.4`` (ÖP-katalogen 2.3 och, enligt Boverket,
test 5 av Lantmäteriets nationella specifikation för översiktsplan), så att en plan som pluginet skapar har samma
struktur som Boverkets mall. Allt innehåll pekar på planen med ``oversiktsplan`` (planens objektidentitet); *berör annat
innehåll* och externa referenser till riksintressen är egna kopplingstabeller, och beslut har tre tabeller.
Varje innehållstyp är ett lager i tre varianter: ``_polygon``, ``_line`` och ``_point`` (utom Område och
Plangeometri, som bara är ytor).

Medvetna avvikelser från Boverkets mall (se ``docs/datamodell.md``):
  * alla tabeller har ``fid`` som nyckel (mallen har ``OBJECTID`` i några, och ``dokumentreferens_op`` saknar nyckel)
    och ``geom`` som geometrikolumn;
  * datum är datum, ja/nej-fält är booleska och ``digitalt_ursprung`` är ett ja/nej-fält;
  * ``beslut_op`` har även ``rubrik`` och ``arkividentitet``, som finns i specifikationens beslutOP;
  * uppslagstabellerna har samma kolumner överallt och fylls med värden ur den aktuella ÖP-katalogen.

Pluginets egna tabeller har prefixet ``rita_``: metadata och standardvärden (``rita_oversiktsplan_meta``) och
geometri som ritats men ännu inte fått något innehåll (``rita_otilldelad_yta``, ``_linje``, ``_punkt``). De följer
inte med i en leverans.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

DATABASMODELL = "0.4"  # Boverkets GIS-databasmodell som tabellerna följer
SPEC_VERSION = "test 4"  # Lantmäteriets nationella specifikation för översiktsplan som exporten följer
SCHEMA_VERSION = 5  # pluginets egen schemaversion (1: grundtabellerna; 2: + otilldelad geometri, standardvärden;
# 3: + beslut_op; 4: + precisering i plangeometrin och rita_pilar i utvecklingsinriktningens linjer;
# 5: Boverkets databasmodell 0.4, se geopackage.upgrade)
EPSG = 3006  # SWEREF 99 TM, som i Boverkets mall; standard för nya planer
# Lantmäteriets geometri 2.0.1 (koordinatsystemPlan) tillåter SWEREF 99 TM och de tolv lokala zonerna
EPSG_CODES = tuple(range(3006, 3019))
META_TABLE = "rita_oversiktsplan_meta"

# Fälttyper
TEXT, INT, REAL, DATE, DATETIME, BOOL = "text", "int", "real", "date", "datetime", "bool"

# Uttryck som QGIS använder för standardvärden.
UUID_EXPR = "lower(uuid('WithoutBraces'))"
NOW_EXPR = "now()"
TRUE_EXPR = "true"
FALSE_EXPR = "false"

AVGRANSNING = ("nedåt", "uppåt")  # vertikal avgränsning, kodlista i specifikationen


@dataclass(frozen=True)
class FieldDef:
    name: str
    type: str
    alias: str
    required: bool = False  # obligatoriskt enligt specifikationen (mjuk begränsning i QGIS)
    lookup: Optional[str] = None  # uppslagstabell med tillåtna värden
    choices: Optional[tuple[str, ...]] = None  # fast lista med tillåtna värden
    default: Optional[str] = None  # QGIS-uttryck
    length: int = 0
    multiline: bool = False
    hidden: bool = False  # sköts av pluginet, visas inte i formuläret


@dataclass(frozen=True)
class LayerDef:
    name: str  # tabellnamn i GeoPackage
    alias: str
    geometry: Optional[str]  # "MultiPolygon" | "MultiLineString" | "Point" | None (attributtabell)
    fields: tuple[FieldDef, ...]
    category: Optional["Category"] = None


@dataclass(frozen=True)
class LookupDef:
    """Uppslagstabell med värden ur ÖP-katalogen."""
    name: str
    value_column: str
    category: str  # kategori i ÖP-katalogen
    group: Optional[str] = None  # annan kategori som grupp (se opkatalog.Catalog.values)
    itself: bool = False  # kategorin själv är värdet, inte värdena under den


@dataclass(frozen=True)
class Category:
    """En innehållstyp i Boverkets modell: ett lager per geometrityp och en uppslagstabell."""
    key: str  # del av tabellnamnet: innehall_op_<key>_<geometri>
    alias: str  # namn i QGIS lagerpanel
    catalog: str  # kategori i ÖP-katalogen
    group: Optional[str] = None
    kompletterande: Optional[str] = None  # uppslagstabell för kompletterande innehållstyp
    extra: tuple[FieldDef, ...] = ()
    polygon_only: bool = False

    @property
    def lookup(self) -> str:
        return f"innehall_op_{self.key}_lookup"


GEOMETRIES = (("polygon", "MultiPolygon", "yta"), ("line", "MultiLineString", "linje"), ("point", "Point", "punkt"))

# -- uppslagstabeller ---------------------------------------------------------------------------------------------------
PLANHANDELSE_LOOKUP = LookupDef("planhandelse_lookup", "planhandelse_varde", "Planhändelse")
SAMBANDSNIVA_LOOKUP = LookupDef("sambandsniva_lookup", "sambandsniva_varde", "Sambandsnivå")
UNDERLAGSTYP_LOOKUP = LookupDef("underlagstyp_lookup", "underlagstyp_varde", "Underlag")
AVSNITTSTYP_LOOKUP = LookupDef("avsnittstyp_varde_lookup", "innehallstyp_varde", "Avsnittstyp")
KOMPLETTERANDE_MVA = LookupDef("innehall_op_kompletterandemarkochvattenanvandning_lookup", "innehallstyp_varde",
                               "Kompletterande mark- och vattenanvändning")
KOMPLETTERANDE_UI = LookupDef("innehall_op_kompletterandeutvecklingsinriktning_lookup", "innehallstyp_varde",
                              "Utvecklingsinriktning")

_UTBYGGNADSORDNING = FieldDef("utbyggnadsordning", TEXT, "Utbyggnadsordning", multiline=True)
_SAMBANDSNIVA = FieldDef("sambandsniva_varde", TEXT, "Sambandsnivå", lookup=SAMBANDSNIVA_LOOKUP.name)
_RI = FieldDef("objektidentitet_ri", TEXT, "Riksintressets objektidentitet", length=38)

PLAN_AREA_KEY = "plangeometri"
PLAN_AREA_ALIAS = "Plangeometri"  # lagrets namn i lagerpanelen

CATEGORIES: tuple[Category, ...] = (
    Category("plangeometri", "Plangeometri", "Plangeometri", polygon_only=True),
    Category("omrade", "Område", "Område", polygon_only=True),
    Category("utvecklingsinriktning", "Utvecklingsinriktning", "Utvecklingsinriktning",
             kompletterande=KOMPLETTERANDE_UI.name, extra=(_SAMBANDSNIVA, _UTBYGGNADSORDNING)),
    Category("markochvattenanvandning", "Mark- och vattenanvändning", "Mark- och vattenanvändning",
             kompletterande=KOMPLETTERANDE_MVA.name, extra=(_UTBYGGNADSORDNING,)),
    Category("riksintressenop", "Riksintresse, kommunens ställningstagande", "Riksintresse kommunens ställningstagande",
             extra=(_RI,)),
    Category("riksintressen", "Riksintressen enligt 3 och 4 kap. MB", "Riksintresse kommunens ställningstagande",
             group="Riksintressen enligt 3 och 4 kap. MB",
             extra=(FieldDef("hamtatdatum", DATE, "Hämtat datum"), _RI)),
    Category("miljokvalitetsnormer", "Miljökvalitetsnormer", "Miljökvalitetsnormer enligt 5 kap. MB"),
    Category("ovrigaforhallandeavvasentligbetydelse", "Övriga förhållanden av väsentlig betydelse",
             "Övriga förhållanden av väsentlig betydelse"),
    Category("bostadsforsorjning", "Bostadsförsörjning", "Bostadsförsörjning"),
    Category("malplanprogram", "Mål, planer och program", "Mål, planer och program"),
    Category("lis", "LIS", "Landsbygdsutveckling i strandnära läge"),
    Category("sarskiltvardefullabyggnadsverkallmannaplatserochbebyggelseomraden", "Särskilt värdefull kulturmiljö",
             "Särskilt värdefulla byggnadsverk, allmänna platser och bebyggelseområden"),
    Category("klimatrelateradrisk", "Klimatrelaterade risker", "Klimatrelaterade risker"),
    Category("avvikelsefranregionplan", "Avvikelse från regionplan", "Avvikelse från regionplan"),
    Category("mellankommunalaochregionalaintressen", "Mellankommunala och regionala intressen",
             "Mellankommunala och regionala intressen", extra=(_SAMBANDSNIVA,)),
    Category("lansstyrelsensinvandning", "Länsstyrelsens invändningar",
             "Invändningar i länsstyrelsens granskningsyttrande"),
    Category("konsekvenser", "Konsekvenser", "Konsekvenser"),
)

LOOKUPS: tuple[LookupDef, ...] = (
    *(LookupDef(c.lookup, "innehallstyp_varde", c.catalog, c.group, itself=c.key == "utvecklingsinriktning")
      for c in CATEGORIES),
    KOMPLETTERANDE_MVA, KOMPLETTERANDE_UI, PLANHANDELSE_LOOKUP, SAMBANDSNIVA_LOOKUP, UNDERLAGSTYP_LOOKUP,
    AVSNITTSTYP_LOOKUP,
)


# -- tabeller -----------------------------------------------------------------------------------------------------------
def _identitet() -> tuple[FieldDef, ...]:
    return (
        FieldDef("objektidentitet", TEXT, "Objektidentitet", required=True, default=UUID_EXPR, length=38, hidden=True),
        FieldDef("versiongiltigfran", DATETIME, "Versionen gäller från", required=True, default=NOW_EXPR, hidden=True),
    )


OVERSIKTSPLAN = LayerDef("oversiktsplan", "Översiktsplan", None, (
    *_identitet(),
    FieldDef("beslut", TEXT, "Beslut", length=38, hidden=True),
    FieldDef("kommunkod", TEXT, "Kommunkod", required=True, length=4),
    FieldDef("kommunnamn", TEXT, "Kommun", required=True),
    FieldDef("planens_titel", TEXT, "Planens titel"),
    FieldDef("planhandelse_varde", TEXT, "Planhändelse", required=True, lookup=PLANHANDELSE_LOOKUP.name),
    FieldDef("planhandelse_datum", DATE, "Datum för planhändelsen", required=True),
    FieldDef("datum_paborjat", DATE, "Datum påbörjad", required=True),
    FieldDef("digitalt_ursprung", BOOL, "Digitalt ursprung", required=True, default=TRUE_EXPR),
    FieldDef("digitaliseringsbeskrivning", TEXT, "Digitaliseringsbeskrivning", multiline=True),
))

PLAN_FIELD = "oversiktsplan"  # innehållets hänvisning till planen (planens objektidentitet)


def _innehall(category: Category) -> tuple[FieldDef, ...]:
    """Fälten i ett innehållslager (innehallOP i specifikationen), i samma ordning som i Boverkets mall."""
    fields = [
        *_identitet()[:1],
        FieldDef("vertikal_avgransning", TEXT, "Vertikal avgränsning", choices=AVGRANSNING),
        FieldDef("kompletterandeInnehallstyp", TEXT, "Kompletterande innehållstyp", lookup=category.kompletterande),
        FieldDef("namn", TEXT, "Namn"),
        FieldDef("innehallstyp_varde", TEXT, "Innehållstyp", required=True, lookup=category.lookup),
        FieldDef("precisering", TEXT, "Precisering", multiline=True),
        _identitet()[1],
        FieldDef("beslut", TEXT, "Beslut", length=38, hidden=True),
        FieldDef("planhandelse_varde", TEXT, "Planhändelse", required=True, lookup=PLANHANDELSE_LOOKUP.name),
        FieldDef("under_ersattning", BOOL, "Under ersättning", required=True, default=FALSE_EXPR),
        FieldDef("datum_paborjat", DATE, "Datum påbörjad"),
        FieldDef("illustrativa_granser", BOOL, "Illustrativa gränser", required=True, default=TRUE_EXPR,
                 hidden=True),  # alltid sant enligt specifikationen
        FieldDef("presentationsskala", INT, "Presentationsskala"),
        FieldDef("planhandelse_datum", DATE, "Datum för planhändelsen", required=True),
    ]
    # Boverkets mall har inte kompletterande innehållstyp i Plangeometri och Område, och inte precisering i Område
    if category.key == "plangeometri":
        fields = [f for f in fields if f.name != "kompletterandeInnehallstyp"]
    elif category.key == "omrade":
        fields = [f for f in fields if f.name not in ("kompletterandeInnehallstyp", "precisering")]
    plan = FieldDef(PLAN_FIELD, TEXT, "Översiktsplan", length=38, hidden=True)  # sist, som i mallen
    return (*fields, *category.extra, plan)


# Pluginets eget fält (inte i Boverkets mall, följer inte med i exporten): pilspetsarna på utvecklingsinriktningens
# linjer. Tomt = temats standard (se styles.ARROWS).
ARROW_FIELD = "rita_pilar"
ARROW_END, ARROW_START, ARROW_BOTH, ARROW_NONE = "slut", "start", "båda", "ingen"
_ARROWS = FieldDef(ARROW_FIELD, TEXT, "Pilspetsar", choices=(ARROW_END, ARROW_START, ARROW_BOTH, ARROW_NONE))


def content_layers() -> tuple[LayerDef, ...]:
    layers = []
    for category in CATEGORIES:
        for suffix, geometry, word in GEOMETRIES:
            if category.polygon_only and suffix != "polygon":
                continue
            name = f"innehall_op_{category.key}" + ("" if category.polygon_only else f"_{suffix}")
            alias = category.alias if category.polygon_only else f"{category.alias} ({word})"
            fields = _innehall(category)
            if category.key == "utvecklingsinriktning" and suffix == "line":
                fields = (*fields, _ARROWS)
            layers.append(LayerDef(name, alias, geometry, fields, category))
    return tuple(layers)


CONTENT_LAYERS = content_layers()

DOCUMENT_TABLES: tuple[LayerDef, ...] = (
    LayerDef("oversiktsplan_underlag", "Underlag", None, (
        FieldDef("underlag_id", TEXT, "Underlag", length=38),
        FieldDef("underlagstyp_varde", TEXT, "Underlagstyp", lookup=UNDERLAGSTYP_LOOKUP.name),
    )),
    LayerDef("oversiktsplan_underlag_underlag", "Underlagets dokument", None, (
        FieldDef("underlag_id", TEXT, "Underlag", length=38),
        FieldDef("dokumentreferens_id", TEXT, "Dokumentreferens", length=38),
    )),
    LayerDef("dokumentreferens_op", "Dokumentreferenser", None, (
        FieldDef("namn", TEXT, "Namn"),
        FieldDef("kortnamn", TEXT, "Kortnamn"),
        FieldDef("datumangivelse", TEXT, "Datumangivelse"),
        FieldDef("specifik_referens", TEXT, "Specifik referens"),
        FieldDef("dokumentreferens_id", TEXT, "Dokumentreferens", length=38),
        FieldDef("referens_id", TEXT, "Referens", length=38),
        FieldDef("lank", TEXT, "Länk"),
        FieldDef("identitet", TEXT, "Identitet"),
        FieldDef("namespace", TEXT, "Namnrymd"),
        FieldDef("avser", TEXT, "Avser"),
        FieldDef("producentens_identitet", TEXT, "Producentens identitet", length=38),
        FieldDef("tidsstampel", DATETIME, "Tidsstämpel"),
    )),
    LayerDef("dokumentavsnitt", "Dokumentavsnitt", None, (
        FieldDef("avsnittstyp_varde", TEXT, "Avsnittstyp", lookup=AVSNITTSTYP_LOOKUP.name),
        FieldDef("avsnittsbokmarke_id", TEXT, "Bokmärke"),
        FieldDef("dokumentreferens_id", TEXT, "Dokumentreferens", length=38),
        FieldDef("dokument_id", TEXT, "Dokument", length=38),
        FieldDef("objektidentitet", TEXT, "Objektidentitet", length=38),
    )),
    # Tabellnamnet har å i Boverkets mall; det behålls.
    LayerDef("avsnittsbokmärke", "Avsnittsbokmärken", None, (
        FieldDef("avsnittsbokmarke_id", TEXT, "Bokmärke"),
        FieldDef("avsnittsbokmarke_text", TEXT, "Bokmärkets namn"),
    )),
    # En rad per koppling: innehållet (objektidentitet) berör ett annat innehåll (beror_objektidentitet)
    LayerDef("innehall_op_beror_annat_innehall", "Berör annat innehåll", None, (
        FieldDef("objektidentitet", TEXT, "Innehållet som berör", required=True, length=38),
        FieldDef("beror_objektidentitet", TEXT, "Innehållet som berörs", required=True, length=38),
    )),
    # Ett riksintresse (objektidentitet) kopplat till en dokumentreferens
    LayerDef("innehall_op_extern_referens_ri", "Externa referenser till riksintressen", None, (
        FieldDef("extern_referens_ri_id", TEXT, "Extern referens", required=True, default=UUID_EXPR, length=38),
        FieldDef("objektidentitet", TEXT, "Riksintresset", required=True, length=38),
        FieldDef("dokumentreferens_id", TEXT, "Dokumentreferens", required=True, length=38),
    )),
)

# Geometri som ritats men ännu inte fått innehåll: man ritar först och tilldelar sedan innehållet (som i Rita
# Detaljplan). Ett objekt flyttas till rätt innehållslager när det tilldelas.
DRAFT_LAYERS: dict[str, LayerDef] = {
    suffix: LayerDef(f"rita_otilldelad_{word}", f"Otilldelad {word}", geometry, (
        FieldDef("skapad", DATETIME, "Skapad", default=NOW_EXPR, hidden=True),
    ))
    for suffix, geometry, word in GEOMETRIES
}

# Beslut om planen (beslutOP i Lantmäteriets specifikation), i Boverkets tre tabeller (databasmodell 0.4): beslutet,
# dess händelser (en rad per händelse och datum) och dess dokument. Planens och innehållets ``beslut`` pekar på
# beslutets objektidentitet. Föreskrifterna (BFS 2024:2, 2 kap. 2 §) kräver antagandebeslutets diarienummer och datum
# när det fick laga kraft. ``rubrik`` och ``arkividentitet`` finns i specifikationen men inte i Boverkets mall.
BESLUT_INSTANS = "kommunfullmäktige"  # den enda beslutande instansen i specifikationens kodlista
# händelsetyperna i specifikationens kodlista (Boverkets mall har fritext)
FATTAT, OVERKLAGAT, LAGA_KRAFT = "fattat", "överklagat", "laga kraft"
BESLUT_HANDELSER = (FATTAT, OVERKLAGAT, LAGA_KRAFT)
BESLUT = LayerDef("beslut_op", "Beslut", None, (
    *_identitet(),
    FieldDef("beslutande_organisation_namn", TEXT, "Beslutande organisation", required=True),
    FieldDef("beslutande_organisation_nummer", TEXT, "Organisationsnummer"),
    FieldDef("beslutande_instans", TEXT, "Beslutande instans", choices=(BESLUT_INSTANS,), default=f"'{BESLUT_INSTANS}'"),
    FieldDef("diarienummer", TEXT, "Diarienummer", required=True),
    FieldDef("rubrik", TEXT, "Rubrik"),
    FieldDef("arkividentitet", TEXT, "Arkividentitet"),
))
BESLUT_HANDELSE = LayerDef("beslut_op_handelse", "Beslutshändelser", None, (
    FieldDef("beslut_op_id", TEXT, "Beslut", required=True, length=38),
    FieldDef("handelsetyp", TEXT, "Händelse", required=True, choices=BESLUT_HANDELSER),
    FieldDef("datum", DATE, "Datum", required=True),
))
BESLUT_DOKUMENT = LayerDef("beslut_op_dokumentreferens", "Beslutsdokument", None, (
    FieldDef("beslut_op_id", TEXT, "Beslut", required=True, length=38),
    FieldDef("dokumentreferens_id", TEXT, "Dokumentreferens", required=True, length=38),
))
DECISION_TABLES = (BESLUT, BESLUT_HANDELSE, BESLUT_DOKUMENT)

LAYERS: tuple[LayerDef, ...] = (OVERSIKTSPLAN, *CONTENT_LAYERS, *DOCUMENT_TABLES, *DECISION_TABLES,
                                *DRAFT_LAYERS.values())
# läggs till i planer från äldre versioner
ADDED_TABLES: tuple[LayerDef, ...] = (*DRAFT_LAYERS.values(), *DECISION_TABLES)
# kolumner som lagts till i befintliga tabeller, läggs till i planer från äldre versioner: precisering och rita_pilar
# (schema 4) och Boverkets databasmodell 0.4 (schema 5)
ADDED_COLUMNS: dict[str, tuple[str, ...]] = {
    **{d.name: (PLAN_FIELD,) for d in CONTENT_LAYERS},
    "innehall_op_plangeometri": ("precisering", PLAN_FIELD),
    "innehall_op_utvecklingsinriktning_line": (PLAN_FIELD, ARROW_FIELD),
    "dokumentreferens_op": ("avser", "producentens_identitet", "tidsstampel"),
    "innehall_op_beror_annat_innehall": ("objektidentitet", "beror_objektidentitet"),
    "innehall_op_extern_referens_ri": ("objektidentitet", "dokumentreferens_id"),
    "beslut_op": ("beslutande_organisation_namn", "beslutande_organisation_nummer"),
}
# kolumner som tagits bort (schema 5, databasmodell 0.4); innehållet flyttas först, se geopackage.upgrade
REMOVED_COLUMNS: dict[str, tuple[str, ...]] = {
    "oversiktsplan": ("underlag_id", "dokument_id"),
    **{d.name: ("beror_annat_innehall_id", "dokument_id") for d in CONTENT_LAYERS},
    **{d.name: ("beror_annat_innehall_id", "dokument_id", "extern_referens_ri_id")
       for d in CONTENT_LAYERS if d.category.key == "riksintressen"},
    "innehall_op_beror_annat_innehall": ("beror_annat_innehall_id", "beror_annat_innehal_uuid"),
    "innehall_op_extern_referens_ri": ("dokumentreferns_id",),
    "beslut_op": ("beslutande_organisation", "datum_fattat", "datum_overklagat", "datum_laga_kraft"),
}
# beslutets datumkolumner i schema 3 och 4, som blir rader i beslut_op_handelse
OLD_DECISION_DATES = (("datum_fattat", FATTAT), ("datum_overklagat", OVERKLAGAT), ("datum_laga_kraft", LAGA_KRAFT))


def layer(name: str) -> LayerDef:
    return next(layer_def for layer_def in LAYERS if layer_def.name == name)


def geometry_suffix(layer_def: LayerDef) -> str:
    """``polygon``, ``line`` eller ``point`` för ett geometrilager."""
    return next(suffix for suffix, geometry, _ in GEOMETRIES if geometry == layer_def.geometry)


def content_layer(category: Category, suffix: str) -> Optional[LayerDef]:
    """Innehållslagret för en grupp och geometri, eller None om gruppen inte har den geometrin."""
    return next((d for d in CONTENT_LAYERS if d.category == category and geometry_suffix(d) == suffix), None)


NO_GEOMETRY = "none"  # innehåll utan geometri, bara kopplat till planhandlingens text


def categories_for(suffix: str) -> tuple[Category, ...]:
    """Grupperna som kan ha den här geometrin (Plangeometri och Område är bara ytor). Utan geometri: alla utom
    Plangeometri, Område och Mark- och vattenanvändning, som enligt föreskrifterna (BFS 2024:2, 3 kap. 3 §) ska vara
    lägesbestämd."""
    if suffix == NO_GEOMETRY:
        return tuple(c for c in CATEGORIES if not c.polygon_only and c.key != "markochvattenanvandning")
    return tuple(c for c in CATEGORIES if content_layer(c, suffix) is not None)


def storage_layer(category: Category, suffix: str) -> Optional[LayerDef]:
    """Lagret ett innehåll sparas i. Innehåll utan geometri sparas i gruppens ytlager med tom geometri, så att det
    ligger i samma tabell som gruppens övriga innehåll (geometrin är frivillig i specifikationen)."""
    return content_layer(category, "polygon" if suffix == NO_GEOMETRY else suffix)


# -- standardvärden för nytt innehåll --------------------------------------------------------------------------------
# Värden som gäller allt innehåll i planen ställs in under Planens uppgifter och sparas i metadatatabellen. De sätts
# på varje objekt när det tilldelas innehåll, och kan sedan ändras per objekt i attributformuläret.
DEFAULT_KEYS = {
    "vertikal_avgransning": "standard_vertikal_avgransning",  # "", "nedåt" eller "uppåt"
    "under_ersattning": "standard_under_ersattning",  # "0" eller "1"
    "datum_paborjat": "standard_datum_paborjat",  # ÅÅÅÅ-MM-DD eller ""
    "presentationsskala": "standard_presentationsskala",  # heltal eller ""
}
DEFAULT_VALUES = {"standard_vertikal_avgransning": "", "standard_under_ersattning": "0",
                  "standard_datum_paborjat": "", "standard_presentationsskala": ""}
