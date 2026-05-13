import typer

from labos import __version__

app = typer.Typer(help="LabOS operator CLI")


@app.command()
def version() -> None:
    """Print the LabOS CLI version."""
    typer.echo(__version__)
