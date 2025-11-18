import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import textwrap

# PDF rendering
from weasyprint import HTML, CSS
from fastapi.responses import StreamingResponse
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    book_title: str
    subtitle: str
    author_name: str
    theme_color: str
    page_background_color: str
    writing_style: str
    image_style: str
    length: str
    topic_description: str


class GenerateResponse(BaseModel):
    cover_html: str
    content_html: str
    full_html: str


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        from database import db
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


# ---------- Utility functions ----------

def _make_base64_svg(width: int, height: int, bg_color: str, title: str, subtitle: str, footer: str) -> str:
    """Create a simple SVG illustration and return it as a base64 data URI."""
    def esc(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="{bg_color}" stop-opacity="0.95" />
          <stop offset="100%" stop-color="{bg_color}" stop-opacity="0.7" />
        </linearGradient>
      </defs>
      <rect width="100%" height="100%" fill="url(#g)"/>
      <g fill="#ffffff" opacity="0.15">
        <circle cx="{width*0.2}" cy="{height*0.3}" r="60"/>
        <circle cx="{width*0.8}" cy="{height*0.2}" r="40"/>
        <circle cx="{width*0.6}" cy="{height*0.75}" r="70"/>
      </g>
      <text x="50%" y="45%" dominant-baseline="middle" text-anchor="middle" font-family="Inter, Arial" font-size="28" font-weight="700" fill="#ffffff">{esc(title)}</text>
      <text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" font-family="Inter, Arial" font-size="18" font-weight="500" fill="#f0f0f0">{esc(subtitle)}</text>
      <text x="50%" y="90%" dominant-baseline="middle" text-anchor="middle" font-family="Inter, Arial" font-size="14" fill="#f9f9f9">{esc(footer)}</text>
    </svg>'''
    data = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{data}"


def _ai_image(prompt: str, style: str, theme_color: str, width: int = 1200, height: int = 800, retries: int = 2) -> str:
    """Pseudo AI image generation using SVG with retries. Returns data URI."""
    last_error: Optional[str] = None
    for _ in range(retries + 1):
        try:
            subtitle = f"{style} • {prompt[:60]}".strip()
            return _make_base64_svg(width, height, theme_color, "AI Illustration", subtitle, "Generated Inline")
        except Exception as e:
            last_error = str(e)
            continue
    return _make_base64_svg(width, height, theme_color, "Image Unavailable", last_error or "", "Retry later")


def _split_into_paragraphs(text: str, max_chars: int = 700) -> List[str]:
    text = text.strip().replace("\r\n", "\n")
    if not text:
        return []
    paragraphs = []
    for line in textwrap.wrap(text, width=max_chars):
        paragraphs.append(line)
    return paragraphs


def _generate_lorem(topic: str, style: str, words: int = 250) -> str:
    base = (
        f"{topic} — An exploration in {style.lower()} tone. "
        "This section delves into the core ideas, practical implications, and examples to make the material engaging and accessible. "
        "We balance clarity with depth, ensuring each concept builds on the previous one while maintaining a compelling narrative arc. "
        "Key takeaways are highlighted with actionable insights and meaningful context. "
    )
    return (base * max(1, words // 40))[: words * 5]


def _length_to_pages(length: str) -> int:
    if "Short" in length:
        return 5
    if "Medium" in length:
        return 10
    if "Long" in length:
        return 20
    return 5


def _common_css() -> str:
    return (
        "<style>"
        "@page { size: A4; margin: 20mm; }"
        "body { font-family: Inter, Arial, sans-serif; color: #0f172a; }"
        ".page { width: 210mm; height: 297mm; box-sizing: border-box; padding: 20mm; display: flex; flex-direction: column; justify-content: flex-start; }"
        "h1 { font-size: 32px; font-weight: 700; margin: 0 0 12px; }"
        "h2 { font-size: 26px; font-weight: 600; margin: 0 0 10px; }"
        "p { font-size: 18px; line-height: 1.6; margin: 10px 0; }"
        ".center { display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; height:100%; }"
        ".cover-title { font-size: 42px; font-weight: 800; margin-bottom: 8px; }"
        ".cover-subtitle { font-size: 22px; font-weight: 600; opacity: 0.95; }"
        ".author { margin-top: 24px; font-size: 18px; opacity: 0.9; }"
        "img { max-width: 100%; height: auto; border-radius: 8px; }"
        ".page-img { margin: 12px 0 6px; }"
        ".break { page-break-after: always; }"
        "</style>"
    )


def _cover_html(req: GenerateRequest) -> str:
    cover_img = _ai_image(
        prompt=f"Book cover about {req.topic_description}",
        style=req.image_style,
        theme_color=req.theme_color,
        width=2480,
        height=1748,
    )
    html = (
        "<!DOCTYPE html><html><head>" + _common_css() + "</head><body>"
        f"<div class=\"page\" style=\"background-color:{req.theme_color}; color:white;\">"
        f"  <div class=\"center\">"
        f"    <img alt=\"Cover\" class=\"page-img\" src=\"{cover_img}\" />"
        f"    <div class=\"cover-title\">{req.book_title}</div>"
        f"    <div class=\"cover-subtitle\">{req.subtitle}</div>"
        f"    <div class=\"author\">By {req.author_name}</div>"
        f"  </div>"
        f"</div>"
        "</body></html>"
    )
    return html


def _content_pages_html(req: GenerateRequest) -> str:
    pages = _length_to_pages(req.length)
    sections = [
        "Introduction",
        "Foundations",
        "Key Concepts",
        "Applications",
        "Case Study",
        "Techniques",
        "Best Practices",
        "Challenges",
        "Future Outlook",
        "Conclusion",
    ]
    html_parts: List[str] = ["<!DOCTYPE html><html><head>" + _common_css() + "</head><body>"]

    for i in range(pages):
        heading = sections[i % len(sections)]
        text = _generate_lorem(req.topic_description, req.writing_style, 250)
        paragraphs = _split_into_paragraphs(text, max_chars=600)
        img_data = _ai_image(
            prompt=f"{heading} — {req.topic_description}",
            style=req.image_style,
            theme_color=req.theme_color,
            width=1200,
            height=720,
        )
        html_parts.append(
            f"<div class=\"page\" style=\"background-color:{req.page_background_color};\">"
            f"  <h2>{i+1}. {heading}</h2>"
            f"  <img class=\"page-img\" alt=\"Illustration\" src=\"{img_data}\" />"
            + "".join(f"<p>{p}</p>" for p in paragraphs[:5]) +
            f"</div>"
        )
        if i < pages - 1:
            html_parts.append('<div class="break"></div>')

    html_parts.append("</body></html>")
    return "".join(html_parts)


def _assemble_full_html(cover_html: str, content_html: str) -> str:
    css = _common_css()
    cover_body = cover_html.split("<body>", 1)[-1].rsplit("</body>", 1)[0]
    content_body = content_html.split("<body>", 1)[-1].rsplit("</body>", 1)[0]
    final = (
        "<!DOCTYPE html><html><head>" + css + "</head><body>" +
        cover_body +
        '<div class="break"></div>' +
        content_body +
        "</body></html>"
    )
    return final


@app.post("/generate", response_model=GenerateResponse)
def generate_book(req: GenerateRequest):
    try:
        cover_html = _cover_html(req)
        content_html = _content_pages_html(req)
        full_html = _assemble_full_html(cover_html, content_html)
        if "class=\"page\"" not in full_html:
            raise ValueError("No pages generated")
        return GenerateResponse(cover_html=cover_html, content_html=content_html, full_html=full_html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RenderRequest(BaseModel):
    html: str


@app.post("/render-pdf")
def render_pdf(req: RenderRequest):
    try:
        html = HTML(string=req.html, base_url=".")
        css = CSS(string="@page { size: A4; margin: 20mm } body { -weasy-print-color-adjust: exact; }")
        pdf_bytes = html.write_pdf(stylesheets=[css])
        stream = BytesIO(pdf_bytes)
        return StreamingResponse(stream, media_type="application/pdf", headers={
            "Content-Disposition": "attachment; filename=ebook.pdf"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF rendering failed: {e}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
