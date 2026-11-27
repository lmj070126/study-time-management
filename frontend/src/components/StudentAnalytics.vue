<script setup>
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'

const props = defineProps({
  token: { type: String, required: true },
})
const emit = defineEmits(['unauthorized'])
const data = ref(null)
const loading = ref(false)
const error = ref('')

const summary = computed(() => data.value?.summary ?? null)
const chartDays = computed(() => {
  const days = data.value?.daily ?? []
  const maximum = Math.max(1, ...days.map(day => day.minutes))
  return days.map(day => ({
    ...day,
    label: day.date.slice(5).replace('-', '/'),
    barHeight: day.minutes ? Math.max(5, 100 * day.minutes / maximum) : 0,
  }))
})
const subjects = computed(() => {
  const list = data.value?.subjects ?? []
  const total = Math.max(1, summary.value?.week_minutes ?? 0)
  return list.map(item => ({
    ...item,
    percentage: 100 * item.minutes / total,
  }))
})
const ratingPoints = computed(() => (data.value?.daily ?? []).map((day, index) => {
  if (day.average_rating == null) return null
  return {
    x: 62 + 90 * index,
    y: 146 - 30 * (day.average_rating - 1),
    label: day.date.slice(5),
    rating: day.average_rating,
  }
}))
const ratingSegments = computed(() => {
  const segments = []
  let points = []
  for (const point of ratingPoints.value) {
    if (point) {
      points.push(`${point.x},${point.y}`)
    } else if (points.length) {
      segments.push(points.join(' '))
      points = []
    }
  }
  if (points.length) segments.push(points.join(' '))
  return segments
})
const hasRatings = computed(() => ratingPoints.value.some(Boolean))
const advice = computed(() => {
  const s = summary.value
  if (!s || s.week_sessions === 0) {
    return '最近7天暂无已完成的专注记录。先从一次25分钟专注开始，逐步建立稳定的学习节奏。'
  }
  if (s.week_avg_rating < 3) {
    return '最近7天的效率自评偏低。建议把复杂任务拆成小步骤，专注后记录干扰因素，再比较后续变化。'
  }
  if (s.today_minutes === 0) {
    return '今天还没有已完成的专注记录。可以优先选择一项待完成任务，安排一次短时专注。'
  }
  if (s.streak_days >= 3) {
    return `你已连续学习${s.streak_days}天。建议维持适度节奏，同时关注休息与效率自评。`
  }
  return '本周已有真实学习记录。可以查看各科目时间占比，优先安排投入不足且仍有待办任务的科目。'
})
function formatMinutes(minutes) {
  if (minutes == null) return '—'
  if (minutes < 60) return `${minutes} 分钟`
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分钟`
}
async function refreshAnalytics() {
  if (loading.value || !props.token) return
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get('/api/analytics/overview', {
      headers: { Authorization: `Bearer ${props.token}` },
    })
    data.value = response.data
  } catch (err) {
    if (err.response?.status === 401) {
      emit('unauthorized')
      return
    }
    if (err.response?.status === 403) {
      error.value = '此页面仅对学生账号开放。'
    } else {
      error.value = '无法获取学习分析，请确认 FastAPI 服务及数据库连接正常。'
    }
  } finally {
    loading.value = false
  }
}
onMounted(refreshAnalytics)
</script>

<template>
  <section class="analytics">
    <header class="analytics-header">
      <div>
        <span class="eyebrow">LEARNING INSIGHTS</span>
        <h2>我的学习数据</h2>
        <p>依据真实学习记录生成，统计范围为最近7个自然日（含今天）。</p>
      </div>
      <button class="refresh" :disabled="loading" @click="refreshAnalytics">
        {{ loading ? '加载中...' : '刷新统计' }}
      </button>
    </header>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="loading && !data" class="loading" role="status">正在读取真实学习数据...</p>

    <template v-if="data && summary">
      <p class="period">
        {{ data.period.start_date }} 至 {{ data.period.end_date }}
        <span>（{{ data.period.timezone }}）</span>
      </p>
      <div class="metric-grid">
        <div class="metric-card">
          <span class="metric-icon">◷</span>
          <span class="metric-label">今日专注时长</span>
          <strong>{{ formatMinutes(summary.today_minutes) }}</strong>
          <small>仅计入已完成的专注</small>
        </div>
        <div class="metric-card">
          <span class="metric-icon">◈</span>
          <span class="metric-label">近7天学习时长</span>
          <strong>{{ formatMinutes(summary.week_minutes) }}</strong>
          <small>共 {{ summary.week_sessions }} 次专注</small>
        </div>
        <div class="metric-card">
          <span class="metric-icon">✦</span>
          <span class="metric-label">平均效率自评</span>
          <strong>{{ summary.week_avg_rating == null ? '—' : `${summary.week_avg_rating} / 5` }}</strong>
          <small>每次专注等权计算</small>
        </div>
        <div class="metric-card">
          <span class="metric-icon">↗</span>
          <span class="metric-label">连续学习天数</span>
          <strong>{{ summary.streak_days }} 天</strong>
          <small>按有专注记录的自然日计算</small>
        </div>
      </div>

      <div class="chart-grid">
        <article class="chart-panel">
          <div class="panel-heading">
            <h3>七日学习时长</h3>
            <span>单位：分钟</span>
          </div>
          <div class="bar-chart" role="img" aria-label="最近7天每日已完成专注时长柱状图">
            <div v-for="day in chartDays" :key="day.date" class="bar-column">
              <div class="bar-track">
                <div class="bar" :style="{ height: `${day.barHeight}%` }" :title="`${day.date}：${day.minutes}分钟`"></div>
              </div>
              <strong>{{ day.minutes }}</strong>
              <span>{{ day.label }}</span>
            </div>
          </div>
          <p class="chart-hint">按专注开始时所属的 UTC+8 自然日归档。</p>
        </article>

        <article class="chart-panel">
          <div class="panel-heading">
            <h3>科目时间分布</h3>
            <span>近7天</span>
          </div>
          <div v-if="subjects.length" class="subjects">
            <div v-for="subject in subjects" :key="subject.subject_id" class="subject-row">
              <div class="subject-labels">
                <strong>{{ subject.subject_name }}</strong>
                <span>{{ subject.minutes }} 分钟 · {{ subject.sessions }} 次</span>
              </div>
              <div class="subject-track">
                <div class="subject-fill" :style="{ width: `${subject.percentage}%` }"></div>
              </div>
            </div>
          </div>
          <div v-else class="empty">本周暂无科目学习记录</div>
        </article>

        <article class="chart-panel">
          <div class="panel-heading">
            <h3>效率自评趋势</h3>
            <span>1–5 分</span>
          </div>
          <div v-if="hasRatings">
            <svg class="rating-chart" viewBox="0 0 660 182" role="img" aria-label="过去七天有记录日期的平均自评趋势折线图">
              <g v-for="tick in [1, 2, 3, 4, 5]" :key="tick">
                <line x1="55" x2="612" :y1="146 - (tick - 1) * 30" :y2="146 - (tick - 1) * 30" stroke="#e7edf8" stroke-width="1"/>
                <text x="30" :y="150 - (tick - 1) * 30" fill="#8a94a9" font-size="13">{{ tick }}</text>
              </g>
              <polyline v-for="(line, index) in ratingSegments" :key="index" :points="line" fill="none" stroke="#5269d0" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
              <template v-for="(point, index) in ratingPoints" :key="index">
                <circle v-if="point" :cx="point.x" :cy="point.y" r="6" fill="#5269d0" stroke="white" stroke-width="2">
                  <title>{{ point.label }}：{{ point.rating }} 分</title>
                </circle>
              </template>
            </svg>
            <div class="rating-dates"><span v-for="day in chartDays" :key="day.date">{{ day.label }}</span></div>
          </div>
          <div v-else class="empty">本周暂无效率评分记录</div>
          <p class="chart-hint">无记录日期不补零分，也不跨缺失日期连线。</p>
        </article>

        <article class="chart-panel completion-panel">
          <div class="panel-heading">
            <h3>任务完成率</h3>
            <span>当前有效任务</span>
          </div>
          <div class="completion-value">{{ summary.task_completion_rate }}<small>%</small></div>
          <div class="completion-track">
            <div :style="{ width: `${summary.task_completion_rate}%` }"></div>
          </div>
          <p>已完成 {{ summary.task_done }} / {{ summary.task_total }} 项任务</p>
          <small>取消的任务不计入分母；任务完成不等于专注时间。</small>
        </article>
      </div>

      <section class="insight">
        <div class="insight-icon">✧</div>
        <div>
          <h3>学习建议</h3>
          <p>{{ advice }}</p>
          <small>基于本周指标的透明规则建议，不代表 AI 预测或医学评估。</small>
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
.analytics{margin:32px auto;max-width:1400px;padding:32px;border:1px solid #e7ebf4;border-radius:22px;background:white;color:#233354;box-shadow:0 12px 45px #1526500b}
.analytics-header{display:flex;justify-content:space-between;align-items:center;gap:16px}
.eyebrow{font-size:11px;letter-spacing:2.5px;font-weight:800;color:#5269cb}
.analytics-header h2{margin:8px 0 10px;font-size:28px;color:#1f2c51}
.analytics-header p{margin:0;color:#8994ab;font-size:14px}
.refresh{flex-shrink:0;padding:10px 16px;border:1px solid #dde4f2;background:white;border-radius:10px;color:#485b81;cursor:pointer}
.refresh:disabled{opacity:.5;cursor:wait}
.error{padding:12px 15px;border-radius:10px;background:#fff1f1;color:#9e3249}
.loading{color:#687893;padding:28px 0}
.period{color:#8591a9;font-size:12px;margin:23px 0 17px}
.period span{color:#a4aec0}
.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.metric-card{border-radius:16px;padding:22px;background:linear-gradient(155deg,#f8faff,#f0f4ff);border:1px solid #e9eefb;display:flex;flex-direction:column;gap:10px}
.metric-card:nth-child(2){background:linear-gradient(155deg,#f4f9ff,#ebf5ff)}
.metric-card:nth-child(3){background:linear-gradient(155deg,#fcfaff,#f4edff)}
.metric-card:nth-child(4){background:linear-gradient(155deg,#f3fdfa,#eaf8f4)}
.metric-icon{font-size:21px;color:#536bcc}
.metric-label{font-size:13px;color:#66748f}
.metric-card strong{font-size:25px;font-weight:800;letter-spacing:-.5px;white-space:nowrap}
.metric-card small{font-size:12px;color:#8591aa}
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:20px}
.chart-panel{padding:23px;border:1px solid #e8edf5;border-radius:16px;min-width:0}
.panel-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}
.panel-heading h3{font-size:17px;margin:0;color:#233354}
.panel-heading>span{font-size:12px;color:#8995ae}
.bar-chart{margin-top:26px;height:224px;display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:12px;align-items:end}
.bar-column{display:flex;flex-direction:column;align-items:center;gap:6px;height:100%;min-width:0;color:#73809a;font-size:12px}
.bar-track{height:175px;width:100%;display:flex;align-items:flex-end;justify-content:center;border-bottom:1px solid #e0e7f3}
.bar{width:min(36px,85%);border-radius:8px 8px 0 0;background:linear-gradient(#7c8fea,#4964ce);transition:height .25s ease}
.bar-column strong{font-size:12px;color:#33456e;font-weight:700}
.bar-column span{white-space:nowrap;font-size:11px}
.chart-hint{font-size:11px;color:#9ba5b9;margin:16px 0 0}
.subjects{display:grid;gap:23px;margin-top:30px}
.subject-labels{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px;font-size:13px}
.subject-labels span{font-size:12px;color:#8995ab}
.subject-track,.completion-track{width:100%;height:10px;background:#edf1fa;border-radius:999px;overflow:hidden}
.subject-fill,.completion-track>div{height:100%;background:linear-gradient(90deg,#526bd1,#899af1);border-radius:999px}
.empty{padding:48px 10px;text-align:center;color:#96a0b3;font-size:13px}
.rating-chart{width:100%;height:auto;display:block;margin-top:14px}
.rating-dates{display:grid;grid-template-columns:repeat(7,1fr);text-align:center;color:#94a0b5;font-size:10px;padding:0 4% 0 6%}
.completion-value{font-size:58px;font-weight:800;color:#425fc6;margin:28px 0 16px;letter-spacing:-2px}
.completion-value small{font-size:24px;letter-spacing:0}
.completion-panel p{margin:17px 0 9px;font-size:14px;color:#5e6c89}
.completion-panel>small{color:#94a0b7;font-size:12px}
.insight{display:flex;gap:18px;margin-top:20px;padding:22px;border:1px solid #e1e9ff;background:linear-gradient(100deg,#f3f6ff,#f9fbff);border-radius:16px}
.insight-icon{font-size:24px;color:#526bd1}
.insight h3{margin:0 0 9px;font-size:16px}
.insight p{margin:0 0 10px;color:#405173;line-height:1.75;font-size:14px}
.insight small{font-size:11px;color:#9aa6bc}
@media(max-width:1000px){.metric-grid{grid-template-columns:repeat(2,1fr)}.chart-grid{grid-template-columns:1fr}}
@media(max-width:600px){.analytics{padding:18px;margin:16px auto}.analytics-header{align-items:flex-start}.analytics-header h2{font-size:23px}.metric-grid{gap:10px}.metric-card{padding:16px}.metric-card strong{font-size:20px}.chart-panel{padding:16px}.bar-chart{gap:5px}.subject-labels{flex-wrap:wrap}}
</style>
