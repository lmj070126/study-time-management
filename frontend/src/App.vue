
<script setup>
import { ref, computed } from 'vue'
import axios from 'axios'
import StudentTasks from './components/StudentTasks.vue'
import StudentFocus from './components/StudentFocus.vue'

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')
const user = ref(null)
const accessToken = ref('')

const roleNames = {
  student: '学生',
  teacher: '班主任',
  admin: '管理员',
}

const roleName = computed(
  () => roleNames[user.value?.role] || '用户'
)

async function login() {
  if (loading.value) return

  error.value = ''
  loading.value = true

  try {
    // 真实后端账号验证
    const response = await axios.post('/api/auth/login', {
      username: username.value.trim(),
      password: password.value,
    })

    const token = response.data.access_token

    // 使用JWT读取真实用户信息
    const profile = await axios.get('/api/auth/me', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })

    accessToken.value = token
    user.value = profile.data
    password.value = ''

  } catch (err) {
    accessToken.value = ''
    user.value = null

    if (err.response?.status === 401) {
      error.value = '用户名或密码错误，请重新输入'
    } else if (err.response?.status === 422) {
      error.value = '请检查用户名和密码格式'
    } else {
      error.value = '登录失败，请确认后端服务正常运行'
    }
  } finally {
    loading.value = false
  }
}

function logout() {
  user.value = null
  accessToken.value = ''
  password.value = ''
  error.value = ''
}
</script>

<template>
  <div class="page">
    <div v-if="!user" class="login-layout">
      <section class="brand-panel">
        <div class="brand">
          <div class="brand-icon">时</div>
          <span>智学时光</span>
        </div>

        <div class="brand-content">
          <span class="eyebrow">STUDY SMARTER · GROW BETTER</span>
          <h1>让每一分钟<br />都更有价值。</h1>
          <p>
            科学规划学习任务，专注每一刻，
            用真实数据记录成长。
          </p>

          <div class="features">
            <div>✓ 个性化学习任务管理</div>
            <div>✓ 番茄钟专注时间记录</div>
            <div>✓ 多维度学习效率分析</div>
          </div>
        </div>

        <div class="brand-footer">
          学生学习时间管理与效率分析系统
        </div>
      </section>

      <main class="form-panel">
        <div class="form-content">
          <span class="welcome-label">WELCOME BACK</span>
          <h2>欢迎回来</h2>
          <p class="subtitle">登录账号，开启今天的高效学习。</p>

          <form @submit.prevent="login">
            <label for="username">用户名</label>
            <input
              id="username"
              v-model="username"
              type="text"
              placeholder="请输入用户名"
              autocomplete="username"
              maxlength="64"
              required
            />

            <label for="password">密码</label>
            <div class="password-wrap">
              <input
                id="password"
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                placeholder="请输入登录密码"
                autocomplete="current-password"
                required
              />
              <button
                type="button"
                class="toggle"
                @click="showPassword = !showPassword"
              >
                {{ showPassword ? '隐藏' : '显示' }}
              </button>
            </div>

            <p v-if="error" class="error" role="alert">
              {{ error }}
            </p>

            <button
              class="login-button"
              type="submit"
              :disabled="loading"
            >
              {{ loading ? '正在验证身份...' : '登 录' }}
            </button>
          </form>

          <div class="login-note">
            学生 · 班主任 · 管理员统一登录入口
          </div>
        </div>
      </main>
    </div>

    <div v-else class="dashboard">
      <header class="dashboard-header">
        <div class="brand dark-brand">
          <div class="brand-icon">时</div>
          <span>智学时光</span>
        </div>
        <button class="logout-button" @click="logout">
          退出登录
        </button>
      </header>

      <StudentTasks
        v-if="user.role === 'student'"
        :token="accessToken"
        @unauthorized="logout"
      />
      <StudentFocus
        v-if="user.role === 'student'"
        :token="accessToken"
        @unauthorized="logout"
      />
      <main class="dashboard-content">
        <span class="eyebrow dark-eyebrow">WELCOME</span>
        <h1>你好，{{ user.alias || user.username }}！</h1>
        <p>你的账号已经通过真实后端身份验证。</p>

        <div class="info-card">
          <h3>当前登录信息</h3>
          <div class="info-row">
            <span>用户名</span>
            <strong>{{ user.username }}</strong>
          </div>
          <div class="info-row">
            <span>身份角色</span>
            <strong>{{ roleName }}</strong>
          </div>
          <div class="info-row">
            <span>班级ID</span>
            <strong>{{ user.class_id ?? '无' }}</strong>
          </div>
          <div class="info-row">
            <span>认证状态</span>
            <strong class="success">已认证</strong>
          </div>
        </div>

        <p class="next-note">
          下一阶段将根据角色接入任务管理、
          番茄钟及学习分析功能。
        </p>
      </main>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
}

.login-layout {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1fr 1fr;
  background: #fff;
}

.brand-panel {
  min-height: 100vh;
  background: linear-gradient(145deg, #17265f, #3656b9);
  color: white;
  padding: 48px 9%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 24px;
  font-weight: 750;
}

.brand-icon {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #ffffff25;
  font-size: 24px;
}

.brand-content {
  max-width: 540px;
}

.eyebrow,
.welcome-label {
  font-size: 12px;
  letter-spacing: 2px;
  font-weight: 700;
  color: #b5c7ff;
}

.brand-content h1 {
  font-size: clamp(36px, 4vw, 59px);
  line-height: 1.25;
  margin: 22px 0;
  letter-spacing: -1.5px;
}

.brand-content p {
  font-size: 17px;
  line-height: 1.9;
  color: #d6e0ff;
}

.features {
  display: grid;
  gap: 16px;
  margin-top: 42px;
  font-size: 15px;
}

.brand-footer {
  font-size: 13px;
  color: #c1cff5;
}

.form-panel {
  display: grid;
  place-items: center;
  padding: 42px;
}

.form-content {
  width: 100%;
  max-width: 420px;
}

.welcome-label {
  color: #4f64c9;
}

.form-content h2 {
  font-size: 38px;
  margin: 16px 0 8px;
  color: #1c2850;
}

.subtitle {
  color: #8790a5;
  margin-bottom: 38px;
}

form {
  display: flex;
  flex-direction: column;
}

label {
  color: #2e3852;
  font-weight: 650;
  margin-bottom: 10px;
}

input {
  width: 100%;
  border: 1px solid #dce2ee;
  border-radius: 12px;
  padding: 15px 16px;
  font-size: 15px;
  outline: none;
  background: #fafbfe;
  color: #243050;
  margin-bottom: 23px;
}

input:focus {
  border-color: #5b73da;
  box-shadow: 0 0 0 3px #5b73da15;
}

.password-wrap {
  position: relative;
}

.password-wrap input {
  padding-right: 70px;
}

.toggle {
  position: absolute;
  right: 12px;
  top: 15px;
  background: none;
  border: 0;
  color: #566fd0;
  cursor: pointer;
}

.login-button {
  border: 0;
  border-radius: 12px;
  padding: 16px;
  background: #405cc7;
  color: white;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  margin-top: 8px;
}

.login-button:hover {
  background: #304cad;
}

.login-button:disabled {
  opacity: .65;
  cursor: not-allowed;
}

.error {
  color: #c03546;
  background: #fff1f1;
  padding: 12px;
  border-radius: 8px;
  margin: 0 0 15px;
}

.login-note {
  margin-top: 30px;
  text-align: center;
  color: #8993a8;
  font-size: 13px;
}

.dashboard {
  min-height: 100vh;
  background: #f5f7fc;
}

.dashboard-header {
  height: 84px;
  padding: 0 7%;
  background: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e9edf5;
}

.dark-brand {
  color: #243866;
}

.dark-brand .brand-icon {
  background: #405cc7;
  color: white;
}

.logout-button {
  background: white;
  border: 1px solid #dbe2ef;
  border-radius: 9px;
  padding: 10px 18px;
  cursor: pointer;
}

.dashboard-content {
  max-width: 920px;
  margin: 80px auto;
  padding: 0 24px;
}

.dark-eyebrow {
  color: #526ad2;
}

.dashboard-content h1 {
  font-size: 38px;
  color: #1d2b50;
}

.dashboard-content > p {
  color: #65738d;
}

.info-card {
  margin-top: 36px;
  background: white;
  border-radius: 18px;
  padding: 30px;
  box-shadow: 0 8px 30px #1d37600b;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 16px 0;
  border-bottom: 1px solid #edf0f6;
}

.info-row span {
  color: #77839b;
}

.success {
  color: #16865f;
}

.next-note {
  margin-top: 25px;
}

@media (max-width: 800px) {
  .login-layout {
    grid-template-columns: 1fr;
  }

  .brand-panel {
    min-height: auto;
    padding: 32px 28px;
    gap: 24px;
  }

  .brand-content h1 {
    font-size: 32px;
  }

  .features,
  .brand-footer {
    display: none;
  }

  .form-panel {
    padding: 48px 24px;
  }

  .dashboard-content {
    margin-top: 44px;
  }
}
</style>
