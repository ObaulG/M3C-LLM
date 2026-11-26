-- Suppression de toutes les tables et vues créées par les scripts
-- de sql_tables_scripts/ (inverse des scripts de création).
--
-- Utilisation (depuis app/database/) :
--   python exec_sql.py sql_tables_scripts/drop_tables.sql
--
-- ATTENTION : cette opération est irréversible, toutes les données
-- des tables listées ci-dessous seront perdues.

SET FOREIGN_KEY_CHECKS = 0;

DROP VIEW IF EXISTS user_knowledge_with_themes;
DROP VIEW IF EXISTS user_knowledge_by_theme;
DROP VIEW IF EXISTS user_theme_stats_v2;
DROP VIEW IF EXISTS user_theme_stats;
DROP VIEW IF EXISTS user_visited_resources;
DROP VIEW IF EXISTS user_profile_stats;

DROP TABLE IF EXISTS chatbot_feedbacks;
DROP TABLE IF EXISTS chatbot_message_chunks;
DROP TABLE IF EXISTS chatbot_messages;
DROP TABLE IF EXISTS document_reading_sessions;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS indexing_jobs;
DROP TABLE IF EXISTS knowledge_item_entities;
DROP TABLE IF EXISTS knowledge_item_questions;
DROP TABLE IF EXISTS knowledge_item_themes;
DROP TABLE IF EXISTS knowledge_items;
DROP TABLE IF EXISTS knowledge_sources;
DROP TABLE IF EXISTS llm_interpretations;
DROP TABLE IF EXISTS model_evidences;
DROP TABLE IF EXISTS observation_payloads;
DROP TABLE IF EXISTS observation_targets;
DROP TABLE IF EXISTS observations;
DROP TABLE IF EXISTS question_session_questions;
DROP TABLE IF EXISTS question_sessions;
DROP TABLE IF EXISTS session_answers;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS text_answer_facts;
DROP TABLE IF EXISTS text_chunking_strategies;
DROP TABLE IF EXISTS text_chunks;
DROP TABLE IF EXISTS text_document_chunking_validation;
DROP TABLE IF EXISTS text_documents;
DROP TABLE IF EXISTS text_question_answers;
DROP TABLE IF EXISTS text_question_chunks;
DROP TABLE IF EXISTS text_questions;
DROP TABLE IF EXISTS themes;
DROP TABLE IF EXISTS entities;
DROP TABLE IF EXISTS user_interests_entities;
DROP TABLE IF EXISTS user_interests_themes;
DROP TABLE IF EXISTS user_knowledge_states;
DROP TABLE IF EXISTS user_mistral_api_keys;
DROP TABLE IF EXISTS user_model_history;
DROP TABLE IF EXISTS user_profiles;
DROP TABLE IF EXISTS user_sessions;

SET FOREIGN_KEY_CHECKS = 1;
