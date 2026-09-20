"""
Services pour la récupération des données du profil utilisateur.

Ce module contient toutes les fonctions pour récupérer et agréger les données
nécessaires à l'affichage de la page de profil.
"""
import json
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import aiomysql

from .models import (
    UserProfile,
    ProfileStats,
    VisitedResource,
    ThemeStats,
    KnowledgeItem,
    EntityInfo,
    SourceInfo,
    ThemeKnowledgeGroup,
    UserProfileResponse,
    KnowledgeStatus,
    ObservationRecord,
    ObservationTargetInfo,
    ObservationTypeStats,
    ObservationType,
)


# ============================================================================
# Fonctions de base pour la connexion à la base de données
# ============================================================================

async def _get_profile_db_connection():
    """Retourne une connexion à la base de données pour le module profile."""
    from database.database import get_db_connection as base_get_db_connection
    return await base_get_db_connection()


# ============================================================================
# Fonctions pour récupérer le profil utilisateur
# ============================================================================

async def get_user_profile(user_id: str, conn) -> Optional[UserProfile]:
    """
    Récupère les informations de base du profil utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        conn: Connexion à la base de données
        
    Returns:
        UserProfile ou None si l'utilisateur n'existe pas
    """
    query = """
        SELECT 
            user_id,
            languages,
            visit_goal,
            detail_level,
            accessibility_needs,
            is_active,
            last_activity_at,
            created_at
        FROM user_profiles 
        WHERE user_id = %s
    """
    
    async with conn.cursor(aiomysql.DictCursor) as cursor:
        await cursor.execute(query, (user_id,))
        result = await cursor.fetchone()
        
    if not result:
        return None
    
    return UserProfile(
        user_id=result["user_id"],
        languages=json.loads(result["languages"]) if result["languages"] else [],
        visit_goal=result["visit_goal"],
        detail_level=result["detail_level"],
        accessibility_needs=json.loads(result["accessibility_needs"]) if result["accessibility_needs"] else [],
        is_active=bool(result["is_active"]),
        last_activity_at=result["last_activity_at"],
        created_at=result["created_at"],
    )


# ============================================================================
# Fonctions pour récupérer les statistiques
# ============================================================================

async def get_profile_stats(user_id: str, conn) -> ProfileStats:
    """
    Récupère les statistiques globales pour un utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        conn: Connexion à la base de données
        
    Returns:
        ProfileStats avec toutes les statistiques
    """
    # Utilisation de la vue user_profile_stats si elle existe
    # Sinon, calcul direct
    query = """
        SELECT 
            user_id,
            COUNT(DISTINCT o.id) AS total_observations,
            COUNT(DISTINCT CASE WHEN o.observation_type = 'behavioral' AND o.specific_type = 'resource_view' THEN o.id END) AS total_resource_views,
            COUNT(DISTINCT CASE WHEN o.observation_type = 'behavioral' AND o.specific_type = 'theme_view' THEN o.id END) AS total_theme_views,
            COUNT(DISTINCT CASE WHEN o.observation_type = 'evaluative' THEN o.id END) AS total_evaluations,
            COUNT(DISTINCT CASE WHEN o.observation_type = 'behavioral' AND o.specific_type = 'resource_view' THEN ot_resource.target_id END) AS total_resources_visited,
            COUNT(DISTINCT ot_theme.target_id) AS total_themes_explored,
            COUNT(DISTINCT ot_knowledge.target_id) AS total_knowledge_items_encountered,
            COUNT(DISTINCT CASE WHEN uks.status = 'demonstrated' THEN uks.knowledge_id END) AS total_knowledge_demonstrated,
            COUNT(DISTINCT CASE WHEN uks.status = 'developing' THEN uks.knowledge_id END) AS total_knowledge_developing,
            COUNT(DISTINCT CASE WHEN uks.status = 'encountered' THEN uks.knowledge_id END) AS total_knowledge_encountered,
            COUNT(DISTINCT CASE WHEN uks.status = 'unknown' THEN uks.knowledge_id END) AS total_knowledge_unknown,
            MIN(o.timestamp) AS first_visit,
            MAX(o.timestamp) AS last_visit,
            up.created_at AS profile_created_at,
            up.last_activity_at AS profile_last_activity
        FROM user_profiles up
        LEFT JOIN observations o ON up.user_id = o.user_id
        LEFT JOIN observation_targets ot_knowledge ON o.id = ot_knowledge.observation_id AND ot_knowledge.target_type = 'knowledge'
        LEFT JOIN observation_targets ot_resource ON o.id = ot_resource.observation_id AND ot_resource.target_type = 'entity'
        LEFT JOIN observation_targets ot_theme ON o.id = ot_theme.observation_id AND ot_theme.target_type = 'theme'
        LEFT JOIN user_knowledge_states uks ON up.user_id = uks.user_id AND uks.knowledge_id = ot_knowledge.target_id
        WHERE up.user_id = %s
        GROUP BY up.user_id, up.created_at, up.last_activity_at
    """
    
    async with conn.cursor(aiomysql.DictCursor) as cursor:
        await cursor.execute(query, (user_id,))
        result = await cursor.fetchone()
    
    if not result:
        # Retourner des statistiques vides
        return ProfileStats(user_id=user_id)
    
    return ProfileStats(
        user_id=user_id,
        total_observations=result["total_observations"] or 0,
        total_resource_views=result["total_resource_views"] or 0,
        total_theme_views=result["total_theme_views"] or 0,
        total_evaluations=result["total_evaluations"] or 0,
        total_resources_visited=result["total_resources_visited"] or 0,
        total_themes_explored=result["total_themes_explored"] or 0,
        total_knowledge_items_encountered=result["total_knowledge_items_encountered"] or 0,
        total_knowledge_demonstrated=result["total_knowledge_demonstrated"] or 0,
        total_knowledge_developing=result["total_knowledge_developing"] or 0,
        total_knowledge_encountered=result["total_knowledge_encountered"] or 0,
        total_knowledge_unknown=result["total_knowledge_unknown"] or 0,
        first_visit=result["first_visit"],
        last_visit=result["last_visit"],
        profile_created_at=result["profile_created_at"],
        profile_last_activity=result["profile_last_activity"],
    )


# ============================================================================
# Fonctions pour récupérer les ressources consultées
# ============================================================================

async def get_visited_resources(user_id: str, conn, limit: int = 100) -> List[VisitedResource]:
    """
    Récupère la liste des ressources consultées par l'utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        conn: Connexion à la base de données
        limit: Nombre maximum de ressources à retourner
        
    Returns:
        Liste de VisitedResource
    """
    query = """
        SELECT 
            kr.id AS resource_id,
            kr.title AS resource_title,
            kr.uri AS resource_uri,
            kr.resource_type,
            kr.author,
            kr.publication_date,
            COUNT(DISTINCT o.id) AS view_count,
            MAX(o.timestamp) AS last_viewed_at,
            MIN(o.timestamp) AS first_viewed_at,
            AVG(o.confidence) AS avg_confidence
        FROM observations o
        JOIN observation_targets ot ON o.id = ot.observation_id AND ot.target_type = 'entity'
        JOIN knowledge_resources kr ON ot.target_id = kr.id
        WHERE o.user_id = %s 
            AND o.observation_type = 'behavioral' 
            AND o.specific_type = 'resource_view'
        GROUP BY kr.id, kr.title, kr.uri, kr.resource_type, kr.author, kr.publication_date
        ORDER BY last_viewed_at DESC
        LIMIT %s
    """
    
    async with conn.cursor(aiomysql.DictCursor) as cursor:
        await cursor.execute(query, (user_id, limit))
        results = await cursor.fetchall()
    
    visited_resources = []
    for row in results:
        visited_resources.append(VisitedResource(
            resource_id=row["resource_id"],
            resource_title=row["resource_title"],
            resource_uri=row["resource_uri"],
            resource_type=row["resource_type"],
            author=row["author"],
            publication_date=row["publication_date"],
            view_count=row["view_count"] or 0,
            last_viewed_at=row["last_viewed_at"],
            first_viewed_at=row["first_viewed_at"],
            avg_confidence=round(row["avg_confidence"] or 0.0, 2),
        ))
    
    return visited_resources


# ============================================================================
# Fonctions pour récupérer les statistiques par thème
# ============================================================================

async def get_theme_stats(user_id: str, conn, limit: int = 50) -> List[ThemeStats]:
    """
    Récupère les statistiques pour chaque thème exploré par l'utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        conn: Connexion à la base de données
        limit: Nombre maximum de thèmes à retourner
        
    Returns:
        Liste de ThemeStats
    """
    query = """
        SELECT 
            t.id AS theme_id,
            t.name AS theme_name,
            t.description AS theme_description,
            COALESCE(uit.weight, 0) AS interest_weight,
            COALESCE(uit.confidence, 0) AS interest_confidence,
            COUNT(DISTINCT o.id) AS observation_count,
            COUNT(DISTINCT CASE WHEN o.observation_type = 'behavioral' THEN o.id END) AS behavioral_count,
            COUNT(DISTINCT CASE WHEN o.observation_type = 'evaluative' THEN o.id END) AS evaluative_count,
            COUNT(DISTINCT ki.id) AS knowledge_items_count,
            COUNT(DISTINCT CASE WHEN uks.status = 'demonstrated' THEN uks.knowledge_id END) AS demonstrated_count,
            COUNT(DISTINCT CASE WHEN uks.status = 'developing' THEN uks.knowledge_id END) AS developing_count,
            COUNT(DISTINCT CASE WHEN uks.status = 'encountered' THEN uks.knowledge_id END) AS encountered_count,
            COUNT(DISTINCT CASE WHEN uks.status = 'unknown' THEN uks.knowledge_id END) AS unknown_count,
            MAX(o.timestamp) AS last_interaction_at,
            MIN(o.timestamp) AS first_interaction_at
        FROM themes t
        LEFT JOIN user_interests_themes uit ON t.id = uit.theme_id AND uit.user_id = %s
        LEFT JOIN observations o ON o.user_id = %s
            AND EXISTS (
                SELECT 1 FROM observation_targets ot2 
                WHERE ot2.observation_id = o.id 
                    AND ot2.target_type = 'theme' 
                    AND ot2.target_id = t.id
            )
        LEFT JOIN observation_targets ot ON o.id = ot.observation_id AND ot.target_type = 'theme' AND ot.target_id = t.id
        LEFT JOIN knowledge_item_themes kit ON t.id = kit.theme_id
        LEFT JOIN knowledge_items ki ON kit.knowledge_id = ki.id
        LEFT JOIN user_knowledge_states uks ON %s = uks.user_id AND uks.knowledge_id = ki.id
        WHERE t.id IS NOT NULL
        GROUP BY t.id, t.name, t.description, uit.weight, uit.confidence
        HAVING observation_count > 0 OR interest_weight > 0
        ORDER BY interest_weight DESC, observation_count DESC
        LIMIT %s
    """
    
    async with conn.cursor(aiomysql.DictCursor) as cursor:
        await cursor.execute(query, (user_id, user_id, user_id, limit))
        results = await cursor.fetchall()
    
    theme_stats = []
    for row in results:
        theme_stats.append(ThemeStats(
            theme_id=row["theme_id"],
            theme_name=row["theme_name"],
            theme_description=row["theme_description"],
            interest_weight=round(row["interest_weight"] or 0.0, 4),
            interest_confidence=round(row["interest_confidence"] or 0.0, 2),
            observation_count=row["observation_count"] or 0,
            behavioral_count=row["behavioral_count"] or 0,
            evaluative_count=row["evaluative_count"] or 0,
            knowledge_items_count=row["knowledge_items_count"] or 0,
            demonstrated_count=row["demonstrated_count"] or 0,
            developing_count=row["developing_count"] or 0,
            encountered_count=row["encountered_count"] or 0,
            unknown_count=row["unknown_count"] or 0,
            last_interaction_at=row["last_interaction_at"],
            first_interaction_at=row["first_interaction_at"],
        ))
    
    return theme_stats


# ============================================================================
# Fonctions pour récupérer les éléments de connaissance par thème
# ============================================================================

async def get_knowledge_by_theme(user_id: str, conn, limit_per_theme: int = 20) -> Dict[str, ThemeKnowledgeGroup]:
    """
    Récupère les éléments de connaissance groupés par thème pour un utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        conn: Connexion à la base de données
        limit_per_theme: Nombre maximum de connaissances par thème
        
    Returns:
        Dictionnaire avec clé = theme_name et valeur = ThemeKnowledgeGroup
    """
    # Récupérer toutes les connaissances de l'utilisateur avec leurs thèmes
    query = """
        SELECT 
            ki.id AS knowledge_id,
            ki.proposition,
            ki.summary,
            uks.status,
            uks.score,
            uks.confidence,
            uks.last_interaction_at,
            uks.created_at,
            t.id AS theme_id,
            t.name AS theme_name,
            kit.relevance AS theme_relevance,
            (
                SELECT JSON_ARRAYAGG(
                    JSON_OBJECT(
                        'entity_id', e.id,
                        'entity_name', e.name,
                        'entity_type', e.type,
                        'relevance', kie.relevance
                    )
                )
                FROM knowledge_item_entities kie
                JOIN entities e ON kie.entity_id = e.id
                WHERE kie.knowledge_id = ki.id
            ) AS entities_json,
            (
                SELECT JSON_ARRAYAGG(
                    JSON_OBJECT(
                        'source_id', ks.resource_id,
                        'excerpt', ks.excerpt,
                        'page', ks.page,
                        'confidence', ks.confidence
                    )
                )
                FROM knowledge_sources ks
                WHERE ks.knowledge_id = ki.id
            ) AS sources_json
        FROM user_knowledge_states uks
        JOIN knowledge_items ki ON uks.knowledge_id = ki.id
        JOIN knowledge_item_themes kit ON ki.id = kit.knowledge_id
        JOIN themes t ON kit.theme_id = t.id
        WHERE uks.user_id = %s
        ORDER BY t.name, kit.relevance DESC, uks.score DESC
    """
    
    async with conn.cursor(aiomysql.DictCursor) as cursor:
        await cursor.execute(query, (user_id,))
        results = await cursor.fetchall()
    
    # Grouper par thème
    knowledge_by_theme: Dict[str, ThemeKnowledgeGroup] = {}
    
    for row in results:
        theme_name = row["theme_name"]
        
        # Parser les JSON arrays
        entities = []
        if row["entities_json"]:
            entities_data = json.loads(row["entities_json"])
            for e in entities_data:
                entities.append(EntityInfo(
                    entity_id=e.get("entity_id"),
                    entity_name=e.get("entity_name", ""),
                    entity_type=e.get("entity_type", "other"),
                    relevance=e.get("relevance", 1.0)
                ))
        
        sources = []
        if row["sources_json"]:
            sources_data = json.loads(row["sources_json"])
            for s in sources_data:
                sources.append(SourceInfo(
                    source_id=s.get("source_id"),
                    excerpt=s.get("excerpt"),
                    page=s.get("page"),
                    confidence=s.get("confidence", 1.0),
                    resource_title=None  # Peut être enrichi avec une requête supplémentaire si besoin
                ))
        
        knowledge_item = KnowledgeItem(
            knowledge_id=row["knowledge_id"],
            proposition=row["proposition"],
            summary=row["summary"],
            status=KnowledgeStatus(row["status"]) if row["status"] else KnowledgeStatus.UNKNOWN,
            score=round(row["score"] or 0.0, 2),
            confidence=round(row["confidence"] or 0.5, 2),
            last_interaction_at=row["last_interaction_at"],
            created_at=row["created_at"],
            entities=entities,
            sources=sources,
        )
        
        # Créer ou mettre à jour le groupe de thème
        if theme_name not in knowledge_by_theme:
            knowledge_by_theme[theme_name] = ThemeKnowledgeGroup(
                theme_id=row["theme_id"],
                theme_name=theme_name,
                knowledge_items=[],
            )
        
        # Limiter le nombre de connaissances par thème
        if len(knowledge_by_theme[theme_name].knowledge_items) < limit_per_theme:
            knowledge_by_theme[theme_name].knowledge_items.append(knowledge_item)
    
    return knowledge_by_theme


# ============================================================================
# Fonctions pour récupérer les observations
# ============================================================================

async def get_observation_type_stats(user_id: str, conn) -> List[ObservationTypeStats]:
    """
    Récupère le nombre d'observations par famille (déclarative, comportementale, évaluative).
    
    Args:
        user_id: Identifiant de l'utilisateur
        conn: Connexion à la base de données
        
    Returns:
        Liste de ObservationTypeStats (une entrée par famille, même à 0)
    """
    query = """
        SELECT 
            observation_type,
            COUNT(*) AS count,
            MAX(timestamp) AS last_at
        FROM observations 
        WHERE user_id = %s 
        GROUP BY observation_type
    """
    
    async with conn.cursor(aiomysql.DictCursor) as cursor:
        await cursor.execute(query, (user_id,))
        results = await cursor.fetchall()
    
    stats_by_type = {row["observation_type"]: row for row in results}
    
    type_stats = []
    for obs_type in ObservationType:
        row = stats_by_type.get(obs_type.value)
        type_stats.append(ObservationTypeStats(
            observation_type=obs_type,
            count=row["count"] if row else 0,
            last_at=row["last_at"] if row else None,
        ))
    
    return type_stats


async def get_recent_observations(user_id: str, conn, limit: int = 50) -> List[ObservationRecord]:
    """
    Récupère les observations les plus récentes d'un utilisateur.
    
    Args:
        user_id: Identifiant de l'utilisateur
        conn: Connexion à la base de données
        limit: Nombre maximum d'observations à retourner
        
    Returns:
        Liste de ObservationRecord, triée de la plus récente à la plus ancienne
    """
    query = """
        SELECT 
            o.id AS observation_id,
            o.observation_type,
            o.specific_type,
            o.timestamp,
            o.confidence,
            o.is_raw,
            o.context,
            (
                SELECT GROUP_CONCAT(
                    CONCAT(ot.target_type, ':', ot.target_id, ':', ot.weight)
                    SEPARATOR ','
                )
                FROM observation_targets ot 
                WHERE ot.observation_id = o.id
            ) AS targets_str
        FROM observations o
        WHERE o.user_id = %s
        ORDER BY o.timestamp DESC, o.id DESC
        LIMIT %s
    """
    
    async with conn.cursor(aiomysql.DictCursor) as cursor:
        await cursor.execute(query, (user_id, limit))
        results = await cursor.fetchall()
    
    if not results:
        return []
    
    # Récupérer les libellés des cibles en une seule requête par type
    target_ids_by_type: Dict[str, set] = {"knowledge": set(), "theme": set(), "entity": set()}
    parsed_targets: List[List[Dict[str, Any]]] = []
    
    for row in results:
        targets = []
        if row["targets_str"]:
            for part in row["targets_str"].split(","):
                pieces = part.split(":")
                if len(pieces) < 2:
                    continue
                target_type, target_id_str = pieces[0], pieces[1]
                try:
                    target_id = int(target_id_str)
                except ValueError:
                    continue
                try:
                    weight = float(pieces[2]) if len(pieces) > 2 else 1.0
                except ValueError:
                    weight = 1.0
                targets.append({"target_type": target_type, "target_id": target_id, "weight": weight})
                if target_type in target_ids_by_type:
                    target_ids_by_type[target_type].add(target_id)
        parsed_targets.append(targets)
    
    labels_by_type: Dict[str, Dict[int, str]] = {}
    label_queries = {
        "knowledge": ("SELECT id, proposition FROM knowledge_items WHERE id IN (%s)", "proposition"),
        "theme": ("SELECT id, name FROM themes WHERE id IN (%s)", "name"),
        "entity": ("SELECT id, name FROM entities WHERE id IN (%s)", "name"),
    }
    
    async with conn.cursor(aiomysql.DictCursor) as cursor:
        for target_type, ids in target_ids_by_type.items():
            if not ids or target_type not in label_queries:
                continue
            query_tpl, label_col = label_queries[target_type]
            placeholders = ", ".join(["%s"] * len(ids))
            await cursor.execute(query_tpl % placeholders, tuple(ids))
            label_rows = await cursor.fetchall()
            labels_by_type[target_type] = {r["id"]: r[label_col] for r in label_rows}
    
    observations = []
    for row, targets in zip(results, parsed_targets):
        target_infos = []
        for t in targets:
            label = labels_by_type.get(t["target_type"], {}).get(t["target_id"])
            target_infos.append(ObservationTargetInfo(
                target_type=t["target_type"],
                target_id=t["target_id"],
                weight=t["weight"],
                target_label=label,
            ))
        
        context = {}
        if row["context"]:
            try:
                context = json.loads(row["context"])
            except (TypeError, ValueError):
                context = {"raw": str(row["context"])}
        
        # Construire un résumé lisible du contexte
        context_parts = []
        for key in ("page", "session_id", "resource_id", "device"):
            if context.get(key) is not None:
                context_parts.append(f"{key}: {context[key]}")
        context_display = " | ".join(context_parts) if context_parts else None
        
        observations.append(ObservationRecord(
            observation_id=row["observation_id"],
            observation_type=ObservationType(row["observation_type"]),
            specific_type=row["specific_type"],
            timestamp=row["timestamp"],
            confidence=round(float(row["confidence"] or 1.0), 2),
            is_raw=bool(row["is_raw"]) if row["is_raw"] is not None else True,
            context=context,
            context_display=context_display,
            targets=target_infos,
            payload_preview=None,
        ))
    
    return observations


# ============================================================================
# Fonction principale pour récupérer toutes les données du profil
# ============================================================================

async def get_user_profile_data(user_id: str, conn) -> UserProfileResponse:
    """
    Récupère toutes les données nécessaires pour la page de profil.
    
    Args:
        user_id: Identifiant de l'utilisateur
        conn: Connexion à la base de données
        
    Returns:
        UserProfileResponse avec toutes les données structurées
    """
    # Récupérer le profil utilisateur
    profile = await get_user_profile(user_id, conn)
    if not profile:
        raise ValueError(f"Utilisateur {user_id} introuvable")
    
    # Récupérer les statistiques
    stats = await get_profile_stats(user_id, conn)
    
    # Récupérer les ressources consultées
    visited_resources = await get_visited_resources(user_id, conn)
    
    # Récupérer les statistiques par thème
    theme_stats = await get_theme_stats(user_id, conn)
    
    # Récupérer les éléments de connaissance par thème
    knowledge_by_theme = await get_knowledge_by_theme(user_id, conn)
    
    # Récupérer l'état des observations (types et historique récent)
    observation_type_stats = await get_observation_type_stats(user_id, conn)
    recent_observations = await get_recent_observations(user_id, conn)
    
    return UserProfileResponse(
        user_id=user_id,
        profile=profile,
        stats=stats,
        visited_resources=visited_resources,
        theme_stats=theme_stats,
        knowledge_by_theme=knowledge_by_theme,
        observation_type_stats=observation_type_stats,
        recent_observations=recent_observations,
    )


# ============================================================================
# Fonction utilitaire pour vérifier l'existence d'un utilisateur
# ============================================================================

async def user_exists(user_id: str, conn) -> bool:
    """
    Vérifie si un utilisateur existe dans la base de données.
    
    Args:
        user_id: Identifiant de l'utilisateur
        conn: Connexion à la base de données
        
    Returns:
        True si l'utilisateur existe, False sinon
    """
    query = "SELECT 1 FROM user_profiles WHERE user_id = %s LIMIT 1"
    async with conn.cursor() as cursor:
        await cursor.execute(query, (user_id,))
        result = await cursor.fetchone()
    return result is not None
