from html import escape
from pathlib import Path
from django.conf import settings
from django.http import HttpResponse


def pdf_response(title, content, filename="report.pdf"):
    from weasyprint import HTML

    font = Path(settings.BASE_DIR) / "assets/fonts/NotoSansMalayalam.ttf"
    style = f"""@font-face{{font-family:Malayalam;src:url('{font.as_uri()}')}}
    @page{{size:A4;margin:18mm}}body{{font-family:Malayalam,sans-serif;font-size:11px;color:#172b3c}}
    h1{{font-size:20px}}table{{width:100%;border-collapse:collapse;margin:16px 0}}
    th,td{{border:1px solid #cdd3da;padding:7px;text-align:left}}th{{background:#f1f4f6}}
    .muted{{color:#526273}}tr{{break-inside:avoid}}.page{{break-after:page}}"""
    html = f'<!doctype html><html lang="en"><meta charset="utf-8"><style>{style}</style><title>{escape(title)}</title><h1>{escape(title)}</h1>{content}</html>'
    document = HTML(
        string=html, base_url=str(settings.BASE_DIR), url_fetcher=local_asset
    ).write_pdf()
    response = HttpResponse(document, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response


def local_asset(url, *args, **kwargs):
    # PDFs may load the bundled font only; never fetch remote user-controlled assets.
    from weasyprint import default_url_fetcher

    font_dir = (Path(settings.BASE_DIR) / "assets/fonts").resolve()
    from urllib.parse import urlparse, unquote

    parsed = urlparse(url)
    target = Path(unquote(parsed.path)).resolve()
    if parsed.scheme != "file" or not target.is_relative_to(font_dir):
        raise ValueError("Remote PDF resources are prohibited.")
    return default_url_fetcher(url)
