ALTER TABLE student_node_mastery
  ADD COLUMN inferred TINYINT(1) NOT NULL DEFAULT 0 AFTER observations;
