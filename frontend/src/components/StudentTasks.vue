
<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const props = defineProps({
  token: { type: String, required: true },
})

const emit = defineEmits(['unauthorized'])

const subjects = ref([])
const tasks = ref([])
const subjectId = ref(0)
const title = ref('')
const description = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')

const statusNames = {
  todo: '待开始',
  in_progress: '进行中',
  done: '已完成',
  cancelled: '已取消',
}

const visibleTasks = computed(() =>
  tasks.value.filter(t => t.status !== 'cancelled')
)

function auth() {
  return {
    headers: {
      Authorization: `Bearer ${props.token}`,
    },
  }
}

function handleError(err, fallback) {
  if (err.response?.status === 401) {
    emit('unauthorized')
    return
  }
  const detail = err.response?.data?.detail
  error.value = typeof detail === 'string' ? detail : fallback
}

async function refreshTasks() {
  loading.value = true
  error.value = ''

  try {
    const [subjectsResponse, tasksResponse] =
      await Promise.all([
        axios.get('/api/tasks/subjects', auth()),
        axios.get('/api/tasks', auth()),
      ])

    subjects.value = subjectsResponse.data
    tasks.value = tasksResponse.data

    if (!subjects.value.some(s => s.id === subjectId.value)) {
      subjectId.value = subjects.value[0]?.id ?? 0
    }
  } catch (err) {
    handleError(err, '学习任务加载失败')
  } finally {
    loading.value = false
  }
}

async function createTask() {
  if (saving.value || !title.value.trim() || !subjectId.value) return

  saving.value = true
  error.value = ''
  notice.value = ''

  try {
    const response = await axios.post(
      '/api/tasks',
      {
        subject_id: subjectId.value,
        title: title.value.trim(),
        description: description.value.trim() || null,
      },
      auth()
    )

    tasks.value.unshift(response.data)
    title.value = ''
    description.value = ''
    notice.value = '任务创建成功，已保存到数据库'
  } catch (err) {
    handleError(err, '创建任务失败')
  } finally {
    saving.value = false
  }
}

async function changeStatus(task, status) {
  error.value = ''
  notice.value = ''

  try {
    const response = await axios.patch(
      `/api/tasks/${task.id}`,
      { status },
      auth()
    )

    Object.assign(task, response.data)
    notice.value = '任务状态已更新'
  } catch (err) {
    handleError(err, '修改任务失败')
  }
}

async function cancelTask(task) {
  if (!window.confirm(`确定取消“${task.title}”吗？`)) return

  error.value = ''
  notice.value = ''

  try {
    await axios.delete(`/api/tasks/${task.id}`, auth())
    task.status = 'cancelled'
    notice.value = '任务已取消，历史记录仍保留'
  } catch (err) {
    handleError(err, '取消任务失败')
  }
}

onMounted(refreshTasks)
</script>

<template>
  <section class="tasks-panel">
    <div class="heading">
      <div>
        <span class="section-label">STUDY PLANNER</span>
        <h2>我的学习任务</h2>
        <p>制定计划，逐步完成今天的学习目标。</p>
      </div>
      <button class="refresh" @click="refreshTasks">
        刷新列表
      </button>
    </div>

    <form class="create-form" @submit.prevent="createTask">
      <h3>创建新任务</h3>

      <div class="form-grid">
        <select v-model.number="subjectId" required>
          <option :value="0" disabled>选择学习科目</option>
          <option
            v-for="subject in subjects"
            :key="subject.id"
            :value="subject.id"
          >
            {{ subject.subject_name }}
          </option>
        </select>

        <input
          v-model="title"
          placeholder="例如：完成高等数学第一章练习"
          maxlength="200"
          required
        />
      </div>

      <textarea
        v-model="description"
        placeholder="任务说明（选填）"
        maxlength="3000"
        rows="2"
      />

      <button
        type="submit"
        class="primary"
        :disabled="saving || !subjectId"
      >
        {{ saving ? '正在保存...' : '+ 创建学习任务' }}
      </button>
    </form>

    <p v-if="error" class="message error" role="alert">
      {{ error }}
    </p>
    <p v-if="notice" class="message notice" role="status">
      {{ notice }}
    </p>

    <div class="list-heading">
      <h3>任务列表</h3>
      <span>共 {{ visibleTasks.length }} 项</span>
    </div>

    <p v-if="loading">正在加载真实任务数据...</p>

    <div v-else-if="!visibleTasks.length" class="empty">
      目前还没有任务，创建第一项学习计划吧。
    </div>

    <div v-else class="task-list">
      <article
        v-for="task in visibleTasks"
        :key="task.id"
        class="task-card"
      >
        <div class="task-main">
          <div class="task-meta">
            <span class="subject">{{ task.subject_name }}</span>
            <span class="status" :class="task.status">
              {{ statusNames[task.status] || task.status }}
            </span>
          </div>

          <h4>{{ task.title }}</h4>
          <p v-if="task.description">{{ task.description }}</p>
        </div>

        <div class="task-actions">
          <button
            v-if="task.status === 'todo'"
            @click="changeStatus(task, 'in_progress')"
          >
            开始任务
          </button>

          <button
            v-if="task.status === 'in_progress'"
            @click="changeStatus(task, 'done')"
          >
            标记完成
          </button>

          <button
            v-if="task.status !== 'done'"
            class="danger"
            @click="cancelTask(task)"
          >
            取消
          </button>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.tasks-panel {
  margin-top: 36px;
  padding: 32px;
  background: white;
  border-radius: 18px;
  box-shadow: 0 8px 30px #1d37600b;
}

.heading, .list-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.section-label {
  color: #536bd0;
  letter-spacing: 2px;
  font-size: 12px;
  font-weight: 700;
}

.heading h2 {
  margin: 12px 0;
  color: #1c2b4b;
}

.heading p {
  color: #78859d;
}

.refresh, .task-actions button {
  background: white;
  border: 1px solid #dbe2ef;
  border-radius: 9px;
  padding: 10px 14px;
  cursor: pointer;
  color: #34466b;
}

.create-form {
  margin-top: 24px;
  padding: 24px;
  border-radius: 14px;
  background: #f7f9ff;
}

.create-form h3 {
  margin-top: 0;
  color: #24365b;
}

.form-grid {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 12px;
}

input, select, textarea {
  width: 100%;
  padding: 13px;
  border: 1px solid #dae1ee;
  border-radius: 9px;
  background: white;
  color: #24365b;
  font: inherit;
}

textarea {
  margin-top: 12px;
  resize: vertical;
}

.primary {
  margin-top: 15px;
  padding: 13px 20px;
  color: white;
  border: none;
  border-radius: 10px;
  background: #4963c8;
  font-weight: 650;
  cursor: pointer;
}

button:disabled {
  opacity: .6;
  cursor: not-allowed;
}

.list-heading {
  margin: 28px 0 16px;
}

.list-heading span {
  color: #8993a8;
}

.task-list {
  display: grid;
  gap: 14px;
}

.task-card {
  padding: 20px;
  border: 1px solid #e7ecf5;
  border-radius: 13px;
}

.task-meta {
  display: flex;
  gap: 10px;
  align-items: center;
}

.subject, .status {
  padding: 5px 10px;
  border-radius: 7px;
  font-size: 12px;
  background: #eef2ff;
  color: #435dc1;
}

.status.done {
  color: #15845c;
  background: #e4f8ee;
}

.status.in_progress {
  color: #ad711c;
  background: #fff1dc;
}

.task-main h4 {
  margin: 14px 0 8px;
  color: #24365b;
}

.task-main p {
  color: #78859d;
  margin: 0;
  overflow-wrap: anywhere;
}

.task-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 18px;
}

.task-actions .danger {
  color: #be4755;
}

.message {
  padding: 12px;
  border-radius: 8px;
}

.error {
  background: #fff0f0;
  color: #ae3548;
}

.notice {
  background: #edf9f2;
  color: #16734e;
}

.empty {
  padding: 32px;
  text-align: center;
  background: #f7f9ff;
  border-radius: 12px;
  color: #78859d;
}

@media (max-width: 650px) {
  .tasks-panel { padding: 20px; }
  .form-grid { grid-template-columns: 1fr; }
  .heading { align-items: flex-start; }
}
</style>
