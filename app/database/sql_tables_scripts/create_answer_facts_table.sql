-- Liste des faits/affirmations constituant une réponse de référence.
-- Map l'answer_id d'une réponse à chacune de ses affirmations atomiques.
-- importance: "essential" (fait indispensable à la réponse) ou "optional"
-- (information secondaire qui apporte de la consistance à un fait principal,
-- ou fait d'une énumération au même niveau d'importance).
CREATE TABLE IF NOT EXISTS text_answer_facts (
    fact_id INT AUTO_INCREMENT PRIMARY KEY,
    answer_id BIGINT UNSIGNED NOT NULL,
    content TEXT NOT NULL,
    position INT NOT NULL DEFAULT 0,
    importance VARCHAR(16) NOT NULL DEFAULT 'essential',
    model VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT fk_facts_answer FOREIGN KEY (answer_id)
        REFERENCES text_question_answers (answer_id) ON DELETE CASCADE,
    CONSTRAINT valid_importance CHECK (importance IN ('essential', 'optional')),
    INDEX idx_facts_answer (answer_id)
);
