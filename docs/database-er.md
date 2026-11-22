
# 学生学习时间管理与效率分析系统
## 数据库 ER 关系图

```mermaid
erDiagram
    CLASSES {
        BIGINT id PK
        VARCHAR class_name UK
        BIGINT teacher_id FK
        DATETIME created_at
    }

    USERS {
        BIGINT id PK
        VARCHAR username UK
        VARCHAR password_hash
        VARCHAR role
        BIGINT class_id FK
        VARCHAR alias
        BOOLEAN is_active
    }

    SUBJECTS {
        BIGINT id PK
        VARCHAR subject_name UK
        BOOLEAN enabled
    }

    TASKS {
        BIGINT id PK
        BIGINT student_id FK
        BIGINT subject_id FK
        VARCHAR title
        VARCHAR status
    }

    FOCUS_SESSIONS {
        BIGINT id PK
        BIGINT student_id FK
        BIGINT task_id FK
        INT planned_minutes
        INT rest_minutes
        DATETIME started_at
        DATETIME ended_at
        VARCHAR status
    }

    STUDY_RECORDS {
        BIGINT id PK
        BIGINT focus_session_id FK,UK
        BIGINT student_id FK
        BIGINT subject_id FK
        DATETIME started_at
        DATETIME ended_at
        INT minutes
        TINYINT rating
    }

    BADGE_RULES {
        BIGINT id PK
        VARCHAR badge_code UK
        VARCHAR badge_name
        INT required_days
        BOOLEAN enabled
    }

    USER_BADGES {
        BIGINT id PK
        BIGINT student_id FK
        BIGINT badge_rule_id FK
        DATE streak_start_date
        DATE streak_end_date
    }

    DAILY_REMINDERS {
        BIGINT id PK
        BIGINT student_id FK
        DATE study_date
        VARCHAR reminder_type
    }

    CLASSES ||--o{ USERS : contains_students
    USERS ||--o{ CLASSES : teaches
    USERS ||--o{ TASKS : creates
    SUBJECTS ||--o{ TASKS : categorizes
    USERS ||--o{ FOCUS_SESSIONS : starts
    TASKS ||--o{ FOCUS_SESSIONS : contains
    FOCUS_SESSIONS ||--o| STUDY_RECORDS : produces
    USERS ||--o{ STUDY_RECORDS : owns
    SUBJECTS ||--o{ STUDY_RECORDS : belongs_to
    USERS ||--o{ USER_BADGES : earns
    BADGE_RULES ||--o{ USER_BADGES : defines
    USERS ||--o{ DAILY_REMINDERS : receives
```

## 关系说明

- 一个班级有多个学生。
- 一位班主任可以管理多个班级。
- 一个学生可以创建多个学习任务。
- 一个任务可以对应多次专注会话。
- 一次专注会话最多生成一条学习记录。
- 一个学生可以获得多个不同连续周期的勋章。
- 每个学生每天同种提醒只允许记录一次。

## 数据完整性约束

1. 学习记录的 focus_session_id 必须唯一。
2. 学习分钟必须大于0，自评必须为1至5。
3. 勋章按学生、规则和连续学习周期设置联合唯一约束。
4. 每日提醒按学生、日期和提醒类型设置联合唯一约束。
5. 班主任不能通过更改请求参数查看学生个人明细。
6. 初始化数据必须支持重复执行，不产生重复记录。
```
