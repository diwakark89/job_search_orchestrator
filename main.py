from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))

import typer

from job_enricher.cli import app as enricher_app
from pipeline.cli import app as pipeline_app
from common.cli import app as db_app
from scraping.cli import app as scraping_app

app = typer.Typer(help="Automated Job Hunt orchestration CLI.")
app.add_typer(db_app, name="db")
app.add_typer(enricher_app, name="enricher")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(scraping_app, name="scraping")

if __name__ == "__main__":
    app()
