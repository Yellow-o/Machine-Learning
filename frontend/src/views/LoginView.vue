<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const formRef = ref<FormInstance>()

const form = reactive({
  loginId: '',
  password: '',
})

const rules: FormRules = {
  loginId: [{ required: true, message: '请输入 UID 或手机号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function onSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    const user = await authStore.login(form.loginId, form.password)
    const redirect = String(route.query.redirect || (user.role === 'admin' ? '/dashboard' : '/events'))
    router.replace(redirect)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '登录失败')
  }
}

function goRegister() {
  router.push('/register')
}
</script>

<template>
  <main class="login-page">
    <section class="left panel fade-up">
      <h1>驾驶风险监控中心</h1>
      <p>面向车队运营、安监复核、账号权限联动的工业控制台。</p>
      <ul>
        <li>疲劳事件秒级聚合可视化</li>
        <li>复核状态闭环与申诉链路</li>
        <li>账号角色与权限统一管理</li>
      </ul>
    </section>

    <section class="right panel fade-up">
      <header>
        <h2>系统登录</h2>
        <p>使用 UID 或手机号登录</p>
      </header>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="账号" prop="loginId">
          <el-input v-model="form.loginId" placeholder="例如 admin01 或 13800138000" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password @keyup.enter="onSubmit" />
        </el-form-item>
        <div class="action-row">
          <el-button type="primary" :loading="authStore.loading" class="btn" @click="onSubmit">登录</el-button>
          <el-button class="btn btn-secondary" @click="goRegister">去注册</el-button>
        </div>
      </el-form>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  padding: clamp(16px, 3vw, 34px);
  display: grid;
  grid-template-columns: 1.2fr minmax(320px, 430px);
  gap: 16px;
}

.left,
.right {
  padding: clamp(18px, 3vw, 30px);
}

.left {
  display: grid;
  align-content: center;
  gap: 14px;
}

.left p,
.left li {
  color: var(--ink-1);
  line-height: 1.6;
}

.left ul {
  margin: 8px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

.right header p {
  margin: 6px 0 12px;
  color: var(--ink-2);
}

.btn {
  flex: 1;
  margin-top: 10px;
}

.action-row {
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr 1fr;
}

.btn-secondary {
  background: #111a2b;
  color: var(--ink-1);
  border: 1px solid var(--line-soft);
}

.btn-secondary:hover {
  color: var(--ink-0);
  border-color: var(--line-strong);
  background: #1b2f56;
}

@media (max-width: 960px) {
  .login-page {
    grid-template-columns: 1fr;
  }
}
</style>
