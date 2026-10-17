# Observatorio C1 Cantabria

Panel de seguimiento de la C1 Santander–Reinosa con datos GTFS-RT de Renfe.

## Qué registra
- Capturas periódicas de demoras previstas por circulación (JSONL diario).
- Ranking diario de los trenes con mayores demoras previstas observadas.
- Evolución y clasificación mensual, con días observados y demoras máximas.
- Estado y cobertura del calendario GTFS; identificación de cada circulación por las paradas del recorrido.

## Limitaciones
**Una previsión GTFS-RT no equivale a una llegada real certificada.** Las métricas son estimaciones capturadas a intervalos; el mayor valor observado no implica demora final. Si falta una circulación, NO se infiere su supresión o puntualidad. Si el calendario no incluye servicios activos, la cobertura y el total programado se dejan sin dato.

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
