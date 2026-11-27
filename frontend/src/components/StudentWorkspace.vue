<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import axios from 'axios'
import StudentTasks from './StudentTasks.vue'
import StudentFocus from './StudentFocus.vue'
import StudentAnalytics from './StudentAnalytics.vue'

const props = defineProps({
  user: { type: Object, required: true },
  token: { type: String, required: true },
})
const emit = defineEmits(['logout', 'unauthorized'])

const pages = [
  { id: 'overview', label: '学习总览', glyph: '▦', desc: '掌握每天的学习节奏' },
  { id: 'tasks', label: '学习任务', glyph: '☷', desc: '规划与跟踪学习计划' },
  { id: 'focus', label: '专注番茄钟', glyph: '◷', desc: '专注当下，积累时间' },
  { id: 'analytics', label: '学习分析', glyph: '◈', desc: '用真实数据看见成长' },
]
const activeView = ref('overview')
const mobileMenuOpen = ref(false)
const overview = ref(null)
const loading = ref(false)
const summaryError = ref('')

const activePage = computed(() => pages.find(p => p.id === activeView.value) || pages[0])
const alias = computed(() => props.user.alias || props.user.username || '同学')
const summary = computed(() => overview.value?.summary ?? null)
const daily = computed(() => overview.value?.daily ?? [])
const chartDays = computed(() => {
  const max = Math.max(1, ...daily.value.map(d => Number(d.minutes) || 0))
  return daily.value.map(d => ({
    ...d,
    shortDate: d.date?.slice(5).replace('-', '/') ?? '',
    height: d.minutes ? Math.max(6, Math.round(100 * d.minutes / max)) : 0,
  }))
})
const completionRate = computed(() => summary.value?.task_completion_rate ?? 0)
const completedCircle = computed(() => 276.46 * (1 - completionRate.value / 100))
const nowLabel = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
}).format(new Date())

const cards = computed(() => {
  const s = summary.value
  return [
    { title: '今日专注', value: s ? `${s.today_minutes}` : '—', unit: '分钟', caption: '仅统计已完成的专注', icon: '◷', tone: 'blue' },
    { title: '近7天累计', value: s ? `${s.week_minutes}` : '—', unit: '分钟', caption: '最近7个自然日', icon: '▦', tone: 'purple' },
    { title: '本周专注次数', value: s ? `${s.week_sessions}` : '—', unit: '次', caption: '来自真实学习记录', icon: '◎', tone: 'mint' },
    { title: '平均效率自评', value: s ? (s.week_avg_rating == null ? '—' : `${s.week_avg_rating}`) : '—', unit: '/ 5', caption: '每次完成专注等权计算', icon: '✧', tone: 'amber' },
  ]
})
const insight = computed(() => {
  const s = summary.value
  if (!s) return '数据加载后，将根据你的真实学习记录提供可解释的建议。'
  if (s.week_sessions === 0) return '近7天还没有已完成的专注记录。可以从一项小任务开始，完成一次专注。'
  if (s.week_avg_rating != null && s.week_avg_rating < 3) return '近期效率自评偏低。试着拆分任务、减少干扰，再观察下一周的变化。'
  if (s.today_minutes === 0) return '今天尚无完成的专注记录。选择一项待办任务，安排一段学习时间吧。'
  if (s.streak_days >= 3) return `已经连续学习 ${s.streak_days} 天。保持节奏，也记得安排休息。`
  return '本周已积累真实学习记录。查看科目分布，结合待办任务安排下一次学习。'
})

function viewFromHash() {
  const match = window.location.hash.match(/^#\/student\/(overview|tasks|focus|analytics)$/)
  return match?.[1] || 'overview'
}
function onHashChange() {
  activeView.value = viewFromHash()
  mobileMenuOpen.value = false
  if (activeView.value === 'overview') refreshOverview()
}
function navigate(view) {
  if (!pages.some(p => p.id === view)) return
  mobileMenuOpen.value = false
  if (viewFromHash() === view && window.location.hash === `#/student/${view}`) {
    activeView.value = view
    if (view === 'overview') refreshOverview()
    return
  }
  window.location.hash = `/student/${view}`
}
async function refreshOverview() {
  if (loading.value || !props.token) return
  loading.value = true
  summaryError.value = ''
  try {
    const response = await axios.get('/api/analytics/overview', {
      headers: { Authorization: `Bearer ${props.token}` },
    })
    overview.value = response.data
  } catch (err) {
    if (err.response?.status === 401) {
      emit('unauthorized')
      return
    }
    summaryError.value = err.response?.status === 403
      ? '此功能仅限学生账号使用。'
      : '暂时无法获取学习数据，请检查后端连接后重试。'
  } finally {
    loading.value = false
  }
}
function logout() {
  mobileMenuOpen.value = false
  emit('logout')
}
onMounted(() => {
  if (!/^#\/student\/(overview|tasks|focus|analytics)$/.test(window.location.hash)) {
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#/student/overview`)
  }
  activeView.value = viewFromHash()
  window.addEventListener('hashchange', onHashChange)
  if (activeView.value === 'overview') refreshOverview()
})
onUnmounted(() => window.removeEventListener('hashchange', onHashChange))
</script>

<template>
  <div class="workbench">
    <button v-if="mobileMenuOpen" class="menu-backdrop" type="button" aria-label="关闭菜单" @click="mobileMenuOpen = false"></button>
    <aside id="student-nav" class="sidebar" :class="{ open: mobileMenuOpen }" aria-label="学生工作台导航">
      <div class="brand-wrap">
        <div class="brand-logo" aria-hidden="true">时</div>
        <div><div class="brand-title">智学时光</div><div class="brand-subtitle">STUDY COMPANION</div></div>
      </div>
      <div class="nav-section-title">主菜单</div>
      <nav class="nav-list" aria-label="功能页面">
        <button v-for="page in pages" :key="page.id" type="button" class="nav-item"
          :class="{ selected: activeView === page.id }" :aria-current="activeView === page.id ? 'page' : undefined"
          @click="navigate(page.id)">
          <span class="nav-icon" aria-hidden="true">{{ page.glyph }}</span>
          <span class="nav-copy"><strong>{{ page.label }}</strong><small>{{ page.desc }}</small></span>
          <span v-if="activeView === page.id" class="nav-dot" aria-hidden="true"></span>
        </button>
      </nav>
      <div class="sidebar-tip"><span aria-hidden="true">✦</span><strong>学习小贴士</strong><p>计划要适量，专注和休息同样重要。</p></div>
      <div class="sidebar-profile">
        <div class="avatar" aria-hidden="true">{{ alias.slice(0, 1) }}</div>
        <div class="profile-copy"><strong :title="alias">{{ alias }}</strong><small>学生账号 · 已认证</small></div>
        <button type="button" class="exit-icon" title="退出登录" aria-label="退出登录" @click="logout">⇥</button>
      </div>
    </aside>

    <div class="main-column">
      <header class="topbar">
        <div class="topbar-left">
          <button class="mobile-menu-button" type="button" aria-label="打开导航菜单" aria-controls="student-nav" :aria-expanded="mobileMenuOpen" @click="mobileMenuOpen = !mobileMenuOpen">☰</button>
          <span class="breadcrumb">学生工作台</span><span class="crumb-separator">/</span><strong>{{ activePage.label }}</strong>
        </div>
        <div class="topbar-right"><span class="today-label">{{ nowLabel }}</span><span class="user-pill">{{ alias }}</span></div>
      </header>

      <main class="content" :aria-label="activePage.label">
        <template v-if="activeView === 'overview'">
          <section class="hero">
            <div class="hero-body">
              <div class="hero-eyebrow"><span class="hero-light"></span> 让每一分钟都更有价值</div>
              <h1>你好，{{ alias }}！<br><span>今天也一起向目标前进。</span></h1>
              <p>计划学习任务，专注当下，并用真实数据记录每一步成长。</p>
              <div class="hero-actions">
                <button type="button" class="hero-primary" @click="navigate('focus')">开始专注 <span aria-hidden="true">↗</span></button>
                <button type="button" class="hero-secondary" @click="navigate('tasks')">查看任务</button>
              </div>
            </div>
            <div class="hero-progress" role="img" :aria-label="summary ? `任务完成率 ${summary.task_completion_rate}%` : '正在加载任务完成率'">
              <svg viewBox="0 0 120 120" aria-hidden="true">
                <circle cx="60" cy="60" r="44" class="progress-track" />
                <circle cx="60" cy="60" r="44" class="progress-value" :stroke-dashoffset="completedCircle" />
              </svg>
              <div class="hero-progress-text"><strong>{{ summary ? `${summary.task_completion_rate}%` : '—' }}</strong><span>任务完成率</span></div>
            </div>
          </section>

          <div class="section-heading"><div><h2>学习概览</h2><p>来自你已完成的真实专注记录</p></div><button class="text-action" type="button" :disabled="loading" @click="refreshOverview">{{ loading ? '加载中…' : '↻ 刷新数据' }}</button></div>
          <p v-if="summaryError" class="error-box" role="alert">{{ summaryError }}</p>
          <div class="kpi-grid">
            <article v-for="card in cards" :key="card.title" class="kpi" :class="`kpi-${card.tone}`">
              <div class="kpi-top"><span class="kpi-icon" aria-hidden="true">{{ card.icon }}</span><span class="kpi-category">近况</span></div>
              <p>{{ card.title }}</p><div class="kpi-number">{{ card.value }} <small>{{ card.unit }}</small></div>
              <span class="kpi-caption">{{ card.caption }}</span>
            </article>
          </div>

          <div class="overview-grid">
            <section class="surface-card trend-panel">
              <div class="card-heading"><div><h2>最近7天学习趋势</h2><p>按 UTC+8 自然日统计 · 分钟</p></div><button type="button" class="text-action" @click="navigate('analytics')">完整分析 ↗</button></div>
              <div v-if="chartDays.length" class="mini-chart" role="img" aria-label="最近七天完成的专注分钟数柱状图">
                <div v-for="day in chartDays" :key="day.date" class="mini-column" :title="`${day.date}：${day.minutes}分钟`">
                  <div class="mini-track"><div class="mini-bar" :style="{ height: `${day.height}%` }"></div></div>
                  <strong>{{ day.minutes }}</strong><span>{{ day.shortDate }}</span>
                </div>
              </div>
              <div v-else class="mini-empty">{{ loading ? '正在读取趋势数据…' : '暂时没有可展示的数据' }}</div>
            </section>
            <section class="surface-card insight-panel">
              <div class="card-heading"><div><h2>学习建议</h2><p>根据近7天指标给出透明建议</p></div><span class="insight-mark" aria-hidden="true">✧</span></div>
              <div class="insight-inner"><div class="insight-symbol" aria-hidden="true">✦</div><p>{{ insight }}</p></div>
              <div class="insight-footer">规则生成建议，仅供学习规划参考</div>
              <div class="streak-pill">连续学习 <strong>{{ summary?.streak_days ?? '—' }}</strong> 天</div>
            </section>
          </div>

          <div class="section-heading last-heading"><div><h2>快捷开始</h2><p>选择下一步，保持学习节奏</p></div></div>
          <div class="shortcut-grid">
            <button type="button" class="shortcut" @click="navigate('tasks')"><span class="shortcut-symbol navy">☷</span><span><strong>管理学习任务</strong><small>创建计划、更新进度</small></span><b aria-hidden="true">↗</b></button>
            <button type="button" class="shortcut" @click="navigate('focus')"><span class="shortcut-symbol lilac">◷</span><span><strong>开启番茄钟</strong><small>专注计时与效率自评</small></span><b aria-hidden="true">↗</b></button>
            <button type="button" class="shortcut" @click="navigate('analytics')"><span class="shortcut-symbol sea">◈</span><span><strong>查看学习分析</strong><small>时长、科目和效率趋势</small></span><b aria-hidden="true">↗</b></button>
          </div>
        </template>
        <template v-else>
          <div class="page-intro"><div><span class="page-eyebrow">STUDY WORKSPACE</span><h1>{{ activePage.label }}</h1><p>{{ activePage.desc }}</p></div><button type="button" class="back-home" @click="navigate('overview')">← 返回总览</button></div>
          <div class="embedded-area">
            <StudentTasks v-if="activeView === 'tasks'" :token="token" @unauthorized="emit('unauthorized')" />
            <StudentFocus v-else-if="activeView === 'focus'" :token="token" @unauthorized="emit('unauthorized')" />
            <StudentAnalytics v-else-if="activeView === 'analytics'" :token="token" @unauthorized="emit('unauthorized')" />
          </div>
        </template>
        <footer class="page-footer">智学时光 · 学生学习时间管理与效率分析系统</footer>
      </main>
    </div>
  </div>
</template>

<style scoped>
.workbench{min-height:100vh;display:grid;grid-template-columns:258px minmax(0,1fr);background:#f5f7fc;color:#253453;font-family:Inter,'Microsoft YaHei','PingFang SC',sans-serif}
button{font:inherit;cursor:pointer}button:disabled{opacity:.65;cursor:not-allowed}
.sidebar{height:100vh;position:sticky;top:0;display:flex;flex-direction:column;padding:27px 16px 18px;background:#17244c;color:white;z-index:30}
.brand-wrap{display:flex;align-items:center;gap:12px;padding:3px 11px 39px}.brand-logo{width:43px;height:43px;border-radius:13px;display:grid;place-items:center;color:white;font-size:24px;font-weight:800;background:linear-gradient(135deg,#637cf1,#7a92fc);box-shadow:0 6px 20px #6f85e052}
.brand-title{font-size:19px;font-weight:800;letter-spacing:.4px}.brand-subtitle{font-size:9px;letter-spacing:1.3px;margin-top:4px;color:#a8b7de}
.nav-section-title{padding:0 17px 13px;color:#7f91c0;font-size:11px;font-weight:700;letter-spacing:2px}.nav-list{display:grid;gap:7px}
.nav-item{display:flex;align-items:center;width:100%;gap:13px;border:1px solid transparent;border-radius:12px;text-align:left;padding:12px 12px;background:transparent;color:#bfcbea;transition:background .18s,color .18s}
.nav-item:hover{background:#ffffff0e;color:white}.nav-item.selected{background:#5066cd;color:#fff;box-shadow:0 7px 18px #0d17435a}.nav-icon{font-size:22px;line-height:1;min-width:28px;text-align:center}.nav-copy{display:grid;gap:3px;flex:1}.nav-copy strong{font-size:13px;font-weight:700}.nav-copy small{font-size:10px;opacity:.7}.nav-dot{height:6px;width:6px;border-radius:50%;background:white}
.sidebar-tip{margin:auto 5px 20px;padding:17px;background:#ffffff0c;border:1px solid #ffffff15;border-radius:13px;color:#cfdaf7}.sidebar-tip>span{color:#a9bafd;font-size:21px;display:inline-block;margin-right:8px}.sidebar-tip strong{font-size:12px}.sidebar-tip p{font-size:11px;line-height:1.75;color:#a7b7db;margin:10px 0 0}
.sidebar-profile{display:flex;align-items:center;gap:10px;padding:16px 7px 4px;border-top:1px solid #ffffff24}.avatar{width:37px;height:37px;flex:none;border-radius:12px;background:#5268c8;display:grid;place-items:center;font-weight:700}.profile-copy{display:grid;gap:4px;flex:1;min-width:0}.profile-copy strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}.profile-copy small{font-size:10px;color:#a2b4da}.exit-icon{border:0;color:#afbee3;background:transparent;font-size:25px;padding:4px}
.main-column{min-width:0}.topbar{height:75px;padding:0 clamp(20px,3vw,46px);display:flex;align-items:center;justify-content:space-between;gap:16px;background:#fff;border-bottom:1px solid #e8ecf4;position:sticky;top:0;z-index:10}.topbar-left,.topbar-right{display:flex;gap:13px;align-items:center;min-width:0;font-size:13px}.breadcrumb,.crumb-separator,.today-label{color:#8a96ad}.topbar-left strong{font-size:13px;color:#2c3b5e}.user-pill{border:1px solid #e3e8f2;border-radius:99px;padding:8px 12px;font-size:12px;font-weight:650;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mobile-menu-button{display:none;border:0;background:#eef2ff;color:#445cba;padding:7px 10px;border-radius:9px}.content{max-width:1510px;margin:0 auto;padding:28px clamp(18px,3vw,45px) 40px;min-width:0}
.hero{min-height:245px;border-radius:22px;display:flex;align-items:center;justify-content:space-between;gap:24px;padding:32px clamp(24px,4vw,52px);background:linear-gradient(110deg,#25386f 0%,#455dc4 64%,#6277dc 100%);color:white;overflow:hidden;position:relative;box-shadow:0 15px 38px #243d971d}
.hero:before,.hero:after{content:"";position:absolute;border:1px solid #ffffff22;border-radius:50%;pointer-events:none}.hero:before{width:350px;height:350px;right:-95px;top:-210px}.hero:after{width:260px;height:260px;right:70px;bottom:-202px}.hero-body{position:relative;z-index:1}.hero-eyebrow{font-size:11px;letter-spacing:1.5px;font-weight:700;color:#d7e0ff}.hero-light{display:inline-block;width:7px;height:7px;border-radius:50%;background:#a4f3c8;margin-right:5px}.hero h1{font-size:clamp(23px,2.25vw,33px);line-height:1.5;letter-spacing:-.6px;margin:14px 0 9px}.hero h1 span{font-weight:600;color:#edf1ff}.hero p{font-size:12px;color:#d7e0fb;margin:0;line-height:1.7}.hero-actions{display:flex;gap:10px;margin-top:25px;flex-wrap:wrap}.hero-actions button{border-radius:10px;padding:11px 19px;font-size:12px;font-weight:750}.hero-primary{background:white;color:#334baa;border:0}.hero-primary span{margin-left:7px}.hero-secondary{color:white;background:#ffffff17;border:1px solid #ffffff56}
.hero-progress{position:relative;width:168px;height:168px;flex:none;z-index:1}.hero-progress svg{width:100%;height:100%;transform:rotate(-90deg)}.progress-track,.progress-value{fill:none;stroke-width:8}.progress-track{stroke:#ffffff42}.progress-value{stroke:#b7f2e5;stroke-linecap:round;stroke-dasharray:276.46;transition:stroke-dashoffset .5s ease}.hero-progress-text{position:absolute;inset:0;display:grid;align-content:center;text-align:center;gap:5px}.hero-progress-text strong{font-size:30px}.hero-progress-text span{font-size:11px;color:#e5ecff}
.section-heading{display:flex;justify-content:space-between;align-items:center;gap:14px;margin:30px 0 18px}.section-heading h2,.card-heading h2{font-size:17px;margin:0 0 6px;color:#263654}.section-heading p,.card-heading p{font-size:12px;margin:0;color:#92a0b7}.text-action{background:transparent;border:0;font-size:12px;font-weight:700;color:#5168c4;white-space:nowrap;padding:7px}
.kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:15px}.kpi{padding:20px;border-radius:15px;border:1px solid #e5ebf5;background:white;min-width:0;box-shadow:0 7px 20px #233b6810}.kpi-top{display:flex;justify-content:space-between;align-items:center}.kpi-icon{width:37px;height:37px;border-radius:11px;display:grid;place-items:center;font-size:21px}.kpi-category{font-size:10px;color:#a4b0c1}.kpi p{margin:17px 0 6px;color:#6f7e97;font-size:12px}.kpi-number{font-size:29px;color:#24345d;font-weight:800;font-variant-numeric:tabular-nums;white-space:nowrap;letter-spacing:-1px}.kpi-number small{font-size:12px;color:#8e9bb1;font-weight:500;letter-spacing:0}.kpi-caption{display:block;color:#a0abc0;font-size:11px;margin-top:8px}.kpi-blue .kpi-icon{background:#eff3ff;color:#5873cf}.kpi-purple .kpi-icon{background:#f4efff;color:#8871d1}.kpi-mint .kpi-icon{background:#eaf8f3;color:#319f78}.kpi-amber .kpi-icon{background:#fff5e7;color:#d8a14d}
.overview-grid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(285px,1fr);gap:17px;margin-top:17px}.surface-card{border:1px solid #e7edf5;border-radius:16px;background:white;padding:23px;min-width:0;box-shadow:0 7px 22px #233b680c}.card-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.mini-chart{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:9px;height:207px;margin-top:26px}.mini-column{display:grid;grid-template-rows:minmax(0,1fr) auto auto;justify-items:center;gap:5px;min-width:0;font-size:11px;color:#8c9bb1}.mini-column strong{font-size:11px;color:#465978}.mini-track{width:100%;height:100%;border-bottom:1px solid #e5eaf3;display:flex;align-items:flex-end;justify-content:center}.mini-bar{width:min(34px,75%);background:linear-gradient(#a0adf6,#586ecb);border-radius:7px 7px 0 0;transition:height .25s}.mini-empty{height:180px;display:grid;place-items:center;color:#a0aabe;font-size:12px}.insight-mark{font-size:26px;color:#5c72ce}.insight-inner{display:flex;align-items:flex-start;gap:13px;margin-top:28px;padding:18px;background:#f5f7ff;border-radius:13px}.insight-symbol{background:#e7edff;color:#5870cf;padding:11px;border-radius:11px}.insight-inner p{margin:0;color:#596983;line-height:1.85;font-size:12px}.insight-footer{color:#a0aabd;font-size:10px;margin-top:15px}.streak-pill{display:inline-flex;align-items:center;gap:5px;margin-top:17px;background:#eaf7f2;color:#277957;border-radius:99px;padding:8px 12px;font-size:11px}.last-heading{margin-top:30px}.shortcut-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.shortcut{display:flex;gap:13px;align-items:center;min-width:0;padding:18px;border:1px solid #e7edf5;border-radius:15px;text-align:left;background:#fff;color:#28395d}.shortcut:hover{border-color:#bcc8ef;box-shadow:0 7px 20px #273d7018}.shortcut-symbol{height:43px;width:43px;display:grid;place-items:center;border-radius:12px;flex:none;font-size:24px}.shortcut-symbol.navy{background:#edf1ff;color:#5a70cb}.shortcut-symbol.lilac{background:#f2edff;color:#8568cb}.shortcut-symbol.sea{background:#eaf8f4;color:#3f9a8e}.shortcut>span:nth-child(2){display:grid;gap:5px;min-width:0}.shortcut strong{font-size:12px}.shortcut small{font-size:10px;color:#95a1b6}.shortcut b{margin-left:auto;color:#8495ba;font-size:15px}.page-footer{margin-top:42px;text-align:center;color:#a1adc0;font-size:11px}
.error-box{padding:12px;border-radius:10px;background:#fff0f1;color:#ab3d53;font-size:12px}
.page-intro{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:22px}.page-intro h1{font-size:27px;margin:8px 0;color:#253555}.page-intro p{font-size:12px;color:#90a0b7;margin:0}.page-eyebrow{font-size:10px;letter-spacing:2px;color:#6277d0;font-weight:800}.back-home{border:1px solid #dfe5f1;background:#fff;color:#566a95;border-radius:10px;padding:10px 14px;font-size:12px;white-space:nowrap}.embedded-area{min-width:0}.embedded-area :deep(.tasks-panel),.embedded-area :deep(.focus-panel),.embedded-area :deep(.analytics){max-width:none;margin:0;box-shadow:0 8px 25px #233b680a}
.menu-backdrop{display:none}
@media(max-width:1190px){.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.overview-grid{grid-template-columns:1fr}.hero-progress{width:145px;height:145px}}
@media(max-width:860px){.workbench{display:block}.sidebar{width:258px;position:fixed;top:0;left:0;bottom:0;transform:translateX(-110%);transition:transform .2s}.sidebar.open{transform:translateX(0)}.menu-backdrop{display:block;position:fixed;inset:0;background:#0e183d80;border:0;width:100vw;height:100vh;z-index:20}.mobile-menu-button{display:inline-block}.today-label{display:none}.topbar{height:65px}.content{padding:22px 18px}.sidebar-tip{margin-top:auto}}
@media(max-width:620px){.hero{padding:26px 21px}.hero-progress{display:none}.hero h1{font-size:23px}.kpi-grid{gap:10px}.kpi{padding:16px}.kpi-number{font-size:24px}.shortcut-grid{grid-template-columns:1fr}.overview-grid{gap:12px}.surface-card{padding:16px}.mini-chart{gap:5px}.page-intro{align-items:flex-start}.back-home{padding:8px}.user-pill{max-width:100px}.embedded-area :deep(.focus-panel),.embedded-area :deep(.tasks-panel),.embedded-area :deep(.analytics){padding:18px}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{transition:none!important}}
</style>
