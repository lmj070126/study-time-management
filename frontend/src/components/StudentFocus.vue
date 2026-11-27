<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import axios from 'axios'

const props = defineProps({
  token: { type: String, required: true },
})
const emit = defineEmits(['unauthorized'])

const tasks = ref([])
const records = ref([])
const taskId = ref(null)
const plannedMinutes = ref(25)
const session = ref(null)
const remainingSeconds = ref(25 * 60)
const rating = ref(5)
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
let ticker = null

const auth = () => ({
  headers: { Authorization: `Bearer ${props.token}` },
})

const allowedTasks = computed(() =>
  tasks.value.filter((task) => ['todo', 'in_progress'].includes(task.status)),
)
const hasActiveSession = computed(() =>
  session.value != null && ['pending', 'running', 'paused'].includes(session.value.status),
)
const isRunning = computed(() => session.value?.status === 'running')
const totalSeconds = computed(() =>
  (session.value?.planned_minutes ?? plannedMinutes.value) * 60,
)
const elapsedRatio = computed(() => {
  if (!hasActiveSession.value || totalSeconds.value <= 0) return 0
  return Math.min(100, Math.max(0, (1 - remainingSeconds.value / totalSeconds.value) * 100))
})
const remainingText = computed(() => {
  const min = Math.floor(remainingSeconds.value / 60)
  const sec = remainingSeconds.value % 60
  return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
})
const canComplete = computed(() => isRunning.value && remainingSeconds.value === 0 && !busy.value)

// 后端 MySQL 的 started_at 是不含时区标记的 UTC DATETIME。
function utcMillis(value) {
  if (!value) return NaN
  const normalized = String(value).replace(' ', 'T')
  const hasZone = /(?:Z|[+-]\d\d:?\d\d)$/i.test(normalized)
  return Date.parse(hasZone ? normalized : `${normalized}Z`)
}

function formatTime(value) {
  const timestamp = utcMillis(value)
  return Number.isFinite(timestamp)
    ? new Date(timestamp).toLocaleString('zh-CN', { hour12: false })
    : '—'
}

function updateCountdown() {
  if (!session.value) {
    remainingSeconds.value = plannedMinutes.value * 60
    return
  }
  const started = utcMillis(session.value.started_at)
  if (!Number.isFinite(started)) {
    remainingSeconds.value = session.value.planned_minutes * 60
    return
  }
  const elapsed = Math.max(0, Math.floor((Date.now() - started) / 1000))
  remainingSeconds.value = Math.max(0, session.value.planned_minutes * 60 - elapsed)
}

function reportError(err, fallback) {
  if (err.response?.status === 401) {
    emit('unauthorized')
    return
  }
  const detail = err.response?.data?.detail
  error.value = typeof detail === 'string' ? detail : fallback
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [taskResult, sessionResult, recordResult] = await Promise.all([
      axios.get('/api/tasks', auth()),
      axios.get('/api/focus', auth()),
      axios.get('/api/focus/records', auth()),
    ])
    tasks.value = taskResult.data
    records.value = recordResult.data
    session.value = sessionResult.data.find((row) =>
      ['pending', 'running', 'paused'].includes(row.status),
    ) ?? null
    if (session.value) {
      taskId.value = session.value.task_id
    } else if (!allowedTasks.value.some((task) => task.id === taskId.value)) {
      taskId.value = allowedTasks.value[0]?.id ?? null
    }
    updateCountdown()
  } catch (err) {
    reportError(err, '加载番茄钟数据失败，请检查后端服务')
  } finally {
    loading.value = false
  }
}

async function startFocus() {
  if (busy.value || hasActiveSession.value || !taskId.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const response = await axios.post('/api/focus/start', {
      task_id: taskId.value,
      planned_minutes: plannedMinutes.value,
      rest_minutes: 5,
    }, auth())

    // 即使随后刷新失败，也保留已启动会话的ID，避免再次误点启动。
    session.value = {
      id: response.data.session_id,
      task_id: response.data.task_id,
      planned_minutes: response.data.planned_minutes,
      status: response.data.status,
      started_at: new Date().toISOString(),
    }
    updateCountdown()
    notice.value = `专注会话 #${response.data.session_id} 已启动`
    await refresh() // 获取 MySQL 的权威 started_at，支持页面刷新后恢复
  } catch (err) {
    reportError(err, '启动番茄钟失败')
  } finally {
    busy.value = false
  }
}

async function completeFocus() {
  if (!session.value || !canComplete.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const response = await axios.post(
      `/api/focus/${session.value.id}/complete`,
      { rating: rating.value },
      auth(),
    )
    session.value = null
    notice.value = response.data.already_completed
      ? `学习记录 #${response.data.id} 已存在，没有重复计时`
      : `完成 ${response.data.minutes} 分钟专注，学习记录 #${response.data.id} 已保存`
    await refresh()
  } catch (err) {
    reportError(err, '提交自评失败；如未到达服务端规定时间，请稍后重试')
  } finally {
    busy.value = false
  }
}

async function abandonFocus() {
  if (!session.value || busy.value) return
  if (!window.confirm('确定放弃本次专注？放弃后不会记录学习时长。')) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await axios.post(`/api/focus/${session.value.id}/abandon`, {}, auth())
    session.value = null
    notice.value = '已放弃本次专注，未增加学习时长'
    await refresh()
  } catch (err) {
    reportError(err, '放弃专注失败')
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  refresh()
  ticker = setInterval(updateCountdown, 1000)
})
onUnmounted(() => {
  if (ticker) clearInterval(ticker)
})
</script>

<template>
  <section class="focus-panel">
    <header class="focus-heading">
      <div>
        <span class="eyebrow">FOCUS MODE</span>
        <h2>专注番茄钟</h2>
        <p>选择任务，专注当下，让每分钟都有记录。</p>
      </div>
      <button type="button" class="outline" :disabled="loading || busy" @click="refresh">刷新数据</button>
    </header>

    <div class="focus-grid">
      <div class="timer-card">
        <div
          class="timer-ring"
          :style="{ background: `conic-gradient(#5267d9 ${elapsedRatio}%, #e8edfc ${elapsedRatio}% 100%)` }"
          role="timer"
          :aria-label="`番茄钟剩余时间 ${remainingText}`"
        >
          <div class="timer-center">
            <span class="timer-subtitle">{{ hasActiveSession ? '专注剩余时间' : '准备好开始专注' }}</span>
            <strong>{{ remainingText }}</strong>
            <small>{{ hasActiveSession ? `会话 #${session.id}` : 'FOCUS TIMER' }}</small>
          </div>
        </div>

        <p class="timer-note" v-if="hasActiveSession">
          {{ remainingSeconds === 0 ? '预计时间已到，请提交效率自评' : '专注进行中，按服务端实际时间计时' }}
        </p>
        <p class="timer-note" v-else>默认25分钟，首次联调可使用1分钟测试。</p>
      </div>

      <div class="controls-card">
        <h3>{{ hasActiveSession ? '本次专注' : '开始新的专注' }}</h3>

        <label for="focus-task">学习任务</label>
        <select
          id="focus-task"
          v-model.number="taskId"
          :disabled="hasActiveSession || loading || busy"
        >
          <option :value="null" disabled>请选择任务</option>
          <option v-for="task in allowedTasks" :key="task.id" :value="task.id">
            {{ task.subject_name }} · {{ task.title }}
          </option>
        </select>
        <p v-if="!hasActiveSession && !allowedTasks.length" class="help-text">
          暂无可专注的任务，请先在上方创建任务，再点击刷新数据。
        </p>

        <label for="focus-minutes">计划专注时长</label>
        <select
          id="focus-minutes"
          v-model.number="plannedMinutes"
          :disabled="hasActiveSession || loading || busy"
        >
          <option :value="25">25分钟（正式番茄钟）</option>
          <option :value="1">1分钟（联调测试）</option>
        </select>

        <template v-if="hasActiveSession">
          <template v-if="isRunning">
            <label class="rating-label">本次学习效率自评（1～5分）</label>
            <div class="rating-row" aria-label="选择效率评分">
              <button
                v-for="score in 5"
                :key="score"
                type="button"
                :aria-pressed="rating === score"
                :class="['rating-button', { chosen: rating === score }]"
                :disabled="busy"
                @click="rating = score"
              >{{ score }}</button>
            </div>
            <button type="button" class="primary" :disabled="!canComplete" @click="completeFocus">
              {{ busy ? '正在保存...' : '完成专注并保存记录' }}
            </button>
          </template>
          <p v-else class="help-text">检测到未结束会话（{{ session.status }}）。当前版本不支持暂停恢复，可选择放弃。</p>
          <button type="button" class="outline danger" :disabled="busy" @click="abandonFocus">
            放弃本次专注
          </button>
        </template>
        <button v-else type="button" class="primary" :disabled="!taskId || busy || loading" @click="startFocus">
          {{ busy ? '正在启动...' : '开始专注' }}
        </button>
        <p class="help-text">刷新网页或重新登录后，可从数据库恢复未结束的会话。</p>
      </div>
    </div>

    <p v-if="error" class="feedback error" role="alert">{{ error }}</p>
    <p v-if="notice" class="feedback notice" role="status">{{ notice }}</p>

    <div class="history-heading">
      <h3>最近学习记录</h3>
      <span>展示最近 {{ Math.min(records.length, 5) }} 条</span>
    </div>
    <p v-if="loading">正在加载学习记录...</p>
    <div v-else-if="records.length === 0" class="empty">完成一次专注后，这里就会显示学习记录。</div>
    <div v-else class="record-list">
      <div v-for="record in records.slice(0, 5)" :key="record.id" class="record-row">
        <div>
          <strong>{{ record.subject_name }}</strong>
          <span>{{ formatTime(record.started_at) }}</span>
        </div>
        <div class="record-stats">
          <strong>{{ record.minutes }} 分钟</strong>
          <span>效率 {{ record.rating }}/5</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.focus-panel {
  margin-top: 28px;
  padding: 30px;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 8px 30px #1d37600b;
  color: #263453;
}
.focus-heading, .history-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}
.eyebrow { font-size: 12px; letter-spacing: 2px; font-weight: 750; color: #596dc7; }
h2 { margin: 10px 0 8px; font-size: 27px; }
h3 { margin-top: 0; }
.focus-heading p, .help-text, .timer-note, .history-heading span { color: #7b879f; font-size: 13px; }
.focus-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; margin-top: 26px; }
.timer-card, .controls-card { border: 1px solid #e9edf7; border-radius: 16px; padding: 26px; }
.timer-card { display: grid; justify-items: center; align-content: center; gap: 20px; background: #f8faff; }
.timer-ring {
  width: min(100%, 290px);
  aspect-ratio: 1;
  border-radius: 50%;
  padding: 14px;
  display: grid;
  place-items: center;
}
.timer-center {
  background: white;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 9px;
  text-align: center;
}
.timer-subtitle, .timer-center small { font-size: 12px; color: #8692ad; }
.timer-center strong { font-size: clamp(36px, 4vw, 54px); font-variant-numeric: tabular-nums; letter-spacing: 1px; }
.controls-card { display: flex; flex-direction: column; gap: 12px; }
.controls-card label { font-size: 14px; font-weight: 650; }
.controls-card select { width: 100%; min-height: 44px; border: 1px solid #dbe2f0; background: #fff; border-radius: 9px; color: #263453; padding: 9px; }
.primary, .outline { border-radius: 10px; padding: 12px 18px; cursor: pointer; font: inherit; }
.primary { border: 0; background: #4d63cd; color: #fff; font-weight: 700; margin-top: 5px; }
.outline { border: 1px solid #dbe2f0; color: #43547c; background: #fff; }
button:disabled, select:disabled { opacity: .58; cursor: not-allowed; }
.rating-row { display: flex; gap: 8px; }
.rating-button { flex: 1; padding: 10px; border-radius: 10px; border: 1px solid #dbe2f0; color: #475677; background: white; cursor: pointer; }
.rating-button.chosen { background: #e9edff; color: #3d55bd; border-color: #91a1ea; font-weight: 750; }
.danger { color: #c34d61; }
.feedback { padding: 12px 14px; border-radius: 9px; margin-top: 16px; }
.error { background: #fff0f1; color: #b4384b; }
.notice { background: #edf9f2; color: #176d4d; }
.history-heading { margin-top: 30px; }
.empty { padding: 25px; background: #f8faff; border-radius: 12px; color: #8a96af; }
.record-list { display: grid; gap: 9px; }
.record-row { padding: 14px 16px; border: 1px solid #edf0f6; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.record-row > div { display: grid; gap: 5px; }
.record-row span { color: #8290a9; font-size: 12px; }
.record-stats { text-align: right; }
@media (max-width: 850px) { .focus-grid { grid-template-columns: 1fr; } .focus-panel { padding: 18px; } }
@media (max-width: 500px) { .focus-heading { align-items: flex-start; flex-direction: column; } }
</style>
