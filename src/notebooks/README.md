# Analysis Notebooks

**Standalone analyses.** Each notebook can be run on its own: open it and run all cells. No need to run other notebooks first.

- **Data:** Sync your library first (`python -m src.scripts.automation.sync`). Parquet and export data live in `data/` (project root).
- **Where to run:** Works with kernel started from **project root** or from **src/notebooks**.

| Notebook | Description |
|----------|-------------|
| `01_library.ipynb` | Library overview, stats, top artists, popularity, release year |
| `02_playlists.ipynb` | Playlist breakdown, similarity, and structure |
| `03_listening_history.ipynb` | Listening patterns, streaming history, time-of-day |
| `04_redundant_playlists.ipynb` | Redundant playlists, overlap, consolidation suggestions |

Each notebook: path setup → load data via `notebook_helpers` → analysis and plots.
