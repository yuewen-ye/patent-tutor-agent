CREATE TABLE IF NOT EXISTS learner_learning_plans (
  plan_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL,
  source_session_id VARCHAR(128),
  last_session_id VARCHAR(128),
  learning_goal TEXT NOT NULL,
  learning_goal_hash CHAR(64) NOT NULL,
  knowledge_graph_version VARCHAR(64) NOT NULL,
  plan_version INT NOT NULL,
  status VARCHAR(32) NOT NULL,
  current_node_id VARCHAR(128),
  current_order_idx INT,
  progress_json JSON NOT NULL,
  replan_reason TEXT,
  last_progress_decision JSON,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  completed_at DATETIME(6),
  CONSTRAINT fk_learner_plans_student
    FOREIGN KEY(student_id) REFERENCES students(student_id),
  CONSTRAINT fk_learner_plans_source_session
    FOREIGN KEY(source_session_id) REFERENCES sessions(session_id),
  CONSTRAINT fk_learner_plans_last_session
    FOREIGN KEY(last_session_id) REFERENCES sessions(session_id),
  UNIQUE KEY uq_learner_plan_version(student_id, plan_version),
  CHECK(status IN ('active', 'completed', 'superseded'))
) ENGINE=InnoDB;

CREATE INDEX ix_learner_plans_active
  ON learner_learning_plans(student_id, status, plan_version);

CREATE TABLE IF NOT EXISTS learner_learning_plan_nodes (
  plan_node_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  plan_id VARCHAR(128) NOT NULL,
  node_id VARCHAR(128) NOT NULL,
  node_name VARCHAR(255) NOT NULL,
  prerequisites JSON NOT NULL,
  difficulty_cap VARCHAR(32),
  strategy TEXT,
  node_json JSON NOT NULL,
  order_idx INT NOT NULL,
  node_status VARCHAR(32) NOT NULL,
  completed_at DATETIME(6),
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_learner_plan_nodes_plan
    FOREIGN KEY(plan_id) REFERENCES learner_learning_plans(plan_id),
  UNIQUE KEY uq_learner_plan_node(plan_id, node_id),
  UNIQUE KEY uq_learner_plan_order(plan_id, order_idx),
  CHECK(node_status IN ('pending', 'current', 'completed'))
) ENGINE=InnoDB;
