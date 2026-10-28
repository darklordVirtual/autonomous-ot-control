# Pilot: styrt autonom drift av bygget ditt, 90 dager, dokumentert etter IPMVP

*Tilbudsmal for Luftfiber AS. Beløp fastsettes per avtale; alle
besparelsestall viser til evidenspakken, aldri til denne teksten alene.*

## Hva piloten leverer

En digital driftsleder (caretaker) som foreslår én avgrenset endring om
gangen i byggets ventilasjon, varme, belysning og effektuttak. Hver endring
går gjennom en uavhengig validator og en signert tillatelsesport (REMORA)
før den sendes, og en lesebegrenset observatør bekrefter virkningen. Alt
som skjer, kan ettergås av en tredjepart uten å stole på oss.

Tre ting du får som tall, ikke som løfter:

1. **Effekttopp (kW/mnd).** Nettleiens effektledd avregnes på månedens
   høyeste timesmiddel. Caretakeren holder bygget under et avtalt
   effektbudsjett og slipper budsjettet bare for komfort, frost eller
   sikkerhet. På tvillingen kalibrert mot et målt Oslo-kontor (3 562 m²)
   falt vintertoppene fra 130–166 kW til 80–91 kW uten tap av komfort
   (`docs/results/2026-10-28/pilot-site-001/pilot.html`).
2. **kWh.** Tilstedeværelsesstyrt belysning med dagslysdimming, behovsstyrt
   ventilasjon, optimal start, nattsenking, og en akkumulatortank som
   følger behovet i stedet for en fast temperatur.
3. **Dokumentasjon.** Hver måned en M&V-rapport etter IPMVP Option D
   (kalibrert simulering) og ASHRAE Guideline 14, med baseline, måleavgrensning,
   usikkerhet og digest av alle inndata. Rapporten kan deles med
   energirådgiver, revisor eller Enova.

## Slik gjennomføres piloten

| Fase | Uker | Innhold | Leveranse |
|---|---:|---|---|
| 0 Grunnlag | 1–2 | Timesverdier fra målerne (12–18 mnd), energiattest, SD-anleggets styresekvenser, nettleieavtale. Tvillingen kalibreres mot målerne med en **holdt-tilbake valideringsperiode** (ikke samme periode som tilpasningen). | Kalibreringsrapport: CV(RMSE) og NMBE måned/time, hva som er identifisert og hva som ikke er. |
| 1 Skyggedrift | 3–6 | Caretakeren kjører mot live avlesninger, men skriver ingenting. Hvert forslag logges med beslutningsgrunnlag og sammenlignes med det SD-anlegget faktisk gjorde. | Skyggerapport: hva ville blitt endret, hva validatoren og REMORA ville avvist, og hvorfor. |
| 2 Styrt drift | 7–12 | Skriving til SD-anlegget gjennom signert verktøykontrakt og signerte kumulative grenser (maks endring per kvarter, per time, per døgn), nødstopp hos driftsleder, uavhengig effektobservasjon. Ett lever om gangen, i avtalt rekkefølge. | Månedlig M&V-rapport, avviksliste, revisjonsspor. |
| 3 Oppgjør | 13 | Besparelsen beregnes mot den kalibrerte baselinen på pilotperiodens faktiske vær, priser og bruk. | Sluttrapport og anbefalt driftsavtale. |

## Hva vi trenger fra deg

- Eksport av timesverdier fra hovedmålere og eventuelle undermålere
  (anonymisert: ingen adresse, eier eller målepunkt-ID i vårt system).
- Energiattest og byggets tekniske grunnlag (ventilasjonsmengder,
  varmekilde, akkumulatorvolum, om kompressoren kan trinnes).
- Lesetilgang til SD-anlegget i fase 1; skrivetilgang til en avgrenset
  verktøyliste i fase 2, med driftsleders godkjenning av grensene.
- Nettleieavtalen, så effektleddet prises på din faktiske tariff.

## Prismodell

| Post | Prinsipp |
|---|---|
| Pilotavgift, fase 0–3 | Fast beløp som dekker kalibrering, integrasjon og rapportering; avtales per bygg |
| Suksesshonorar | En avtalt andel av besparelsen som M&V-rapporten dokumenterer i pilotperioden, mot den kalibrerte baselinen og innenfor dens usikkerhet |
| Driftsavtale etter pilot (valgfri) | Fast månedspris per bygg pluss andel av dokumentert besparelse |

Suksesshonoraret beregnes bare på besparelse som er dokumentert i
M&V-rapporten med den avtalte baselinen og usikkerheten. Ingen dokumentert
besparelse, intet honorar.

## Hva vi ikke lover

- Simuleringstall er ikke målte besparelser. Evidenspakken sier hva som er
  etablert og hva som ikke er, linje for linje (`docs/status.md`).
- Vi skriver aldri til et fysisk anlegg uten signert kontrakt, signerte
  grenser og driftsleders nødstopp. Simuleringsresultater låser aldri opp
  en live-tilkobling.
- Ingen person- eller eiendomsdata forlater din kontroll: tvillingen bygges
  på anonymiserte aggregater.

## Hvorfor nå

EUs reviderte bygningsenergidirektiv (EPBD 2024/1275, artikkel 13) krever
bygningsautomasjon med kontinuerlig overvåking, feildeteksjon og
energirapportering i næringsbygg med varme-/kjøleanlegg over 290 kW, og
over 70 kW fra 2030. Norsk gjennomføring gjennom EØS er ikke vedtatt, men
kravene er retningen, og leietakere og långivere spør allerede. Piloten
gir dokumentasjonen det kravet forutsetter.

## Kontakt

Luftfiber AS · support@luftfiber.no · github.com/darklordVirtual/autonomous-ot-control
