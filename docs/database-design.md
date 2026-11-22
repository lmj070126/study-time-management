
# 学生学习时间管理与效率分析系统
## 数据库设计文档 V1.0

### 1. 数据库基本信息

- 数据库名称：study_time_db
- 数据库系统：MySQL 8
- 存储引擎：InnoDB
- 字符集：utf8mb4
- 后端：FastAPI + SQLAlchemy
- 时间存储：UTC
- 业务时间：Asia/Shanghai
- 用户角色：student、teacher、admin

### 2. 数据库表设计

#### 2.1 classes 班级表
- id：BIGINT，主键
- class_name：VARCHAR(80)，唯一，非空
- teacher_id：BIGINT，关联users.id，可为空
- created_at：DATETIME

#### 2.2 users 用户表
- id：BIGINT，主键
- username：VARCHAR(64)，唯一，非空
- password_hash：VARCHAR(255)，非空
- role：ENUM('student','teacher','admin')
- class_id：BIGINT，关联classes.id，可为空
- alias：VARCHAR(80)，学生化名
- is_active：BOOLEAN，默认TRUE
- created_at：DATETIME

要求：
- 密码只保存哈希值
- 学生只能操作本人数据
- 班主任只能访问有权限的班级汇总
- 同一班级的学生化名不能重复

#### 2.3 subjects 科目表
- id：BIGINT，主键
- subject_name：VARCHAR(80)，唯一，非空
- enabled：BOOLEAN，默认TRUE
- created_at：DATETIME

#### 2.4 tasks 学习任务表
- id：BIGINT，主键
- student_id：BIGINT，关联users.id
- subject_id：BIGINT，关联subjects.id
- title：VARCHAR(200)，非空
- description：TEXT
- status：VARCHAR(20)
- created_at：DATETIME
- updated_at：DATETIME

#### 2.5 focus_sessions 专注会话表
- id：BIGINT，主键
- student_id：BIGINT，关联users.id
- task_id：BIGINT，关联tasks.id
- planned_minutes：INT，默认25
- rest_minutes：INT，默认5
- started_at：DATETIME
- ended_at：DATETIME，可为空
- status：VARCHAR(20)
- created_at：DATETIME

#### 2.6 study_records 学习记录表
- id：BIGINT，主键
- focus_session_id：BIGINT，唯一，关联focus_sessions.id
- student_id：BIGINT，关联users.id
- subject_id：BIGINT，关联subjects.id
- started_at：DATETIME，非空
- ended_at：DATETIME，非空
- minutes：INT，必须大于0
- rating：TINYINT，取值1至5
- created_at：DATETIME

重要约束：
- ended_at 必须晚于 started_at
- 每个focus_session_id最多产生一条学习记录
- 完成专注必须在一个事务中更新会话并写入记录
- 只能为当前登录学生生成学习记录
- 后端核实记录分钟数，不能直接信任前端提交的数据

#### 2.7 badge_rules 勋章规则表
- id：BIGINT，主键
- badge_code：VARCHAR(50)，唯一
- badge_name：VARCHAR(100)
- required_days：INT，默认7
- enabled：BOOLEAN

#### 2.8 user_badges 用户勋章表
- id：BIGINT，主键
- student_id：BIGINT，关联users.id
- badge_rule_id：BIGINT，关联badge_rules.id
- streak_start_date：DATE
- streak_end_date：DATE
- awarded_at：DATETIME

唯一约束：
(student_id, badge_rule_id, streak_start_date)

同一连续学习周期不能重复颁发相同勋章。

#### 2.9 daily_reminders 每日提醒表
- id：BIGINT，主键
- student_id：BIGINT，关联users.id
- study_date：DATE
- reminder_type：VARCHAR(30)
- reminded_at：DATETIME

唯一约束：
(student_id, study_date, reminder_type)

同一天累计学习达到180分钟后只提醒一次。

### 3. 数据库关系

- classes 1:N users（学生所属班级）
- users 1:N tasks
- subjects 1:N tasks
- tasks 1:N focus_sessions
- focus_sessions 1:0..1 study_records
- users 1:N study_records
- subjects 1:N study_records
- users 1:N user_badges
- badge_rules 1:N user_badges
- users 1:N daily_reminders

classes.teacher_id单独指向负责该班的教师用户。

### 4. 初始化数据要求

- 建立一个6人班级
- 建立一个4人班级
- 创建相应班主任与管理员测试账号
- 创建数学、英语、计算机等科目
- 为6人班指定学生生成最近4个完整周的学习记录
- 四周总分钟分别为100、120、80、100
- 日期根据运行脚本时的当前周动态生成
- 再次运行初始化脚本不得重复生成测试数据

### 5. 数据库验收

- 所有表可以正常建立
- 主键、外键与唯一约束有效
- 学习记录分钟数大于0，自评范围1至5
- 同一专注会话不能重复生成记录
- 6人班和4人班人数准确
- 指定学生四周学习分钟准确
- 权限在后端校验，不仅依靠前端隐藏按钮
- 初始化脚本可重复执行
  