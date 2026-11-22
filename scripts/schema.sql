-- Project 20: Study Time Management and Efficiency Analysis System
-- Schema v1.0 | MySQL 8.0.16+ (or 8.4 LTS) | utf8mb4
-- Run against a development database; no DROP TABLE / DROP DATABASE statements.
-- The application must set UTC at every DB connection and apply authorization in FastAPI.

CREATE DATABASE IF NOT EXISTS study_time_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE study_time_db;
SET time_zone = '+00:00';

-- 1. Classes (teacher_id FK is added after users to avoid circular DDL references)
CREATE TABLE IF NOT EXISTS classes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  class_name VARCHAR(80) NOT NULL,
  teacher_id BIGINT UNSIGNED NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uk_classes_name (class_name),
  KEY idx_classes_teacher (teacher_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 2. Users: role and class authorization must ALSO be enforced by the backend.
CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('student', 'teacher', 'admin') NOT NULL,
  class_id BIGINT UNSIGNED NULL,
  alias VARCHAR(80) NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_username (username),
  UNIQUE KEY uk_users_class_alias (class_id, alias),
  KEY idx_users_role_class (role, class_id),
  CONSTRAINT fk_users_class FOREIGN KEY (class_id) REFERENCES classes (id)
    ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Establish the remaining side of the classes <-> users association once.
-- Re-running this script skips the FK if already present.
SET @add_teacher_fk = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE classes ADD CONSTRAINT fk_classes_teacher FOREIGN KEY (teacher_id) REFERENCES users(id) ON UPDATE RESTRICT ON DELETE RESTRICT',
    'SELECT ''fk_classes_teacher already exists'' AS info')
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND TABLE_NAME = 'classes'
    AND CONSTRAINT_NAME = 'fk_classes_teacher'
    AND CONSTRAINT_TYPE = 'FOREIGN KEY'
);
PREPARE stmt_teacher_fk FROM @add_teacher_fk;
EXECUTE stmt_teacher_fk;
DEALLOCATE PREPARE stmt_teacher_fk;

-- 3. Subjects
CREATE TABLE IF NOT EXISTS subjects (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  subject_name VARCHAR(80) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uk_subjects_name (subject_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 4. Tasks
CREATE TABLE IF NOT EXISTS tasks (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  subject_id BIGINT UNSIGNED NOT NULL,
  title VARCHAR(200) NOT NULL,
  description TEXT NULL,
  status ENUM('todo', 'in_progress', 'done', 'cancelled') NOT NULL DEFAULT 'todo',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY idx_tasks_student_status (student_id, status),
  KEY idx_tasks_subject (subject_id),
  CONSTRAINT fk_tasks_student FOREIGN KEY (student_id) REFERENCES users (id)
    ON UPDATE RESTRICT ON DELETE RESTRICT,
  CONSTRAINT fk_tasks_subject FOREIGN KEY (subject_id) REFERENCES subjects (id)
    ON UPDATE RESTRICT ON DELETE RESTRICT,
  CONSTRAINT chk_tasks_title CHECK (CHAR_LENGTH(TRIM(title)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 5. Focus sessions
CREATE TABLE IF NOT EXISTS focus_sessions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  task_id BIGINT UNSIGNED NOT NULL,
  planned_minutes INT NOT NULL DEFAULT 25,
  rest_minutes INT NOT NULL DEFAULT 5,
  started_at DATETIME(6) NULL,
  ended_at DATETIME(6) NULL,
  status ENUM('pending', 'running', 'paused', 'completed', 'abandoned') NOT NULL DEFAULT 'pending',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY idx_focus_student_started (student_id, started_at),
  KEY idx_focus_task (task_id),
  CONSTRAINT fk_focus_student FOREIGN KEY (student_id) REFERENCES users (id)
    ON UPDATE RESTRICT ON DELETE RESTRICT,
  CONSTRAINT fk_focus_task FOREIGN KEY (task_id) REFERENCES tasks (id)
    ON UPDATE RESTRICT ON DELETE RESTRICT,
  CONSTRAINT chk_focus_minutes CHECK (planned_minutes > 0 AND rest_minutes > 0),
  CONSTRAINT chk_focus_dates CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at > started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 6. Study records: at most one valid record per completed session
CREATE TABLE IF NOT EXISTS study_records (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  focus_session_id BIGINT UNSIGNED NOT NULL,
  student_id BIGINT UNSIGNED NOT NULL,
  subject_id BIGINT UNSIGNED NOT NULL,
  started_at DATETIME(6) NOT NULL,
  ended_at DATETIME(6) NOT NULL,
  minutes INT NOT NULL,
  rating TINYINT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uk_records_session (focus_session_id),
  KEY idx_records_student_started (student_id, started_at),
  KEY idx_records_student_subject_started (student_id, subject_id, started_at),
  CONSTRAINT fk_records_session FOREIGN KEY (focus_session_id) REFERENCES focus_sessions (id)
    ON UPDATE RESTRICT ON DELETE RESTRICT,
  CONSTRAINT fk_records_student FOREIGN KEY (student_id) REFERENCES users (id)
    ON UPDATE RESTRICT ON DELETE RESTRICT,
  CONSTRAINT fk_records_subject FOREIGN KEY (subject_id) REFERENCES subjects (id)
    ON UPDATE RESTRICT ON DELETE RESTRICT,
  CONSTRAINT chk_records_minutes CHECK (minutes > 0),
  CONSTRAINT chk_records_rating CHECK (rating BETWEEN 1 AND 5),
  CONSTRAINT chk_records_time CHECK (ended_at > started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 7. Badge rules
CREATE TABLE IF NOT EXISTS badge_rules (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  badge_code VARCHAR(50) NOT NULL,
  badge_name VARCHAR(100) NOT NULL,
  required_days INT NOT NULL DEFAULT 7,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (id),
  UNIQUE KEY uk_badge_code (badge_code),
  CONSTRAINT chk_badge_required_days CHECK (required_days > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 8. Student badges: streak_start_date identifies the ENTIRE continuous run.
-- It must remain the same as the streak extends, preventing repeated awards.
CREATE TABLE IF NOT EXISTS user_badges (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  badge_rule_id BIGINT UNSIGNED NOT NULL,
  streak_start_date DATE NOT NULL,
  streak_end_date DATE NOT NULL,
  awarded_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_badges_streak (student_id, badge_rule_id, streak_start_date),
  KEY idx_user_badges_rule (badge_rule_id),
  CONSTRAINT fk_user_badges_student FOREIGN KEY (student_id) REFERENCES users (id)
    ON UPDATE RESTRICT ON DELETE RESTRICT,
  CONSTRAINT fk_user_badges_rule FOREIGN KEY (badge_rule_id) REFERENCES badge_rules (id)
    ON UPDATE RESTRICT ON DELETE RESTRICT,
  CONSTRAINT chk_user_badges_dates CHECK (streak_end_date >= streak_start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 9. Daily reminder: one reminder per student/date/type
CREATE TABLE IF NOT EXISTS daily_reminders (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  study_date DATE NOT NULL,
  reminder_type VARCHAR(30) NOT NULL DEFAULT 'break_180',
  reminded_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uk_daily_reminder (student_id, study_date, reminder_type),
  CONSTRAINT fk_reminder_student FOREIGN KEY (student_id) REFERENCES users (id)
    ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Verify: expected number of project tables is 9.
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'study_time_db'
ORDER BY table_name;
