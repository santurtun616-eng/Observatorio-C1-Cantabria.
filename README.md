# Observatorio C1 Cantabria

Panel de seguimiento de la C1 Santander–Reinosa con datos GTFS-RT de Renfe.

## Qué registra
- Capturas periódicas de demoras previstas por circulación (JSONL diario).
- Ranking diario de los trenes con mayores demoras previstas observadas.
- Evolución y clasificación mensual, con días observados y demoras máximas.
- Estado y cobertura del calendario GTFS; identificación de cada circulación por las paradas del recorrido.

## Limitaciones
**Una previsión GTFS-RT no equivale a una llegada real certificada.** Las métricas son estimaciones capturadas a intervalos; el mayor valor observado no implica demora final. Si falta una circulación, NO se infiere su supresión o puntualidad. Si el calendario no incluye servicios activos, se puede reconstruir un **grupo candidato** a partir de servicios que aparecen realmente en GTFS-RT, pero **no** equivale a un calendario acreditado. La cobertura oficial se deja sin dato y la proporción sobre el grupo candidato se identifica separadamente.

## Funcionamiento
GitHub Actions ejecuta `collector.py` cada cinco minutos (la programación de GitHub Actions puede sufrir retrasos) y `report.py` genera `data/dashboard.json`. El panel `index.html` consume este JSON en un sitio web estático.

Para publicar el panel: Settings → Pages → Build and deployment → Deploy from a branch → main / (root). Después podrá consultarse la dirección indicada en Pages.

## Archivos
- `collector.py`: descargas de la fuente oficial, selección por recorrido e histórico.
- `report.py`: agregación diaria y mensual.
- `data/status.json`: estado de la última captura.
- `data/observations/YYYYMMDD.jsonl`: observaciones históricas.
- `data/dashboard.json`: datos del panel.

Para calcular puntualidad y supresiones verificadas será necesario integrar horarios reales acreditables (Adif/Renfe) y reconstruir el calendario vigente. No se presentan porcentajes de puntualidad como si ya estuvieran verificados.

## Referencia de horarios contrastada (18/10/2026)

El usuario ha facilitado los dos cuadros de horarios oficiales de Renfe Cercanías Cantabria, válidos desde el **30/08/2026**. Se han contrastado estos ejemplos con `data/schedule.json` recuperado de GTFS:

| Circulación | Origen | Salida programada | Destino | Llegada programada |
| --- | --- | --- | --- | --- |
| 26908 | Santander | 08:14 | Reinosa | 09:45 |
| 26957 | Reinosa | 14:41 | Santander | 16:27 |

La equivalencia de número de tren procede del identificador GTFS, no de suponer que las filas del cartel llevan una numeración concreta. Las capturas suministradas permiten cotejar ambos sentidos, pero no permiten por sí solas deducir llegadas reales ni supresiones. No sustituir una captura de GTFS-RT por una hora certificada.

## Pruebas automáticas

Antes de cada captura se ejecuta `python -m unittest discover -s tests -v`. La batería comprueba sintaxis, generación de informe sin inventar cobertura y correspondencia con los horarios de referencia cuando existen datos locales. Un estado `error: null` en `data/status.json` confirma que la captura terminó, pero no que todas las circulaciones del día estén registradas.
