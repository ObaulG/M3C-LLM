"""
Knowledge Element Extractor - Extrait des éléments de connaissance structurés depuis des chunks de texte

Ce module implémente l'extraction d'éléments de connaissance atomiques et vérifiables
selon le modèle décrit dans modele-utilisateur-connaissances-observations.md.

Chaque connaissance extraite contient:
- Une proposition vérifiable
- Des entités associées (personnes, lieux, œuvres, événements, pratiques)
- Des thèmes associés
- Des références précises vers la source (chunk, document, positions)

Author: Extracted from the user knowledge model requirements
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import json
import re
import hashlib
from pathlib import Path

from atomic_agents import AtomicAgent, AgentConfig, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator, ChatHistory

from .mistral_client import get_mistral_client
from .prompt_loader import get_prompt


class EntityType(str, Enum):
    """Types d'entités supportés par le modèle de connaissance"""
    PERSON = "person"
    PLACE = "place"
    WORK = "work"
    EVENT = "event"
    PRACTICE = "practice"
    OTHER = "other"


@dataclass
class EntityCandidate:
    """Candidat d'entité extrait d'un chunk de texte"""
    name: str
    type: EntityType = EntityType.OTHER
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour la sérialisation"""
        return {
            'name': self.name,
            'type': self.type.value,
            'confidence': self.confidence
        }


@dataclass  
class ThemeCandidate:
    """Candidat de thème extrait d'un chunk de texte"""
    name: str
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour la sérialisation"""
        return {
            'name': self.name,
            'confidence': self.confidence
        }


@dataclass
class SourceReference:
    """Référence vers la source d'une connaissance (chunk, document, positions)"""
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    excerpt: str = ""
    page: Optional[int] = None
    position_in_page: Optional[int] = None
    position_start: int = 0  # Position de début dans le texte source
    position_end: int = 0    # Position de fin dans le texte source
    uri: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour la sérialisation"""
        result = {
            'excerpt': self.excerpt,
            'position_start': self.position_start,
            'position_end': self.position_end
        }
        if self.document_id:
            result['document_id'] = self.document_id
        if self.chunk_id:
            result['chunk_id'] = self.chunk_id
        if self.page is not None:
            result['page'] = self.page
        if self.position_in_page is not None:
            result['position_in_page'] = self.position_in_page
        if self.uri:
            result['uri'] = self.uri
        return result


@dataclass
class KnowledgeItemCandidate:
    """Candidat d'élément de connaissance extrait d'un chunk de texte"""
    proposition: str
    entities: List[EntityCandidate] = field(default_factory=list)
    themes: List[ThemeCandidate] = field(default_factory=list)
    source_reference: SourceReference = field(default_factory=SourceReference)
    summary: Optional[str] = None
    confidence: float = 1.0
    is_verified: bool = False
    verification_notes: Optional[str] = None
    
    def __post_init__(self):
        """Assure que les listes sont initialisées"""
        if self.entities is None:
            self.entities = []
        if self.themes is None:
            self.themes = []
        if self.source_reference is None:
            self.source_reference = SourceReference()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire JSON-sérialisable"""
        return {
            'proposition': self.proposition,
            'summary': self.summary,
            'entities': [e.to_dict() for e in self.entities],
            'themes': [t.to_dict() for t in self.themes],
            'source_reference': self.source_reference.to_dict(),
            'confidence': self.confidence,
            'is_verified': self.is_verified,
            'verification_notes': self.verification_notes
        }
    
    def get_hash(self) -> str:
        """Calcule un hash unique pour cette proposition"""
        content = f"{self.proposition}|{self.summary}"
        return hashlib.md5(content.encode()).hexdigest()


class KnowledgeExtractionInput(BaseIOSchema):
    """Schema d'entrée pour l'extraction de connaissances"""
    text_chunk: str
    chunk_id: Optional[str] = None
    document_id: Optional[str] = None  
    page: Optional[int] = None
    position_in_page: Optional[int] = None
    resource_metadata: Optional[Dict[str, Any]] = None


class KnowledgeExtractionOutput(BaseIOSchema):
    """Schema de sortie pour l'extraction de connaissances"""
    knowledge_items: List[Dict[str, Any]]
    extraction_stats: Optional[Dict[str, Any]] = None
    
    def to_candidates(self) -> List[KnowledgeItemCandidate]:
        """Convertit le résultat en liste de KnowledgeItemCandidate"""
        candidates = []
        for item in self.knowledge_items or []:
            source_ref_data = item.get('source_reference', {})
            source_ref = SourceReference(
                document_id=source_ref_data.get('document_id'),
                chunk_id=source_ref_data.get('chunk_id'),
                excerpt=source_ref_data.get('excerpt', ''),
                page=source_ref_data.get('page'),
                position_in_page=source_ref_data.get('position_in_page'),
                position_start=source_ref_data.get('position_start', 0),
                position_end=source_ref_data.get('position_end', 0),
                uri=source_ref_data.get('uri')
            )
            
            candidate = KnowledgeItemCandidate(
                proposition=item.get('proposition', ''),
                summary=item.get('summary'),
                entities=[
                    EntityCandidate(
                        name=e.get('name', ''),
                        type=EntityType(e.get('type', 'other')),
                        confidence=e.get('confidence', 1.0)
                    )
                    for e in item.get('entities', []) if isinstance(e, dict)
                ],
                themes=[
                    ThemeCandidate(
                        name=t.get('name', ''),
                        confidence=t.get('confidence', 1.0)
                    )
                    for t in item.get('themes', []) if isinstance(t, dict)
                ],
                source_reference=source_ref,
                confidence=item.get('confidence', 1.0),
                is_verified=item.get('is_verified', False),
                verification_notes=item.get('verification_notes')
            )
            candidates.append(candidate)
        return candidates


def create_fallback_knowledge_prompt() -> SystemPromptGenerator:
    """Crée un prompt de fallback pour l'extraction de connaissances"""
    return SystemPromptGenerator(
        background=[
            "Tu es un expert en extraction d'éléments de connaissance depuis des textes.",
            "Ton objectif est d'identifier des propositions atomiques et vérifiables, puis de les relier à des entités, thèmes et sources.",
            "Travaille EXCLUSIVEMENT en FRANÇAIS.",
            "Sois précis, rigoureux et méthodique. Ne devine pas, extrait uniquement ce qui est présent dans le texte.",
        ],
        steps=[
            "Lis attentivement le texte fourni dans son intégralité",
            "Identifie TOUTES les PROPOSITIONS FACTUELLES VÉRIFIABLES (une affirmation précise qui peut être vraie ou fausse)",
            "Pour chaque proposition identifiée:",
            "  1. Extrait la proposition exacte dans 'proposition' (doit être une phrase complète et compréhensible)",
            "  2. Crée un résumé très court (5-15 mots) dans 'summary'",
            "  3. Identifie TOUS les entrées mentionnées avec leur type et confiance dans 'entities'",
            "  4. Identifie TOUS les thèmes principaux abordés avec confiance dans 'themes'",
            "  5. Note l'extrait EXACT du texte qui soutient cette proposition avec positions de début et fin dans 'source_reference'",
            "Élimine les propositions trop vagues, subjectives ou non vérifiables",
        ],
        output_instructions=[
            "Retourne UNIQUEMENT un objet JSON avec EXACTEMENT cette structure:",
            "{'knowledge_items': [",
            "  {'proposition': 'texte exact de la proposition (20-500 caractères)',",
            "   'summary': 'résumé très court (5-15 mots)',",
            "   'entities': [{'name': 'nom complet de l\\'entité', 'type': 'person|place|work|event|practice|other', 'confidence': 0.8}],",
            "   'themes': [{'name': 'nom du thème', 'confidence': 0.8}],",
            "   'source_reference': {'excerpt': 'extrait exact (20-200 caractères)', 'position_start': debut, 'position_end': fin}}",
            "  },",
            "]}",
            "",
            "RÈGLES STRICTES:",
            "1. Chaque 'proposition' DOIT être une affirmation factuelle vérifiable (pas de questions, pas d'opinions, pas de descriptions générales)",
            "2. Les positions (position_start, position_end) DOIVENT correspondre exactement à l'emplacement de la proposition dans le texte source (indices 0-based)",
            "3. Les entités DOIVENT être des noms propres ou concepts bien définis (ex: 'Léonard de Vinci', 'Musée du Louvre', pas 'un homme' ou 'un bâtiment')",
            "4. Les thèmes DOIVENT être des catégories générales et précises (ex: 'Histoire de France', 'Technique de peinture à l'huile')",
            "5. Le champ 'excerpt' DOIT contenir le passage exact du texte qui soutient la proposition",
            "6. Si une information n'est pas certaine dans le texte, utilise une confiance entre 0.5 et 0.7",
            "7. NE RETOURNE JAMAIS de texte en dehors du JSON, pas même des commentaires ou des explications",
            "8. Ne pas inventer d'informations non présentes dans le texte",
            "9. Pour les entités, utilise des noms COMPLETS et PRÉCIS (ex: 'Léonard de Vinci' et non 'Léonard')",
            "10. Si le texte ne contient aucune proposition factuelle vérifiable, retourne {'knowledge_items': []}"
        ]
    )


def get_knowledge_extractor_agent(model: str = "mistral-medium"):
    """
    Crée et retourne un agent d'extraction de connaissances structurées.
    
    Args:
        model: Nom du modèle LLM à utiliser (par défaut: mistral-medium)
    
    Returns:
        AtomicAgent configuré pour l'extraction de connaissances
    """
    client = get_mistral_client()
    
    # Tenta de charger le prompt depuis YAML
    system_prompt_generator = get_prompt("fact_extractor", "knowledge_extractor")
    if system_prompt_generator is None:
        system_prompt_generator = create_fallback_knowledge_prompt()
    
    agent = AtomicAgent[KnowledgeExtractionInput, KnowledgeExtractionOutput](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=system_prompt_generator,
            output_format="json_object"
        )
    )
    return agent


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def clean_entity_name(name: str) -> str:
    """
    Nettoie et normalise le nom d'une entité.
    
    Args:
        name: Nom brut de l'entité
    
    Returns:
        Nom nettoyé et normalisé
    """
    if not name:
        return ""
    
    # Supprime les articles initiaux
    name = re.sub(r'^\s*(le|la|les|un|une|des|du|de la|de l\')\s+', '', name, flags=re.IGNORECASE)
    # Supprime les articles finaux
    name = re.sub(r'\s+(le|la|les|un|une|des|du|de la|de l\')\s*$', '', name, flags=re.IGNORECASE)
    # Supprime les articles au milieu (entre virgules ou tirets)
    name = re.sub(r'[,\-]\s*(le|la|les|un|une|des|du|de la|de l\')\s+', ', ', name, flags=re.IGNORECASE)
    
    # Normalise les espaces et la casse
    name = ' '.join(name.split()).strip()
    
    # Supprime les caractères speciaux autour
    name = name.strip('"\'(),;:')
    
    return name


def extract_text_excerpt(text: str, start: int, end: int, max_length: int = 200) -> str:
    """
    Extrait un passage de texte avec un contexte raisonnable.
    
    Args:
        text: Texte source complet
        start: Position de début (0-based)
        end: Position de fin (0-based, exclusive)
        max_length: Longueur maximale de l'extrait
    
    Returns:
        Extrait de texte avec contexte
    """
    if not text or start < 0 or end > len(text) or start >= end:
        return text[start:min(end, len(text))] if text and start < len(text) else ""
    
    # Ajoute du contexte avant/après
    context_start = max(0, start - 20)
    context_end = min(len(text), end + 20)
    excerpt = text[context_start:context_end]
    
    # Limite la longueur
    if len(excerpt) > max_length:
        center = (start + end) // 2
        half_length = max_length // 2
        excerpt = text[max(0, center - half_length):min(len(text), center + half_length)]
    
    return excerpt


def validate_knowledge_item(item: KnowledgeItemCandidate, min_proposition_length: int = 20) -> bool:
    """
    Valide qu'un élément de connaissance est complet et valide.
    
    Args:
        item: KnowledgeItemCandidate à valider
        min_proposition_length: Longueur minimale d'une proposition
    
    Returns:
        True si l'élément est valide, False sinon
    """
    if not item.proposition or len(item.proposition.strip()) < min_proposition_length:
        return False
    
    if not item.source_reference or not item.source_reference.excerpt:
        return False
    
    # Vérifie que les positions sont valides
    if item.source_reference.position_start >= item.source_reference.position_end:
        return False
    
    # Au moins une entité ou un thème
    if not item.entities and not item.themes:
        return False
    
    return True


def filter_valid_candidates(candidates: List[KnowledgeItemCandidate]) -> List[KnowledgeItemCandidate]:
    """Filtre les candidats valides"""
    return [c for c in candidates if validate_knowledge_item(c)]


# ============================================================================
# FONCTION PRINCIPALE D'EXTRACTION (ASYNCHRONE)
# ============================================================================

async def extract_knowledge_elements(text: str, 
                                    chunk_id: Optional[str] = None, 
                                    document_id: Optional[str] = None,
                                    page: Optional[int] = None, 
                                    position_in_page: Optional[int] = None,
                                    model: str = "mistral-medium") -> List[KnowledgeItemCandidate]:
    """
    Extrait les éléments de connaissance depuis un chunk de texte en utilisant un LLM.
    
    Args:
        text: Texte du chunk à analyser
        chunk_id: Identifiant unique du chunk
        document_id: Identifiant du document source
        page: Numéro de page
        position_in_page: Position dans la page
        model: Modèle LLM à utiliser
    
    Returns:
        Liste de KnowledgeItemCandidate extraits
    """
    if not text or not text.strip():
        return []
    
    agent = get_knowledge_extractor_agent(model)
    
    input_data = KnowledgeExtractionInput(
        text_chunk=text,
        chunk_id=chunk_id,
        document_id=document_id,
        page=page,
        position_in_page=position_in_page
    )
    
    try:
        result = await agent.run_async(input_data)
        candidates = result.to_candidates()
        
        # Valider et nettoyer les candidats
        valid_candidates = []
        for candidate in candidates:
            # Nettoyer les noms d'entités
            for entity in candidate.entities:
                entity.name = clean_entity_name(entity.name)
            
            #Ajuster les positions si chunk_id/document_id fournis
            if chunk_id and not candidate.source_reference.chunk_id:
                candidate.source_reference.chunk_id = chunk_id
            if document_id and not candidate.source_reference.document_id:
                candidate.source_reference.document_id = document_id
            if page is not None and candidate.source_reference.page is None:
                candidate.source_reference.page = page
            if position_in_page is not None and candidate.source_reference.position_in_page is None:
                candidate.source_reference.position_in_page = position_in_page
            
            # Valider le candidat
            if validate_knowledge_item(candidate):
                valid_candidates.append(candidate)
        
        return valid_candidates
        
    except Exception as e:
        print(f"Erreur lors de l'extraction de connaissances: {e}")
        # En cas d'erreur, essayer l'extraction simple de faits
        return await extract_knowledge_fallback(text, chunk_id, document_id, page, position_in_page)


# ============================================================================
# FONCTION DE FALLBACK (SI LLM INACCESSIBLE)
# ============================================================================

async def extract_knowledge_fallback(text: str, 
                                     chunk_id: Optional[str] = None, 
                                     document_id: Optional[str] = None,
                                     page: Optional[int] = None, 
                                     position_in_page: Optional[int] = None) -> List[KnowledgeItemCandidate]:
    """
    Méthode de fallback pour extraire des connaissances sans LLM.
    Utilise l'agent de base FactExtractionAgent existant.
    """
    from .fact_extractor import get_fact_analyser_agent
    
    if not text or not text.strip():
        return []
    
    # Utiliser le fact extractor existant
    agent = get_fact_analyser_agent()
    
    from atomic_agents import BaseIOSchema
    
    class FallbackInput(BaseIOSchema):
        paragraph: str
    
    class FallbackOutput(BaseIOSchema):
        facts: List[str]
    
    try:
        result = await agent.run_async(FallbackInput(paragraph=text))
        facts = result.facts or []
    except Exception:
        # Extraction très simple basée sur des phrases
        sentences = re.split(r'(?<=[.!?])\s+', text)
        facts = [s.strip() for s in sentences if len(s.strip()) >= 20]
    
    # Convertir les faits en KnowledgeItemCandidate
    candidates = []
    for i, fact in enumerate(facts):
        start_pos = max(0, text.find(fact))
        end_pos = min(len(text), start_pos + len(fact))
        
        candidate = KnowledgeItemCandidate(
            proposition=fact,
            summary=fact[:50] + "..." if len(fact) > 50 else fact,
            entities=[],  # À enrichir par la suite
            themes=[],    # À enrichir par la suite
            source_reference=SourceReference(
                document_id=document_id,
                chunk_id=chunk_id,
                excerpt=extract_text_excerpt(text, start_pos, end_pos),
                page=page,
                position_in_page=position_in_page,
                position_start=start_pos,
                position_end=end_pos
            ),
            confidence=0.5,  # Confiance plus faible pour le fallback
            is_verified=False
        )
        candidates.append(candidate)
    
    return candidates


# ============================================================================
# EXEMPLES D'UTILISATION
# ============================================================================

async def demo_extraction():
    """Démonstration de l'extraction de connaissances"""
    
    # Texte d'exemple
    text = """
    Léonard de Vinci, né le 15 avril 1452 à Vinci en Italie, était un peintre, architecte et inventeur renommé.
    Il a peint la Joconde, actuellement exposée au Musée du Louvre à Paris.
    Cette œuvre, opus 257, a été réalisée entre 1503 et 1519 et représente Mona Lisa.
    Le tableau est célèbre pour son sourire énigmatique et son utilisation révolutionnaire de la technique du sfumato.
    """
    
    print("Extraction de connaissances en cours...")
    candidates = await extract_knowledge_elements(
        text=text,
        chunk_id="demo_chunk_1",
        document_id="demo_doc_1",
        page=1,
        position_in_page=0
    )
    
    print(f"Extraits {len(candidates)} éléments de connaissance:")
    for i, candidate in enumerate(candidates):
        print(f"\n--- Élément {i+1} ---")
        print(f"Proposition: {candidate.proposition}")
        print(f"Résumé: {candidate.summary}")
        print(f"Confiance: {candidate.confidence}")
        print(f"Entités: {[f'{e.name} ({e.type.value})' for e in candidate.entities]}")
        print(f"Thèmes: {[t.name for t in candidate.themes]}")
        print(f"Source: positions {candidate.source_reference.position_start}-{candidate.source_reference.position_end}")
        print(f"Excerpt: "{candidate.source_reference.excerpt}"...")


# ============================================================================
# PERSISTANCE EN BASE DE DONNÉES MySQL
# ============================================================================

async def save_knowledge_candidates_to_db(candidates: List[KnowledgeItemCandidate],
                                         db_connection,
                                         resource_id: Optional[int] = None,
                                         document_id: Optional[str] = None,
                                         author: Optional[str] = None) -> List[int]:
    """
    Sauvegarde les candidats de connaissance dans la base de données MySQL.
    
    Utilise le schéma défini dans user_knowledge_model.sql.
    
    Args:
        candidates: Liste de KnowledgeItemCandidate à sauvegarder
        db_connection: Connexion MySQL (aiomysql ou autre compatible async)
        resource_id: ID de la ressource dans knowledge_resources (si déjà existante)
        document_id: document_id à utiliser si resource_id n'est pas fourni
        author: Auteur par défaut pour les ressources créées
    
    Returns:
        Liste des IDs des knowledge_items créés
    """
    import time
    
    knowledge_ids = []
    start_time = time.time()
    
    async with db_connection.cursor() as cursor:
        # 1. Créer ou récupérer les entités
        entity_map = {}  # nom -> id
        theme_map = {}   # nom -> id
        resource_map = {}  # document_id -> resource_id
        
        # D'abord, collecter toutes les entités et thèmes uniques
        all_entity_names = set()
        all_theme_names = set()
        
        for candidate in candidates:
            for entity in candidate.entities:
                if entity.name:  # Ignorer les entités vides
                    all_entity_names.add(clean_entity_name(entity.name))
            for theme in candidate.themes:
                if theme.name:  # Ignorer les thèmes vides
                    all_theme_names.add(clean_entity_name(theme.name))
        
        # 1.1 Gérer les entités
        print(f"Trouvées {len(all_entity_names)} entités uniques à traiter")
        for entity_name in all_entity_names:
            # Vérifier si l'entité existe déjà
            await cursor.execute(
                "SELECT id FROM entities WHERE name = %s",
                (entity_name[:255],)  # Limiter à 255 caractères
            )
            result = await cursor.fetchone()
            if result:
                entity_map[entity_name] = result['id']
            else:
                # Créer une nouvelle entité
                entity_type = EntityType.OTHER.value
                # Déterminer le type par défaut (peut être amélioré)
                await cursor.execute(
                    "INSERT INTO entities (name, type, description, created_at) "
                    "VALUES (%s, %s, %s, NOW())",
                    (entity_name[:255], entity_type, f"Extrait depuis analyse de texte")
                )
                entity_map[entity_name] = cursor.lastrowid
        
        # 1.2 Gérer les thèmes
        print(f"Trouvées {len(all_theme_names)} thèmes uniques à traiter")
        for theme_name in all_theme_names:
            # Vérifier si le thème existe déjà
            await cursor.execute(
                "SELECT id FROM themes WHERE name = %s",
                (theme_name[:255],)
            )
            result = await cursor.fetchone()
            if result:
                theme_map[theme_name] = result['id']
            else:
                # Créer un nouveau thème
                await cursor.execute(
                    "INSERT INTO themes (name, description, created_at) "
                    "VALUES (%s, %s, NOW())",
                    (theme_name[:255], f"Thème extrait depuis analyse de texte")
                )
                theme_map[theme_name] = cursor.lastrowid
        
        print(f"Entités pris en charge: {len(entity_map)}, Thèmes pris en charge: {len(theme_map)}")
        
        # 1.3 Gérer la ressource si nécessaire
        if resource_id:
            resource_map[document_id or "default"] = resource_id
        else:
            for candidate in candidates:
                doc_id = candidate.source_reference.document_id or document_id
                if doc_id and doc_id not in resource_map:
                    # Créer une nouvelle ressource
                    title = f"Document {doc_id}" if doc_id else "Document inconnu"
                    try:
                        await cursor.execute(
                            "INSERT INTO knowledge_resources (title, uri, resource_type, author, created_at) "
                            "VALUES (%s, %s, %s, %s, NOW())",
                            (title[:500], None, "chunk", author[:255] if author else None)
                        )
                        resource_map[doc_id] = cursor.lastrowid
                    except Exception as e:
                        print(f"Erreur lors de la création de la ressource {doc_id}: {e}")
                        # Essayer de récupérer l'ID existant
                        await cursor.execute(
                            "SELECT id FROM knowledge_resources WHERE title = %s",
                            (title[:500],)
                        )
                        result = await cursor.fetchone()
                        if result:
                            resource_map[doc_id] = result['id']
        
        # 2. Créer les knowledge_items et leurs relations
        print(f"Traitement de {len(candidates)} candidats de connaissance")
        for i, candidate in enumerate(candidates):
            try:
                # Vérifier si la proposition existe déjà
                proposition_hash = candidate.get_hash()
                
                await cursor.execute(
                    "SELECT id FROM knowledge_items WHERE proposition = %s",
                    (candidate.proposition[:65535],)  # TEXT field
                )
                result = await cursor.fetchone()
                
                if result:
                    knowledge_id = result['id']
                    print(f"Connaissance existante trouvée: {knowledge_id}")
                else:
                    # Créer un nouveau knowledge_item
                    await cursor.execute(
                        "INSERT INTO knowledge_items "
                        "(proposition, summary, is_verified, verification_notes, confidence, created_at) "
                        "VALUES (%s, %s, %s, %s, %s, NOW())",
                        (
                            candidate.proposition[:65535],
                            candidate.summary[:1000] if candidate.summary else None,
                            candidate.is_verified,
                            candidate.verification_notes[:65535] if candidate.verification_notes else None,
                            candidate.confidence
                        )
                    )
                    knowledge_id = cursor.lastrowid
                    print(f"Nouvelle connaissance créée: {knowledge_id}")
                
                knowledge_ids.append(knowledge_id)
                
                # 2.1 Créer les relations entités
                for entity in candidate.entities:
                    clean_name = clean_entity_name(entity.name)
                    if clean_name and clean_name in entity_map:
                        try:
                            await cursor.execute(
                                "INSERT IGNORE INTO knowledge_item_entities "
                                "(knowledge_id, entity_id, relevance, created_at) "
                                "VALUES (%s, %s, %s, NOW())",
                                (knowledge_id, entity_map[clean_name], entity.confidence)
                            )
                        except Exception as e:
                            print(f"Erreur relation knowledge-entity: {e}")
                
                # 2.2 Créer les relations thèmes
                for theme in candidate.themes:
                    clean_name = clean_entity_name(theme.name)
                    if clean_name and clean_name in theme_map:
                        try:
                            await cursor.execute(
                                "INSERT IGNORE INTO knowledge_item_themes "
                                "(knowledge_id, theme_id, relevance, created_at) "
                                "VALUES (%s, %s, %s, NOW())",
                                (knowledge_id, theme_map[clean_name], theme.confidence)
                            )
                        except Exception as e:
                            print(f"Erreur relation knowledge-theme: {e}")
                
                # 2.3 Créer les sources
                doc_id = candidate.source_reference.document_id or document_id
                if doc_id in resource_map:
                    resource_id_for_source = resource_map[doc_id]
                    try:
                        excerpt = candidate.source_reference.excerpt[:500]  # Limiter la taille
                        await cursor.execute(
                            "INSERT IGNORE INTO knowledge_sources "
                            "(knowledge_id, resource_id, excerpt, page, uri, confidence, created_at) "
                            "VALUES (%s, %s, %s, %s, %s, %s, NOW())",
                            (
                                knowledge_id,
                                resource_id_for_source,
                                excerpt,
                                candidate.source_reference.page,
                                candidate.source_reference.uri[:1000] if candidate.source_reference.uri else None,
                                candidate.confidence
                            )
                        )
                    except Exception as e:
                        print(f"Erreur création source: {e}")
                
            except Exception as e:
                print(f"Erreur lors du traitement du candidat {i}: {e}")
                continue
        
        await db_connection.commit()
        
    end_time = time.time()
    print(f"Sauvegarde terminée en {end_time - start_time:.2f}s")
    return knowledge_ids


async def save_candidates_with_new_resource(candidates: List[KnowledgeItemCandidate],
                                           db_connection,
                                           resource_title: str,
                                           resource_uri: Optional[str] = None,
                                           resource_type: str = "chunk") -> List[int]:
    """
    Sauvegarde les candidats avec création automatique d'une nouvelle ressource.
    
    Args:
        candidates: Liste de candidats à sauvegarder
        db_connection: Connexion à la base de données
        resource_title: Titre pour la nouvelle ressource
        resource_uri: URI optionnelle pour la ressource
        resource_type: Type de ressource (par défaut: "chunk")
    
    Returns:
        Liste des IDs des knowledge_items créés
    """
    async with db_connection.cursor() as cursor:
        # Créer une nouvelle ressource
        await cursor.execute(
            "INSERT INTO knowledge_resources (title, uri, resource_type, created_at) "
            "VALUES (%s, %s, %s, NOW())",
            (resource_title[:500], resource_uri[:1000] if resource_uri else None, resource_type[:100])
        )
        resource_id = cursor.lastrowid
        await db_connection.commit()
        
        # Sauvegarder les candidats avec cette ressource
        return await save_knowledge_candidates_to_db(
            candidates, db_connection, resource_id
        )


# ============================================================================
# UTILITAIRES D'EXTRACTION EN BATCH
# ============================================================================

async def extract_and_save_from_chunks(chunks: List[Dict[str, Any]],
                                      db_connection,
                                      resource_title: str,
                                      resource_type: str = "document") -> int:
    """
    Extrait et sauvegarde les connaissances depuis une liste de chunks.
    
    Args:
        chunks: Liste de chunks avec 'content', 'chunk_id', 'page', etc.
        db_connection: Connexion à la base de données
        resource_title: Titre de la ressource
        resource_type: Type de ressource
    
    Returns:
        Nombre total de connaissances sauvegardées
    """
    all_candidates = []
    total_saved = 0
    
    for i, chunk in enumerate(chunks):
        text = chunk.get('content', '')
        chunk_id = chunk.get('chunk_id', f'chunk_{i}')
        page = chunk.get('page', None)
        position_in_page = chunk.get('position_in_page', None)
        
        if text and text.strip():
            print(f"Traitement du chunk {chunk_id} ({len(text)} caractères)...")
            candidates = await extract_knowledge_elements(
                text=text,
                chunk_id=chunk_id,
                document_id=resource_title,
                page=page,
                position_in_page=position_in_page
            )
            all_candidates.extend(candidates)
            print(f"  -> {len(candidates)} connaissances extraites")
    
    if all_candidates:
        # Sauvegarder tous les candidats avec une nouvelle ressource
        saved_ids = await save_candidates_with_new_resource(
            all_candidates, db_connection, resource_title, resource_type=resource_type
        )
        return len(saved_ids)
    
    return 0


# ============================================================================
# TESTS ET DÉMONSTRATIONS
# ============================================================================

async def demo_extraction_and_save():
    """Démonstration complète: extraction + sauvegarde en base de données"""
    from .database import get_db_connection
    
    # Texte d'exemple
    text = """
    Léonard de Vinci, né le 15 avril 1452 à Vinci en Italie, était un peintre, architecte et inventeur renommé de la période Renaissance.
    Il a peint la Joconde entre 1503 et 1519, une œuvre majeure actuellement exposée au Musée du Louvre à Paris.
    Cette peinture célèbre, connus aussi comme Mona Lisa, représente Lisa Gherardini et est célèbre pour son sourire énigmatique.
    Léonard a également travaillé sur la Cène, une autre œuvre majeure située dans le couvent Santa Maria delle Grazie à Milan.
    """
    
    print("=== DEMO: Extraction de connaissances ===")
    candidates = await extract_knowledge_elements(
        text=text,
        chunk_id="demo_chunk_1",
        document_id=" Paintres_italiens_Renaissance",
        page=1,
        position_in_page=0
    )
    
    print(f"Extraits {len(candidates)} éléments de connaissance")
    
    for i, candidate in enumerate(candidates):
        print(f"\n--- Élément {i+1} ---")
        print(f"Proposition: {candidate.proposition}")
        print(f"Résumé: {candidate.summary}")
        print(f"Confiance: {candidate.confidence}")
        print(f"Entités: {[f'{e.name} ({e.type.value})' for e in candidate.entities]}")
        print(f"Thèmes: {[t.name for t in candidate.themes]}")
    
    # Essayons de sauvegarder en base de données
    try:
        print("\n=== Tentative de sauvegarde en base de données ===")
        db = await get_db_connection()
        
        # Sauvegarder avec une nouvelle ressource
        saved_ids = await save_candidates_with_new_resource(
            candidates, db, "Démonstration Léonard de Vinci"
        )
        print(f"Enregistrements sauvegardés: {len(saved_ids)}")
        
        await db.close()
        
    except Exception as e:
        print(f"Connexion à la base de données échouée: {e}")
        print("Cela est normal si vous n'avez pas de base de données configurée.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_extraction_and_save())
