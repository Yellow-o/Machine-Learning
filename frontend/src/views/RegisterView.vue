<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const formRef = ref<FormInstance>()

const form = reactive({
  username: '',
  fullName: '',
  phone: '',
  idCard: '',
  password: '',
  confirmPassword: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入账号', trigger: 'blur' },
    { min: 4, max: 32, message: '账号长度需为 4-32 位', trigger: 'blur' },
  ],
  fullName: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1\d{10}$/, message: '请输入 11 位手机号', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== form.password) {
          callback(new Error('两次输入的密码不一致'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

async function onSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    const user = await authStore.register({
      username: form.username.trim(),
      password: form.password,
      full_name: form.fullName.trim(),
      phone: form.phone.trim(),
      id_card: form.idCard.trim() || undefined,
    })
    ElMessage.success('注册成功，已自动登录')
    router.replace(user.role === 'admin' ? '/dashboard' : '/events')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '注册失败')
  }
}

function goLogin() {
  router.push('/login')
}
</script>

<template>
  <main class="register-page">
    <section class="left panel fade-up">
      <h1>账号注册</h1>
      <p>统一账号体系：注册后可在 Web 端和 GUI 端共用同一账号。</p>
      <ul>
        <li>默认注册为驾驶员账号</li>
        <li>管理员账号由系统管理员在后台创建</li>
        <li>手机号可用于登录与事件归属</li>
      </ul>
    </section>

    <section class="right panel fade-up">
      <header>
        <h2>创建驾驶员账号</h2>
        <p>填写信息后自动登录并进入系统</p>
      </header>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="账号" prop="username">
          <el-input v-model="form.username" placeholder="例如 driver01" clearable />
        </el-form-item>
        <el-form-item label="姓名" prop="fullName">
          <el-input v-model="form.fullName" placeholder="请输入真实姓名" clearable />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="11 位手机号" clearable />
        </el-form-item>
        <el-form-item label="身份证号（选填）" prop="idCard">
          <el-input v-model="form.idCard" placeholder="选填，不填则系统自动生成" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" show-password @keyup.enter="onSubmit" />
        </el-form-item>
        <div class="action-row">
          <el-button type="primary" :loading="authStore.loading" class="btn" @click="onSubmit">注册并登录</el-button>
          <el-button class="btn btn-secondary" @click="goLogin">返回登录</el-button>
        </div>
      </el-form>
    </section>
  </main>
</template>

<style scoped>
.register-page {
  min-height: 100vh;
  padding: clamp(16px, 3vw, 34px);
  display: grid;
  grid-template-columns: 1.2fr minmax(320px, 460px);
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

.action-row {
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr 1fr;
}

.btn {
  width: 100%;
  margin-top: 10px;
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
  .register-page {
    grid-template-columns: 1fr;
  }
}
</style>
