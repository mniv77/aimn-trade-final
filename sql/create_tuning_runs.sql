-- /home/MeirNiv/aimn-trade-final/sql/create_tuning_runs.sql
-- Run this once in MySQL to create the tuning_runs table

CREATE TABLE IF NOT EXISTS tuning_runs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    started_at  DATETIME NOT NULL,
    finished_at DATETIME,
    status      VARCHAR(20) DEFAULT 'running',  -- running / success / partial / failed
    summary     TEXT,
    log_text    LONGTEXT,
    created_at  DATETIME DEFAULT NOW()
);