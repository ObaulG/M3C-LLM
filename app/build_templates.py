#!/usr/bin/env python3
"""Compile les templates Jinja2 du portail en pages HTML statiques.

Les templates sources vivent dans app/templates/pages/ et héritent de base.html
et des macros de app/templates/macros/. Le build génère les pages HTML dans
app/static/ (racine) et app/static/admin/ (pages admin), en servant les mêmes
URLs que la configuration StaticFiles existante.

Usage :
    python3 app/build_templates.py            # compile toutes les pages
    python3 app/build_templates.py index.j2    # compile une page précise

Toutes les macros sont exposées automatiquement comme variables globales
(ui, header_nav, profile, question_card), de même que `static_prefix`.
"""
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "app" / "templates"
PAGES_DIR = TEMPLATES_DIR / "pages"
STATIC_DIR = REPO_ROOT / "app" / "static"

# Pages compilées : (nom de template, sous-dossier de sortie, static_prefix)
# Le sous-dossier '' correspond à la racine static, 'admin' aux pages admin.
PAGES = [
    ("index.j2", "", ""),
    ("m3c-chatbot.j2", "", ""),
    ("question_session.j2", "", ""),
    ("questions_management.j2", "", ""),
    ("rag_visualization.j2", "", ""),
    ("solr_search.j2", "", ""),
    ("tutorials.j2", "", ""),
    ("m3c-chatbot-history.j2", "", ""),
    ("auth.j2", "", ""),
    ("admin/indexation.j2", "admin", "../"),
    ("admin/questions_generation.j2", "admin", "../"),
    ("admin/knowledge_items_generation.j2", "admin", "../"),
    ("admin/message_evaluator_admin.j2", "admin", "../"),
    ("admin/chatbot_admin.j2", "admin", "../"),
]


def build_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )

    # Import global des macros : disponibles dans toutes les pages sans `{% import %}`.
    ui = env.get_template("macros/ui.html").module
    nav = env.get_template("macros/header_nav.html").module
    prof = env.get_template("macros/profile.html").module
    qcard = env.get_template("macros/question_card.html").module

    env.globals.update(
        ui=ui,
        header_nav=nav,
        profile=prof,
        question_card_mod=qcard,
        # Alias pratiques d'accès direct aux macros les plus utilisées.
        btn=ui.btn,
        nav_link=ui.nav_link,
        nav_separator=ui.nav_separator,
        message=ui.message,
        message_input=ui.message_input,
        chat_zone=ui.chat_zone,
        loading=ui.loading,
        bot_response=ui.bot_response,
        sources_section=ui.sources_section,
        feature_card=ui.feature_card,
        section=ui.section,
        status_badge=ui.status_badge,
        back_button=ui.back_button,
        header=nav.header,
        header_centered=nav.header_centered,
        nav_bar=nav.nav_bar,
        profile_widget=prof.profile_widget,
        difficulty_stars=qcard.difficulty_stars,
        evaluation_section=qcard.evaluation_section,
        empty_state=qcard.empty_state,
        question_card=qcard.question_card,
    )
    return env


def render_page(env: Environment, template_name: str, out_subdir: str, static_prefix: str) -> Path:
    template = env.get_template(f"pages/{template_name}")
    html = template.render(
        static_prefix=static_prefix,
        include_profile_widget=True,
    )
    out_dir = STATIC_DIR / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = template_name[:-3] if template_name.endswith(".j2") else template_name
    if not out_name.endswith(".html"):
        out_name += ".html"
    out_path = out_dir / out_name
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main(argv: list[str]) -> int:
    env = build_env()
    selected = argv[1:]
    targets = PAGES
    if selected:
        targets = [t for t in PAGES if t[0] in selected]
        if not targets:
            print(f"Aucune page correspondante à : {selected}")
            print("Pages disponibles : " + ", ".join(t[0] for t in PAGES))
            return 1
    built = 0
    for template_name, out_subdir, static_prefix in targets:
        out_path = render_page(env, template_name, out_subdir, static_prefix)
        rel = out_path.relative_to(REPO_ROOT)
        print(f"  ✓ {template_name} -> {rel}")
        built += 1
    print(f"{built} page(s) compilée(s) vers {STATIC_DIR.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
