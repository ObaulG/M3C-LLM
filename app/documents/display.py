"""
Construction de la vue d'affichage d'un document (page de description).

A partir des lignes de la table `value` d'un resource (jointes a `property`),
construit les sections affichees dans la colonne de droite de la page :

- Titre - Sous-titre
- Description
- Auteurs, sujets et disciplines
- Lieux, periodes et langues
- Ou et comment consulter ce document

Les proprietes non reconnues sont regroupees dans une section supplementaire
"Autres informations" (ajoutee seulement si elle contient des valeurs).
"""

# Ordre d'affichage des sections de la page document, avec pour chacune la liste
# ordonnee des local_name (table `property`) qu'elle contient.
SECTION_DEFINITIONS = [
    ("titre", "Titre - Sous-titre", ["title", "shortTitle", "alternative"]),
    ("description", "Description", ["abstract", "description", "tableOfContents"]),
    ("auteurs", "Auteurs, sujets et disciplines",
     ["creator", "contributor", "editor", "translator", "subject"]),
    ("lieux", "Lieux, périodes et langues",
     ["spatial", "temporal", "coverage", "date", "language"]),
    ("consultation", "Où et comment consulter ce document",
     ["publisher", "type", "format", "extent", "numPages", "identifier", "isbn", "doi",
      "source", "relation", "rights", "license", "accessRights",
      "audience", "educationLevel", "edition",
      "created", "issued", "valid", "available", "modified"]),
]

# Labels francais affiches pour chaque local_name (sinon on retombe sur le
# label de la table `property`, puis sur le local_name lui-meme).
FIELD_LABELS = {
    "title": "Titre",
    "shortTitle": "Titre court",
    "alternative": "Sous-titre",
    "abstract": "Résumé",
    "description": "Description",
    "tableOfContents": "Table des matières",
    "creator": "Auteur",
    "contributor": "Contributeur",
    "editor": "Éditeur scientifique",
    "translator": "Traducteur",
    "subject": "Sujets",
    "type": "Type",
    "spatial": "Lieux",
    "temporal": "Périodes",
    "coverage": "Couverture",
    "date": "Date",
    "language": "Langues",
    "publisher": "Éditeur",
    "format": "Format",
    "extent": "Étendue",
    "numPages": "Nombre de pages",
    "identifier": "Identifiants",
    "isbn": "ISBN",
    "doi": "DOI",
    "source": "Source",
    "relation": "Relations",
    "rights": "Droits",
    "license": "Licence",
    "accessRights": "Droits d'accès",
    "audience": "Public",
    "educationLevel": "Niveau éducatif",
    "edition": "Édition",
    "created": "Date de création",
    "issued": "Date de publication",
    "valid": "Date de validité",
    "available": "Date de disponibilité",
    "modified": "Date de modification",
}

OTHERS_SECTION_LABEL = "Autres informations"


def _has_content(row):
    return bool(row.get("value")) or bool(row.get("uri")) or bool(row.get("value_resource_id"))


def _value_dict(row):
    return {
        "type": row.get("type"),
        "text": row.get("value"),
        "uri": row.get("uri"),
        "resource_id": row.get("value_resource_id"),
        "lang": row.get("lang"),
    }


def _field_label(row):
    local_name = row.get("local_name") or ""
    return FIELD_LABELS.get(local_name) or row.get("label") or local_name


def build_resource_view(resource_id, rows, pdf_media=None):
    """
    Construit le payload d'affichage d'un document a partir de ses valeurs.

    Args:
        resource_id: id du resource (item)
        rows: lignes retournees par database.get_resource_values (dicts avec
              local_name, label, type, value, uri, lang, value_resource_id)
        pdf_media: dict {storage_id, extension} ou None (media PDF du resource)

    Returns:
        Dict avec resource_id, title, page_title, pdf et la liste ordonnee
        des sections (chacune : key, label, fields -> values).
    """
    rows = [r for r in rows if _has_content(r)]

    titles = [r["value"] for r in rows if r.get("local_name") == "title" and r.get("value")]
    alternatives = [r["value"] for r in rows if r.get("local_name") == "alternative" and r.get("value")]
    title = titles[0] if titles else None
    # Le grand titre de la page est le titre alternatif s'il existe (cf. site M3C),
    # sinon le titre ; le titre simple devient le sous-titre.
    page_title = alternatives[0] if alternatives else (title or f"Ressource {resource_id}")

    if pdf_media:
        pdf = {
            "available": True,
            "file_name": f"{pdf_media['storage_id']}.{pdf_media['extension']}",
            "url": f"/get_pdf/by_id?resource_id={resource_id}",
        }
    else:
        pdf = {"available": False, "file_name": None, "url": None}

    used_ids = set()
    sections = []
    for key, label, local_names in SECTION_DEFINITIONS:
        fields = []
        for local_name in local_names:
            values = [r for r in rows if r.get("local_name") == local_name and r["id"] not in used_ids]
            if not values:
                continue
            used_ids.update(r["id"] for r in values)
            fields.append({
                "local_name": local_name,
                "label": _field_label(values[0]),
                "values": [_value_dict(r) for r in values],
            })
        if fields:
            sections.append({"key": key, "label": label, "fields": fields})

    # Proprietes non prevues : section supplementaire en dernier.
    others = [r for r in rows if r["id"] not in used_ids]
    if others:
        by_name = {}
        order = []
        for r in others:
            ln = r.get("local_name") or str(r.get("property_id"))
            if ln not in by_name:
                by_name[ln] = []
                order.append(ln)
            by_name[ln].append(r)
        fields = [
            {
                "local_name": ln,
                "label": _field_label(by_name[ln][0]),
                "values": [_value_dict(r) for r in by_name[ln]],
            }
            for ln in order
        ]
        sections.append({"key": "autres", "label": OTHERS_SECTION_LABEL, "fields": fields})

    return {
        "resource_id": resource_id,
        "title": title,
        "page_title": page_title,
        "pdf": pdf,
        "sections": sections,
    }
