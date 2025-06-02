import typer
import httpx
import json
from typing import Optional

app = typer.Typer(help="Interface CLI pour l'API de recherche sémantique")

API_URL = "http://localhost:8005/search"  # À adapter si besoin

@app.command()
def search(
    query: str = typer.Argument(..., help="Terme de recherche"),
    limit: int = typer.Option(5, help="Nombre maximum de résultats"),
    threshold: float = typer.Option(0.6, help="Seuil de pertinence (0-1)"),
    format: str = typer.Option("json", help="Format de sortie (json, text)"),
    verbose: bool = typer.Option(False, help="Mode verbeux pour le débogage")
):
    """
    Effectue une recherche sémantique via l'API.
    """
    payload = {"query": query, "max_results": limit}
    try:
        if verbose:
            typer.echo(f"[DEBUG] POST {API_URL} payload={payload}")
        response = httpx.post(API_URL, json=payload)
        response.raise_for_status()
        results = response.json()
    except Exception as e:
        typer.echo(json.dumps({"error": str(e)}), err=True)
        raise typer.Exit(code=1)

    if format == "json":
        typer.echo(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for idx, result in enumerate(results, 1):
            typer.echo(f"{idx}. {result.get('metadata', {}).get('title', 'No title')} (score: {result.get('score', 0):.2f})")
            typer.echo(f"   {result.get('content', '')}\n")

@app.command()
def index(
    content: str = typer.Argument(..., help="Contenu du document"),
    title: str = typer.Option("Doc Test", help="Titre du document"),
    verbose: bool = typer.Option(False, help="Mode verbeux pour le débogage")
):
    """
    Indexe un document dans la base sémantique.
    """
    metadata = {"title": title}
    params = {"content": content, "metadata": json.dumps(metadata)}
    try:
        if verbose:
            typer.echo(f"[DEBUG] POST {API_URL.replace('/search', '/index')} params={params}")
        response = httpx.post(API_URL.replace('/search', '/index'), params=params)
        response.raise_for_status()
        typer.echo(response.text)
    except Exception as e:
        typer.echo(json.dumps({"error": str(e)}), err=True)
        raise typer.Exit(code=1)

@app.callback()
def main(
    headless: bool = typer.Option(False, "--headless", help="Mode sans tête pour l'automatisation")
):
    """
    CLI pour l'API semantic-search. Utilisez --help pour voir les commandes.
    """
    if headless:
        typer.echo("[INFO] Mode headless activé.")

if __name__ == "__main__":
    app() 